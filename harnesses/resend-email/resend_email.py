#!/usr/bin/env python3
"""Guarded Resend HTTPS API harness; stdout is always one redacted JSON object."""
from __future__ import annotations

import argparse, base64, datetime, hashlib, json, mimetypes, os, re, stat, sys, tempfile, time, urllib.error, urllib.parse, urllib.request, uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

VERSION = "0.1.2"
SCHEMA = "1.0"
DEFAULT_BASE = "https://api.resend.com"
MAX_RECIPIENTS = 1000
MAX_ATTACHMENTS = 10
MAX_ATTACHMENT_BYTES = 10_000_000
MAX_TOTAL_ATTACHMENT_BYTES = 25_000_000
SECRET_KEYS = {"authorization", "api_key", "apikey", "token", "secret", "credential"}
SECRET_RE = re.compile(r"(?i)(bearer\s+\S+|re_[A-Za-z0-9_-]{8,})")
EMAIL_RE = re.compile(r"^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$")
ONBOARDING_STATE_FIELDS = {"provider_accepted", "message_id", "accepted_at", "sender_domain", "test_recipient_sha256"}

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

def api_key() -> str:
    key=os.environ.get("RESEND_API_KEY","")
    if not key: raise HarnessError("not_connected", "credential unavailable; capture with owner-only memory_secret routing and inject through RESEND_API_KEY")
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

def private_state_path(raw: str, *, may_be_missing: bool) -> Path:
    path=Path(raw).expanduser()
    if not path.is_absolute(): raise HarnessError("unsafe_state_path","onboarding state path must be absolute")
    if path.exists() and path.is_symlink(): raise HarnessError("unsafe_state_path","onboarding state must not be a symlink")
    parent=path.parent
    if not parent.is_dir() or parent.is_symlink(): raise HarnessError("unsafe_state_path","onboarding state parent must be an existing private directory")
    resolved_parent=parent.resolve(strict=True)
    if resolved_parent != parent: raise HarnessError("unsafe_state_path","onboarding state parent must not contain symlink indirection")
    if stat.S_IMODE(parent.stat().st_mode) & 0o077: raise HarnessError("unsafe_state_path","onboarding state parent must not be accessible by group or other users")
    if path.exists():
        mode=path.stat().st_mode
        if not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077: raise HarnessError("unsafe_state_path","onboarding state must be a private regular file")
    elif not may_be_missing:
        raise HarnessError("onboarding_incomplete","private onboarding test state is unavailable")
    return path

def read_onboarding_state(raw: str | None) -> dict | None:
    if not raw: return None
    path=private_state_path(raw,may_be_missing=True)
    if not path.exists(): return None
    try: value=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,UnicodeError,json.JSONDecodeError): return None
    if not isinstance(value,dict) or set(value)!=ONBOARDING_STATE_FIELDS: return None
    if value.get("provider_accepted") is not True: return None
    if not all(isinstance(value.get(k),str) and value[k] for k in ONBOARDING_STATE_FIELDS-{"provider_accepted"}): return None
    if not re.fullmatch(r"[0-9a-f]{64}",value["test_recipient_sha256"]): return None
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}",value["message_id"]): return None
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z0-9-]+",value["sender_domain"]): return None
    try: datetime.datetime.fromisoformat(value["accepted_at"].replace("Z","+00:00"))
    except ValueError: return None
    return value

