#!/usr/bin/env python3
"""Guarded Resend HTTPS API harness; stdout is always one redacted JSON object."""
from __future__ import annotations

import argparse, base64, datetime, fcntl, hashlib, json, mimetypes, os, re, stat, sys, time, urllib.error, urllib.parse, urllib.request, uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
SCHEMA = "1.0"
DEFAULT_BASE = "https://api.resend.com"
MAX_RECIPIENTS = 1000
MAX_ATTACHMENTS = 10
MAX_ATTACHMENT_BYTES = 10_000_000
MAX_TOTAL_ATTACHMENT_BYTES = 25_000_000
SECRET_KEYS = {"authorization", "api_key", "apikey", "token", "secret", "credential"}
SECRET_RE = re.compile(r"(?i)(bearer\s+\S+|re_[A-Za-z0-9_-]{8,})")
EMAIL_RE = re.compile(r"^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$")

class HarnessError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False, status: int | None = None, retry_after: float | None = None):
        super().__init__(message); self.code=code; self.retryable=retryable; self.status=status; self.retry_after=retry_after

def redact(value: Any, key: str = "") -> Any:
    if key.lower() in SECRET_KEYS: return "[REDACTED]"
    if isinstance(value, str): return SECRET_RE.sub("[REDACTED]", value)
    if isinstance(value, dict): return {k: redact(v, k) for k, v in value.items()}
    if isinstance(value, list): return [redact(v) for v in value]
    return value

def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def output(command: str, ok: bool, *, data: Any = None, error: HarnessError | None = None, effects: str = "none", retry: dict | None = None) -> dict:
    result={"schema_version":SCHEMA,"ok":ok,"command":command,"request_id":str(uuid.uuid4()),"effects":{"status":effects},"retry":retry or {"retryable":False,"retry_after_seconds":None},"warnings":[]}
    if data is not None: result["data"]=redact(data)
    if error: result["error"]={"code":error.code,"message":str(error),"http_status":error.status}
    return redact(result)

def email(value: str, field: str) -> str:
    value=value.strip().lower()
    if not EMAIL_RE.fullmatch(value): raise HarnessError("invalid_input", f"{field} contains an invalid email address")
    return value

def emails(raw: str | None, field: str, limit: int) -> list[str]:
    if not raw: return []
    try: values=json.loads(raw)
    except json.JSONDecodeError: values=[x.strip() for x in raw.split(",") if x.strip()]
    if not isinstance(values,list) or len(values)>limit: raise HarnessError("invalid_input", f"{field} must contain at most {limit} addresses")
    return [email(str(x),field) for x in values]

def secure_file(path: Path, *, must_exist: bool = True) -> None:
    try: info=path.lstat()
    except FileNotFoundError:
        if must_exist: raise HarnessError("not_configured", "policy is not configured; run onboarding.configure")
        return
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o600:
        raise HarnessError("unsafe_storage", "private state must be a non-symlink regular file with mode 0600")

def secure_parent(path: Path) -> None:
    try: info=path.parent.lstat()
    except OSError as exc: raise HarnessError("unsafe_storage",f"private state parent is unavailable: {exc}")
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode)&0o077:
        raise HarnessError("unsafe_storage", "private state parent must already exist and be private (mode 0700)")

def read_private_json(path: Path, missing_code: str) -> dict:
    secure_file(path)
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd) as fh: return json.load(fh)
    except (OSError,json.JSONDecodeError) as exc: raise HarnessError(missing_code,f"cannot read valid private state: {exc}")

def load_policy(path: str) -> dict:
    p=Path(path); value=read_private_json(p,"invalid_policy")
    if value.get("schema_version") != 1: raise HarnessError("invalid_policy", "unsupported policy schema")
    required={"allowed_recipient_domains","allowed_sender_domains","max_recipients_per_operation","allow_attachments","allow_single","allow_bulk","max_recipients_per_day","usage_state_path"}
    if not required<=value.keys(): raise HarnessError("invalid_policy","policy is missing required standing-authorization fields")
    return value

def write_policy(path: str, policy: dict) -> None:
    p=Path(path)
    secure_file(p,must_exist=False)
    secure_parent(p)
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as fh: json.dump(policy,fh,sort_keys=True,separators=(",",":")); fh.write("\n")

def utc_day() -> str: return datetime.datetime.now(datetime.timezone.utc).date().isoformat()

class DailyQuota:
    """Durable fail-closed daily quota with cross-process reservations."""
    def __init__(self, policy: dict):
        self.limit=policy["max_recipients_per_day"]
        self.path=Path(policy["usage_state_path"])
        self.lock_path=self.path.with_name(self.path.name+".lock")
        self.reservation_id: str | None=None

    def _locked(self):
        secure_parent(self.path)
        secure_file(self.path,must_exist=False)
        secure_file(self.lock_path,must_exist=False)
        try: fd=os.open(self.lock_path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        except OSError as exc: raise HarnessError("unsafe_storage",f"cannot open private usage lock: {exc}")
        os.fchmod(fd,0o600); fcntl.flock(fd,fcntl.LOCK_EX)
        return os.fdopen(fd,"r+")

    def _read(self) -> dict:
        try: self.path.lstat()
        except FileNotFoundError: return {"schema_version":1,"date":utc_day(),"used":0,"reservations":{}}
        value=read_private_json(self.path,"invalid_usage_state")
        reservations=value.get("reservations")
        if value.get("schema_version")!=1 or not isinstance(value.get("used"),int) or value["used"]<0 or not isinstance(reservations,dict) or any(not isinstance(x,int) or x<1 for x in reservations.values()):
            raise HarnessError("invalid_usage_state","usage state has an invalid schema")
        if value.get("date")!=utc_day(): return {"schema_version":1,"date":utc_day(),"used":0,"reservations":{}}
        return value

    def _write(self, value: dict) -> None:
        tmp=self.path.with_name(self.path.name+"."+uuid.uuid4().hex+".tmp")
        try:
            fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,"w") as fh:
                json.dump(value,fh,sort_keys=True,separators=(",",":")); fh.write("\n"); fh.flush(); os.fsync(fh.fileno())
            os.replace(tmp,self.path)
            parent_fd=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY)
            try: os.fsync(parent_fd)
            finally: os.close(parent_fd)
        finally:
            try: tmp.unlink()
            except FileNotFoundError: pass

    def reserve(self, count: int) -> None:
        with self._locked():
            state=self._read(); reserved=sum(state["reservations"].values())
            if state["used"]+reserved+count>self.limit: raise HarnessError("daily_quota_exhausted","daily recipient limit is exhausted")
            self.reservation_id=uuid.uuid4().hex; state["reservations"][self.reservation_id]=count; self._write(state)

    def finish(self, successful: int) -> None:
        if self.reservation_id is None: return
        with self._locked():
            state=self._read(); reserved=state["reservations"].pop(self.reservation_id,None)
            if reserved is None: raise HarnessError("invalid_usage_state","quota reservation is missing")
            if successful<0 or successful>reserved: raise HarnessError("invalid_usage_state","successful count exceeds reservation")
            state["used"]+=successful; self._write(state)
        self.reservation_id=None

def api_key() -> str:
    key=os.environ.get("RESEND_API_KEY","")
    if not key: raise HarnessError("not_connected", "credential unavailable; use the protected secret-capture handoff and runtime injection")
    return key

class Client:
    def __init__(self, base: str, timeout: float, retries: int):
        if not base.startswith("https://") and not (os.environ.get("RESEND_TEST_MODE")=="1" and base.startswith("http://127.0.0.1:")):
            raise HarnessError("invalid_input","base URL must use HTTPS")
        self.base=base.rstrip("/"); self.timeout=timeout; self.retries=retries
    def request(self, method: str, path: str, body: dict | None = None, idem: str | None = None) -> tuple[dict,int,float|None]:
        payload=None if body is None else json.dumps(body,separators=(",",":")).encode()
        headers={"Authorization":"Bearer "+api_key(),"Content-Type":"application/json","User-Agent":"clawpod-resend-email/"+VERSION}
        if idem: headers["Idempotency-Key"]=idem
        for attempt in range(self.retries+1):
            try:
                req=urllib.request.Request(self.base+path,data=payload,headers=headers,method=method)
                with urllib.request.urlopen(req,timeout=self.timeout) as response:
                    raw=response.read(); return (json.loads(raw) if raw else {},attempt+1,None)
            except urllib.error.HTTPError as exc:
                exc.read(); retry_after=parse_retry_after(exc.headers.get("Retry-After"))
                message="Resend API request failed"
                retryable=exc.code==429 or exc.code>=500
                if retryable and attempt<self.retries:
                    time.sleep(min(retry_after if retry_after is not None else .25*(2**attempt),2)); continue
                raise HarnessError("rate_limited" if exc.code==429 else "backend_failure",message,retryable=retryable,status=exc.code,retry_after=retry_after)
            except (urllib.error.URLError,TimeoutError) as exc:
                if attempt<self.retries: time.sleep(.1*(2**attempt)); continue
                raise HarnessError("transport_failure",f"Resend API unavailable: {exc}",retryable=True)
        raise AssertionError