def write_onboarding_state(raw: str, value: dict) -> None:
    path=private_state_path(raw,may_be_missing=True)
    fd,tmp=tempfile.mkstemp(prefix=".resend-onboarding-",dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(value,stream,sort_keys=True,separators=(",",":")); stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def onboarding_status(state_path: str | None) -> dict:
    connected=bool(os.environ.get("RESEND_API_KEY"))
    state=read_onboarding_state(state_path)
    complete=connected and state is not None
    return {"state":"onboarding_complete" if complete else "connected_not_verified" if connected else "installed_but_unconnected","onboarding":"onboarding_complete" if complete else "onboarding_incomplete","credential_available":connected,"provider_test_accepted":bool(state),"delivery_confirmed":False}

def preview_data(msg: dict, count: int) -> dict:
    safe={k:v for k,v in msg.items() if k not in {"text","html","attachments"}}
    safe["content"]={"text_bytes":len(msg.get("text","").encode()),"html_bytes":len(msg.get("html","").encode()),"attachment_count":len(msg.get("attachments",[]))}
    return {"authorized":True,"recipient_count":count,"message":safe,"intent_digest":digest(msg)}

def verified_sender(client: Client, msg: dict) -> int:
    domains,attempts,_=client.request("GET","/domains")
    items=domains.get("data",domains if isinstance(domains,list) else [])
    sender_domain=domain_of(msg["from"])
    if not any(str(x.get("name","")).lower()==sender_domain and x.get("status")=="verified" for x in items):
        raise HarnessError("sender_not_ready","sender domain is not verified")
    return attempts

def command(a) -> dict:
    if a.command=="onboarding":
        data=onboarding_status(a.state)
        data.update({"next":["if supplied in the Room or a message, route the key immediately to owner-only memory_secret without repeating it","inject the stored secret as RESEND_API_KEY only for a separately approved verify operation","run sender.readiness with the intended sender address","only then ask for one test recipient and run onboarding.test"],"secret_handoff":{"required":not data["credential_available"],"source":"Room or message","storage":"memory_secret","owner_only":True,"environment":"RESEND_API_KEY","environment_injection_only":True,"argument_allowed":False,"plaintext_persistence_allowed":False,"plaintext_output_allowed":False,"protected_ui_required":False,"retain":"safe pointer metadata only"},"send_defaults":{"single":True,"bulk":True,"attachments":True,"recipient_domains":"any syntactically valid domain","user_configured_send_limits":False},"sender_requirement":"Live sends fail closed unless the sender domain is verified by Resend."})
        return output(a.command,True,data=data)
    if a.command=="status":
        data=onboarding_status(a.state); data["persistent_policy_required"]=False
        return output(a.command,True,data=data)
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
    if a.command=="onboarding.test":
        sender=email(a.from_address.rsplit("<",1)[-1].rstrip(">"),"from")
        recipient=email(a.to,"to")
        msg={"from":a.from_address,"to":[recipient],"subject":"[Resend onboarding test] Provider submission check","text":"Resend onboarding test: provider submission check. Inbox delivery is not confirmed by this message submission."}
        readiness_attempts=verified_sender(client,msg)
        recipient_hash=hashlib.sha256(recipient.encode()).hexdigest()
        idem="resend-onboarding-v1-"+digest({"sender":sender,"test_recipient_sha256":recipient_hash})
        prior=read_onboarding_state(a.state)
        if prior and prior["sender_domain"]==domain_of(sender) and prior["test_recipient_sha256"]==recipient_hash:
            return output(a.command,True,data={"provider_accepted":True,"message_id":prior["message_id"],"accepted_at":prior["accepted_at"],"sender_domain":prior["sender_domain"],"test_recipient_sha256":recipient_hash,"idempotent":True,"delivery_confirmed":False,"meaning":"Resend previously accepted this test submission; inbox delivery is not confirmed."},retry={"attempts":readiness_attempts,"retryable":False,"retry_after_seconds":None})
        result,attempts,_=client.request("POST","/emails",msg,idem)
        message_id=result.get("id")
        if not isinstance(message_id,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}",message_id): raise HarnessError("backend_failure","Resend did not return a safe message id for the accepted submission")
        accepted_at=datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00","Z")
        state={"provider_accepted":True,"message_id":message_id,"accepted_at":accepted_at,"sender_domain":domain_of(sender),"test_recipient_sha256":recipient_hash}
        write_onboarding_state(a.state,state)
        return output(a.command,True,data={**state,"idempotent":False,"delivery_confirmed":False,"meaning":"Resend accepted the test message for submission; inbox delivery is not confirmed."},effects="email_submitted",retry={"attempts":readiness_attempts+attempts,"retryable":False,"retry_after_seconds":None})
    if a.command in {"preview","send"}:
        msg=message_from_args(a); preview=preview_data(msg,len(msg["to"]))
        if a.command=="preview" or a.dry_run: return output(a.command,True,data={"dry_run":True,"preview":preview})
        readiness_attempts=verified_sender(client,msg)
        key=a.idempotency_key or preview["intent_digest"]
        result,attempts,_=client.request("POST","/emails",msg,key)
        return output(a.command,True,data={"id":result.get("id"),"idempotency_key":key,"preview":preview,"sender_verified":True},effects="email_submitted",retry={"attempts":readiness_attempts+attempts,"retryable":False,"retry_after_seconds":None})
    if a.command=="bulk.send":
        recipients=list(dict.fromkeys(emails(a.to,"to",MAX_RECIPIENTS)))
        if not recipients: raise HarnessError("invalid_input","at least one recipient is required")
        sample=message_from_args(a,recipients[0])
        base_key=a.idempotency_key or digest({"recipients":recipients,"message":sample})
        if a.dry_run: return output(a.command,True,data={"dry_run":True,"deduplicated_count":len(recipients),"preview":preview_data(sample,len(recipients)),"idempotency_key":base_key})
        verified_sender(client,sample)
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
            # Unknown completion state: surface failure and rely on stable idempotency keys.
            raise
        results.sort(key=lambda x:recipients.index(x["recipient"])); failed=[x for x in results if not x["ok"]]
        data={"submitted":len(results)-len(failed),"failed":len(failed),"partial_failure":bool(failed) and len(failed)<len(results),"retry_safe":all(x.get("retry_safe",True) for x in failed),"idempotency_key":base_key,"results":results}
        return output(a.command,not failed,data=data,effects="partial_email_submission" if failed else "emails_submitted")
    raise HarnessError("invalid_input","unknown command")

class JsonParser(argparse.ArgumentParser):
    def error(self,message): raise HarnessError("invalid_input",message)

def parser() -> argparse.ArgumentParser:
    p=JsonParser(); p.add_argument("command",choices=["onboarding","status","verify","domains.list","readiness","sender.readiness","onboarding.test","preview","send","bulk.send"])
    p.add_argument("--base-url",default=DEFAULT_BASE); p.add_argument("--timeout",type=float,default=10); p.add_argument("--retries",type=int,default=2)
    p.add_argument("--from",dest="from_address"); p.add_argument("--to"); p.add_argument("--subject"); p.add_argument("--text"); p.add_argument("--html"); p.add_argument("--reply-to"); p.add_argument("--cc"); p.add_argument("--bcc"); p.add_argument("--attachment",action="append")
    p.add_argument("--dry-run",action="store_true"); p.add_argument("--idempotency-key"); p.add_argument("--batch-size",type=int,default=100); p.add_argument("--concurrency",type=int,default=4); p.add_argument("--rate-per-second",type=float,default=2)
    p.add_argument("--state")
    return p

def validate_args(a) -> None:
    for name,value,low,high in [("timeout",a.timeout,.1,30),("retries",a.retries,0,5),("batch size",a.batch_size,1,100),("concurrency",a.concurrency,1,10),("rate",a.rate_per_second,.1,100)]:
        if value<low or value>high: raise HarnessError("invalid_input",f"{name} must be between {low} and {high}")
    if a.command in {"preview","send","bulk.send"} and (not a.from_address or not a.subject): raise HarnessError("invalid_input","--from and --subject are required")
    if a.command=="sender.readiness" and not a.from_address: raise HarnessError("invalid_input","--from is required")
    if a.command=="onboarding.test" and (not a.from_address or not a.to or not a.state): raise HarnessError("invalid_input","--from, --to, and --state are required")

def main(argv=None) -> int:
    raw=list(argv) if argv is not None else sys.argv[1:]
    try: a=parser().parse_args(raw); validate_args(a); result=command(a)
    except HarnessError as exc:
        cmd=getattr(locals().get("a"),"command",raw[0] if raw else "unknown")
        result=output(cmd,False,error=exc,retry={"retryable":exc.retryable,"retry_after_seconds":exc.retry_after})
    print(json.dumps(redact(result),sort_keys=True,separators=(",",":"))); return 0 if result["ok"] else 2

if __name__=="__main__": raise SystemExit(main())