def parse_retry_after(value: str | None) -> float | None:
    if value is None: return None
    try: return max(0.0,float(value))
    except ValueError: return None

def attachment(path: str) -> dict:
    p=Path(path)
    if p.is_symlink() or not p.is_file(): raise HarnessError("invalid_input","attachment must be a regular non-symlink file")
    size=p.stat().st_size
    if size>MAX_ATTACHMENT_BYTES: raise HarnessError("invalid_input",f"attachment exceeds {MAX_ATTACHMENT_BYTES} bytes")
    return {"filename":p.name,"content":base64.b64encode(p.read_bytes()).decode(),"content_type":mimetypes.guess_type(p.name)[0] or "application/octet-stream","_size":size}

def message_from_args(a, recipient: str | None = None) -> dict:
    to=[recipient] if recipient else emails(a.to,"to",50)
    if not to: raise HarnessError("invalid_input","at least one recipient is required")
    if not a.text and not a.html: raise HarnessError("invalid_input","text or html content is required")
    msg={"from":a.from_address,"to":to,"subject":a.subject}
    email(a.from_address.rsplit("<",1)[-1].rstrip(">"),"from")
    if a.text: msg["text"]=a.text
    if a.html: msg["html"]=a.html
    cc=emails(a.cc,"cc",10); bcc=emails(a.bcc,"bcc",10); reply=emails(a.reply_to,"reply_to",5)
    if recipient and (cc or bcc): raise HarnessError("invalid_input","bulk cc/bcc is unsafe and unsupported")
    if cc: msg["cc"]=cc
    if bcc: msg["bcc"]=bcc
    if reply: msg["reply_to"]=reply
    paths=a.attachment or []
    if len(paths)>MAX_ATTACHMENTS: raise HarnessError("invalid_input",f"at most {MAX_ATTACHMENTS} attachments are allowed")
    items=[attachment(x) for x in paths]
    if sum(x.pop("_size") for x in items)>MAX_TOTAL_ATTACHMENT_BYTES: raise HarnessError("invalid_input","total attachments exceed bounded limit")
    if items: msg["attachments"]=items
    return msg

def domain_of(address: str) -> str: return address.rsplit("@",1)[1].rstrip(">").lower()

def enforce(policy: dict, msg: dict, count: int, mode: str) -> None:
    if mode=="single" and not policy["allow_single"]: raise HarnessError("policy_violation","single send is disabled by standing policy")
    if mode=="bulk" and not policy["allow_bulk"]: raise HarnessError("policy_violation","bulk send is disabled by standing policy")
    recipients=[*msg["to"],*msg.get("cc",[]),*msg.get("bcc",[])]
    allowed=set(policy["allowed_recipient_domains"])
    if count>policy["max_recipients_per_operation"]: raise HarnessError("policy_violation","recipient count exceeds standing policy")
    if any(domain_of(x) not in allowed for x in recipients): raise HarnessError("policy_violation","recipient is outside allowed domains")
    if domain_of(msg["from"]) not in set(policy["allowed_sender_domains"]): raise HarnessError("policy_violation","sender is outside allowed domains")
    if msg.get("attachments") and not policy["allow_attachments"]: raise HarnessError("policy_violation","attachments are not authorized by standing policy")

def preview_data(msg: dict, count: int, policy: dict) -> dict:
    safe={k:v for k,v in msg.items() if k not in {"text","html","attachments"}}
    safe["content"]={"text_bytes":len(msg.get("text","").encode()),"html_bytes":len(msg.get("html","").encode()),"attachment_count":len(msg.get("attachments",[]))}
    return {"authorized":True,"recipient_count":count,"message":safe,"intent_digest":digest(msg),"policy_digest":digest(policy)}

def command(a) -> dict:
    if a.command=="onboarding":
        return output(a.command,True,data={"state":"installed_but_unconnected","next":"onboarding.configure","secret_handoff":{"required":True,"environment":"RESEND_API_KEY","protected_storage_only":True,"never_chat_files_args_logs":True},"standing_policy":"Configure once; in-policy sends need no per-send approval and out-of-policy sends fail closed."})
    if a.command=="status":
        configured=Path(a.policy).is_file(); connected=bool(os.environ.get("RESEND_API_KEY"))
        return output(a.command,True,data={"state":"ready" if configured and connected else "installed_but_unconnected","configured":configured,"credential_available":connected})
    if a.command=="onboarding.configure":
        recipient_domains=sorted(set(x.strip().lower() for x in a.allowed_recipient_domains.split(",") if x.strip()))
        sender_domains=sorted(set(x.strip().lower() for x in a.allowed_sender_domains.split(",") if x.strip()))
        if not recipient_domains or not sender_domains or any("@" in x for x in recipient_domains+sender_domains): raise HarnessError("invalid_input","provide bare allowed domains")
        usage_path=str(Path(a.policy).with_name(Path(a.policy).name+".usage.json").absolute())
        policy={"schema_version":1,"allowed_recipient_domains":recipient_domains,"allowed_sender_domains":sender_domains,"max_recipients_per_operation":a.max_recipients,"allow_attachments":a.allow_attachments,"allow_single":a.allow_single,"allow_bulk":a.allow_bulk,"max_recipients_per_day":a.max_recipients_per_day,"usage_state_path":usage_path,"created_by":"resend-email onboarding"}
        write_policy(a.policy,policy)
        return output(a.command,True,data={"configured":True,"policy_digest":digest(policy),"credential_stored":False,"next":"capture RESEND_API_KEY only through protected secret storage, then run verify"},effects="local_policy_configured")
    client=Client(a.base_url,a.timeout,a.retries)
    if a.command=="verify":
        domains,attempts,_=client.request("GET","/domains")
        return output(a.command,True,data={"connected":True,"domain_count":len(domains.get("data",domains if isinstance(domains,list) else []))},retry={"attempts":attempts,"retryable":False,"retry_after_seconds":None})
    if a.command in {"domains.list","readiness","sender.readiness"}:
        domains,attempts,_=client.request("GET","/domains"); items=domains.get("data",domains if isinstance(domains,list) else [])
        ready=[{"id":x.get("id"),"name":x.get("name"),"status":x.get("status"),"ready":x.get("status")=="verified"} for x in items]
        data={"domains":ready,"all_ready":bool(ready) and all(x["ready"] for x in ready)}
        if a.command=="sender.readiness":
            sender_domain=domain_of(email(a.from_address.rsplit("<",1)[-1].rstrip(">"),"from"))
            match=next((x for x in ready if x["name"]==sender_domain),None)
            data={"sender_domain":sender_domain,"ready":bool(match and match["ready"]),"domain":match}
        return output(a.command,True,data=data,retry={"attempts":attempts,"retryable":False,"retry_after_seconds":None})
    policy=load_policy(a.policy)
    if a.command in {"preview","send"}:
        msg=message_from_args(a); count=len(msg["to"])+len(msg.get("cc",[]))+len(msg.get("bcc",[])); enforce(policy,msg,count,"single")
        preview=preview_data(msg,len(msg["to"]),policy)
        if a.command=="preview" or a.dry_run: return output(a.command,True,data={"dry_run":True,"preview":preview})
        quota=DailyQuota(policy); quota.reserve(count)
        key=a.idempotency_key or preview["intent_digest"]
        try: result,attempts,_=client.request("POST","/emails",msg,key)
        except HarnessError:
            quota.finish(0); raise
        quota.finish(count)
        return output(a.command,True,data={"id":result.get("id"),"idempotency_key":key,"preview":preview},effects="email_submitted",retry={"attempts":attempts,"retryable":False,"retry_after_seconds":None})
    if a.command=="bulk.send":
        recipients=list(dict.fromkeys(emails(a.to,"to",MAX_RECIPIENTS)))
        if not recipients: raise HarnessError("invalid_input","at least one recipient is required")
        sample=message_from_args(a,recipients[0]); enforce(policy,sample,len(recipients),"bulk")
        base_key=a.idempotency_key or digest({"recipients":recipients,"message":sample})
        if a.dry_run: return output(a.command,True,data={"dry_run":True,"deduplicated_count":len(recipients),"preview":preview_data(sample,len(recipients),policy),"idempotency_key":base_key})
        quota=DailyQuota(policy); quota.reserve(len(recipients))
        def deliver(index_address):
            index,address=index_address; msg=message_from_args(a,address); key=f"{base_key}:{digest(address)[:16]}"
            try:
                result,attempts,_=client.request("POST","/emails",msg,key); return {"recipient":address,"ok":True,"id":result.get("id"),"idempotency_key":key,"attempts":attempts}
            except HarnessError as exc:
                return {"recipient":address,"ok":False,"error":{"code":exc.code,"message":str(exc),"http_status":exc.status},"idempotency_key":key,"retry_safe":bool(exc.retryable),"retry_after_seconds":exc.retry_after}
        results=[]
        try:
            for start in range(0,len(recipients),a.batch_size):
                with ThreadPoolExecutor(max_workers=a.concurrency) as pool:
                    futures=[pool.submit(deliver,x) for x in enumerate(recipients[start:start+a.batch_size],start)]
                    results.extend(f.result() for f in as_completed(futures))
                if a.rate_per_second>0 and start+a.batch_size<len(recipients): time.sleep(a.batch_size/a.rate_per_second)
        except BaseException:
            # Unknown completion state: retain the full durable reservation and fail closed.
            raise
        results.sort(key=lambda x:recipients.index(x["recipient"])); failed=[x for x in results if not x["ok"]]
        quota.finish(len(results)-len(failed))
        data={"submitted":len(results)-len(failed),"failed":len(failed),"partial_failure":bool(failed) and len(failed)<len(results),"retry_safe":all(x.get("retry_safe",True) for x in failed),"idempotency_key":base_key,"results":results}
        return output(a.command,not failed,data=data,effects="partial_email_submission" if failed else "emails_submitted")
    raise HarnessError("invalid_input","unknown command")

class JsonParser(argparse.ArgumentParser):
    def error(self,message): raise HarnessError("invalid_input",message)

def parser() -> argparse.ArgumentParser:
    p=JsonParser(); p.add_argument("command",choices=["onboarding","status","onboarding.configure","verify","domains.list","readiness","sender.readiness","preview","send","bulk.send"])
    p.add_argument("--policy",default="resend-policy.json"); p.add_argument("--base-url",default=DEFAULT_BASE); p.add_argument("--timeout",type=float,default=10); p.add_argument("--retries",type=int,default=2)
    p.add_argument("--allowed-recipient-domains"); p.add_argument("--allowed-sender-domains"); p.add_argument("--max-recipients",type=int,default=100); p.add_argument("--allow-attachments",action="store_true"); p.add_argument("--allow-single",action="store_true"); p.add_argument("--allow-bulk",action="store_true"); p.add_argument("--max-recipients-per-day",type=int)
    p.add_argument("--from",dest="from_address"); p.add_argument("--to"); p.add_argument("--subject"); p.add_argument("--text"); p.add_argument("--html"); p.add_argument("--reply-to"); p.add_argument("--cc"); p.add_argument("--bcc"); p.add_argument("--attachment",action="append")
    p.add_argument("--dry-run",action="store_true"); p.add_argument("--idempotency-key"); p.add_argument("--batch-size",type=int,default=100); p.add_argument("--concurrency",type=int,default=4); p.add_argument("--rate-per-second",type=float,default=2)
    return p

def validate_args(a) -> None:
    for name,value,low,high in [("timeout",a.timeout,.1,30),("retries",a.retries,0,5),("max recipients",a.max_recipients,1,MAX_RECIPIENTS),("batch size",a.batch_size,1,100),("concurrency",a.concurrency,1,10),("rate",a.rate_per_second,.1,100)]:
        if value<low or value>high: raise HarnessError("invalid_input",f"{name} must be between {low} and {high}")
    if a.command in {"preview","send","bulk.send"} and (not a.from_address or not a.subject): raise HarnessError("invalid_input","--from and --subject are required")
    if a.command=="sender.readiness" and not a.from_address: raise HarnessError("invalid_input","--from is required")
    if a.command=="onboarding.configure" and (not a.allowed_recipient_domains or not a.allowed_sender_domains or a.max_recipients_per_day is None): raise HarnessError("invalid_input","allowed domains and max recipients per day are required")
    if a.command=="onboarding.configure" and not 1<=a.max_recipients_per_day<=1_000_000: raise HarnessError("invalid_input","max recipients per day must be between 1 and 1000000")

def main(argv=None) -> int:
    raw=list(argv) if argv is not None else sys.argv[1:]
    try: a=parser().parse_args(raw); validate_args(a); result=command(a)
    except HarnessError as exc:
        cmd=getattr(locals().get("a"),"command",raw[0] if raw else "unknown")
        result=output(cmd,False,error=exc,retry={"retryable":exc.retryable,"retry_after_seconds":exc.retry_after})
    print(json.dumps(redact(result),sort_keys=True,separators=(",",":"))); return 0 if result["ok"] else 2

if __name__=="__main__": raise SystemExit(main())
