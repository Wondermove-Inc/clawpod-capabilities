#!/usr/bin/env python3
"""Typed, guarded Notion REST API harness. Stdlib-only and stdout is one JSON object."""
from __future__ import annotations
import argparse, base64, hashlib, hmac, json, os, re, socket, sys, time, urllib.error, urllib.parse, urllib.request, uuid
from dataclasses import dataclass
from typing import Any

API_VERSION="2026-03-11"; SCHEMA_VERSION="1.0"; DEFAULT_BASE="https://api.notion.com/v1"; MAX_BODY=500_000
TOKEN_KEYS={"authorization","token","access_token","refresh_token","client_secret","authorization_code","verification_token","signature"}
SECRET_RE=re.compile(r"(?i)(bearer\s+\S+|(?:secret|ntn)_[A-Za-z0-9_-]{8,}|(?:access|refresh)[_-]?token[=:]\s*\S+)")
UUID_RE=re.compile(r"^[0-9a-f]{32}$",re.I)

@dataclass(frozen=True)
class Spec:
 method:str|None; path:str|None; safety:str="readOnly"; paged:bool=False; verify:str|None=None

SPECS={
 "auth.status":Spec(None,None),"auth.onboarding.plan":Spec(None,None),"diagnostics.doctor":Spec(None,None),
 "resolve.id":Spec(None,None),"resolve.url":Spec(None,None),"markdown.validate":Spec(None,None),
 "webhook.signature.verify":Spec(None,None),"webhook.event.parse":Spec(None,None),
 "user.me":Spec("GET","/users/me"),"user.retrieve":Spec("GET","/users/{id}"),"user.list":Spec("GET","/users",paged=True),
 "search.query":Spec("POST","/search",paged=True),"page.retrieve":Spec("GET","/pages/{id}"),
 "page.property.retrieve":Spec("GET","/pages/{id}/properties/{property_id}",paged=True),
 "page.retrieve_markdown":Spec("GET","/pages/{id}/markdown"),"block.retrieve":Spec("GET","/blocks/{id}"),
 "block.children.list":Spec("GET","/blocks/{id}/children",paged=True),"database.retrieve":Spec("GET","/databases/{id}"),
 "data_source.retrieve":Spec("GET","/data_sources/{id}"),"data_source.query":Spec("POST","/data_sources/{id}/query",paged=True),
 "comment.list":Spec("GET","/comments",paged=True),"file_upload.retrieve":Spec("GET","/file_uploads/{id}"),
 "file_upload.list":Spec("GET","/file_uploads",paged=True),
 "page.create":Spec("POST","/pages","externalSideEffect",verify="page"),
 "page.properties.update":Spec("PATCH","/pages/{id}","externalSideEffect",verify="page"),
 "page.archive":Spec("PATCH","/pages/{id}","destructive",verify="page"),
 "page.restore":Spec("PATCH","/pages/{id}","externalSideEffect",verify="page"),
 "block.children.append":Spec("PATCH","/blocks/{id}/children","externalSideEffect"),
 "block.update":Spec("PATCH","/blocks/{id}","externalSideEffect"),"block.delete":Spec("DELETE","/blocks/{id}","destructive"),
 "markdown.page.create":Spec("POST","/pages","externalSideEffect",verify="page"),
 "markdown.page.update":Spec("PATCH","/pages/{id}/markdown","destructive",verify="page"),
 "data_source.schema.update":Spec("PATCH","/data_sources/{id}","externalSideEffect"),
 "comment.create":Spec("POST","/comments","externalSideEffect"),"file_upload.create":Spec("POST","/file_uploads","externalSideEffect"),
}

def redact(v:Any,key:str="")->Any:
 if key.lower() in TOKEN_KEYS:return "[REDACTED]"
 if isinstance(v,str):
  if "amazonaws.com" in v or "X-Amz-" in v:return urllib.parse.urlsplit(v)._replace(query="").geturl()+"?[REDACTED]"
  return SECRET_RE.sub("[REDACTED]",v)
 if isinstance(v,dict):return {k:redact(x,k) for k,x in v.items()}
 if isinstance(v,list):return [redact(x) for x in v]
 return v

def envelope(cmd:str,ok:bool,data:Any=None,error:dict|None=None,**extra:Any)->dict:
 out={"schema_version":SCHEMA_VERSION,"ok":ok,"command":cmd,"request_id":str(uuid.uuid4()),"api_version":API_VERSION,
      "effects":{"performed":False,"created":[],"updated":[],"deleted":[],"unknown":False},"warnings":[],"retry":{"attempts":0,"retryable":False,"retry_after_seconds":None}}
 if data is not None:out["data"]=redact(data)
 if error is not None:out["error"]=redact(error)
 out.update(extra);return out

def normalized_id(value:str)->str:
 raw=value.strip(); raw=urllib.parse.urlsplit(raw).path if "://" in raw else raw
 candidates=re.findall(r"(?<![0-9a-fA-F])(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(?![0-9a-fA-F])",raw)
 if not candidates:raise ValueError("value does not contain a Notion UUID")
 s=candidates[-1].replace("-","").lower();return f"{s[:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:]}"

def canonical(spec:Spec,a:argparse.Namespace,body:dict)->dict:
 path=spec.path
 if path:
  if "{id}" in path:
   if not a.id:raise ValueError("--id is required")
   path=path.replace("{id}",normalized_id(a.id))
  if "{property_id}" in path:
   if not a.property_id:raise ValueError("--property-id is required")
   path=path.replace("{property_id}",urllib.parse.quote(a.property_id,safe=""))
 q={}
 if a.page_size is not None:q["page_size"]=a.page_size
 if a.start_cursor:q["start_cursor"]=a.start_cursor
 if a.command=="comment.list":
  if not a.id:raise ValueError("comment.list requires --id block/page id")
  q["block_id"]=normalized_id(a.id)
 return {"method":spec.method,"path":path,"query":q,"body":body,"api_version":API_VERSION,"safety":spec.safety}

def intent_hash(req:dict)->str:return hashlib.sha256(json.dumps(req,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def parse_body(a:argparse.Namespace)->dict:
 if not a.body:return {}
 try:v=json.loads(a.body)
 except json.JSONDecodeError as e:raise ValueError(f"--body must be JSON: {e.msg}")
 if not isinstance(v,dict):raise ValueError("--body must be a JSON object")
 if len(a.body.encode())>MAX_BODY:raise ValueError("body exceeds 500000 bytes")
 return v

def category(status:int,code:str)->str:
 if status in (401,):return "authentication"
 if status in (403,):return "permission"
 if status==404:return "not_found"
 if status==429:return "rate_limit"
 if status>=500:return "backend"
 return "request"

class ApiError(Exception):
 def __init__(self,status:int,code:str,message:str,request_id:str|None,retry_after:float|None=None):super().__init__(message);self.status=status;self.code=code;self.request_id=request_id;self.retry_after=retry_after

class Transport:
 def __init__(self,a):self.a=a;self.attempts=0
 def request(self,method,path,query,body,mutation=False):
  token=os.environ.get("NOTION_TOKEN")
  if not token:raise ValueError("credential unavailable; inject NOTION_TOKEN only through protected runtime secret handling")
  url=self.a.base_url.rstrip("/")+path
  if query:url+="?"+urllib.parse.urlencode(query)
  payload=None if method=="GET" else json.dumps(body,separators=(",",":")).encode()
  headers={"Authorization":"Bearer "+token,"Notion-Version":API_VERSION,"Content-Type":"application/json","User-Agent":"clawpod-notion/0.1.0"}
  max_attempts=1 if mutation else self.a.retries+1
  for attempt in range(1,max_attempts+1):
   self.attempts=attempt
   try:
    with urllib.request.urlopen(urllib.request.Request(url,payload,headers,method=method),timeout=self.a.timeout_ms/1000) as r:
     raw=r.read(2_000_001)
     if len(raw)>2_000_000:raise RuntimeError("response exceeded 2000000 bytes")
     return json.loads(raw or b"{}"),dict(r.headers)
   except urllib.error.HTTPError as e:
    raw=e.read(256_000)
    try:obj=json.loads(raw)
    except Exception:obj={}
    code=str(obj.get("code","http_error"));msg=str(obj.get("message",f"HTTP {e.code}"));ra=e.headers.get("Retry-After"); delay=float(ra) if ra and ra.replace(".","",1).isdigit() else None
    retry=e.code in (409,429,500,502,503,504,529) and not mutation and attempt<max_attempts
    if retry:time.sleep(min(delay if delay is not None else .05*(2**(attempt-1)),self.a.max_retry_sleep));continue
    raise ApiError(e.code,code,msg,e.headers.get("x-request-id"),delay)
   except (urllib.error.URLError,TimeoutError,socket.timeout) as e:
    if not mutation and attempt<max_attempts:time.sleep(min(.05*(2**(attempt-1)),self.a.max_retry_sleep));continue
    raise RuntimeError("request timed out or transport unavailable") from e

def execute(a,spec,req):
 t=Transport(a); mutation=spec.safety!="readOnly"
 result,headers=t.request(req["method"],req["path"],req["query"],req["body"],mutation)
 items=[];pages=1
 if spec.paged and a.all_pages:
  items.extend(result.get("results",[]))
  while result.get("has_more"):
   if pages>=a.max_pages or len(items)>=a.max_items:break
   cursor=result.get("next_cursor"); q={**req["query"],"start_cursor":cursor}
   result,_=t.request(req["method"],req["path"],q,req["body"],False);pages+=1;items.extend(result.get("results",[]))
  result={"results":items[:a.max_items],"has_more":bool(result.get("has_more") or len(items)>a.max_items),"next_cursor":result.get("next_cursor")}
 effects={"performed":mutation,"created":[],"updated":[],"deleted":[],"unknown":False}
 if mutation:
  rid=result.get("id") if isinstance(result,dict) else None
  bucket="deleted" if spec.safety=="destructive" and a.command in {"block.delete","page.archive"} else "created" if ".create" in a.command else "updated"
  if rid:effects[bucket]=[rid]
 verified=None
 if mutation and spec.verify=="page" and isinstance(result,dict) and result.get("id"):
  try:verified,_=t.request("GET","/pages/"+normalized_id(result["id"]),{}, {},False)
  except Exception as e:raise RuntimeError("mutation returned success but source-of-truth verification failed") from e
 out=envelope(a.command,True,result,effects=effects,notion_request_id=headers.get("x-request-id"),retry={"attempts":t.attempts,"retryable":False,"retry_after_seconds":None})
 if verified is not None:out["verification"]={"performed":True,"resource_id":verified.get("id"),"last_edited_time":verified.get("last_edited_time")}
 return out

def local(a):
 if a.command=="auth.status":return {"connected":bool(os.environ.get("NOTION_TOKEN")),"credential_source":"protected runtime injection" if os.environ.get("NOTION_TOKEN") else None,"installed_but_not_connected":not bool(os.environ.get("NOTION_TOKEN")),"api_version":API_VERSION}
 if a.command=="auth.onboarding.plan":
  mode=a.auth_mode or "internal"
  return {"recommended":mode,"modes":{"internal":"team-owned automation; create integration, grant minimum capabilities, share explicit roots","pat":"personal development only; user-scoped and expiring","oauth":"multi-user product; authorization-code flow planned, token exchange intentionally outside v0.1.0"},"human_steps":["choose the exact workspace/account","create or authorize the integration","select minimum capabilities","share only approved root pages/data sources","provide the token through protected secret storage"],"agent_steps_after_approval":["inject credential without exposing it","verify user.me identity and workspace","check required capabilities through bounded probes","retrieve each approved root by exact ID"],"revoke":"revoke the integration/PAT in Notion and delete the protected secret pointer","connected":False}
 if a.command=="diagnostics.doctor":return {"api_version":API_VERSION,"base_url":a.base_url,"credential_present":bool(os.environ.get("NOTION_TOKEN")),"network_probe_performed":False,"next":"run user.me with approved protected credential use, then retrieve each approved root"}
 if a.command in {"resolve.id","resolve.url"}:return {"id":normalized_id(a.id or a.url or "")}
 if a.command=="markdown.validate":
  text=a.markdown if a.markdown is not None else "";unknown="<unknown" in text.lower();return {"valid":len(text.encode())<=MAX_BODY,"bytes":len(text.encode()),"unknown_block_marker":unknown,"recommendation":"blocks" if unknown or any(x in text for x in ("<table","<synced_block","<database")) else "markdown"}
 if a.command=="webhook.signature.verify":
  secret=os.environ.get("NOTION_WEBHOOK_SECRET")
  if not secret:raise ValueError("webhook secret unavailable; inject NOTION_WEBHOOK_SECRET through protected runtime handling")
  if a.raw_body_b64 is None or a.signature is None:raise ValueError("--raw-body-b64 and --signature are required")
  try:raw=base64.b64decode(a.raw_body_b64,validate=True)
  except Exception as e:raise ValueError("invalid base64 raw body") from e
  supplied=a.signature.removeprefix("sha256="); expected=hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
  return {"valid":hmac.compare_digest(expected,supplied),"algorithm":"hmac-sha256","body_sha256":hashlib.sha256(raw).hexdigest()}
 if a.command=="webhook.event.parse":
  body=parse_body(a);return {"event_id":body.get("id"),"type":body.get("type"),"timestamp":body.get("timestamp"),"entity":redact(body.get("entity")),"dedupe_key":body.get("id")}
 raise ValueError("unknown local command")

def parser():
 p=argparse.ArgumentParser();p.add_argument("command",choices=sorted(SPECS));p.add_argument("--id");p.add_argument("--url");p.add_argument("--property-id");p.add_argument("--body");p.add_argument("--markdown");p.add_argument("--auth-mode",choices=["internal","pat","oauth"]);p.add_argument("--page-size",type=int,default=100);p.add_argument("--start-cursor");p.add_argument("--all-pages",action="store_true");p.add_argument("--max-items",type=int,default=500);p.add_argument("--max-pages",type=int,default=5);p.add_argument("--timeout-ms",type=int,default=20000);p.add_argument("--retries",type=int,default=2);p.add_argument("--max-retry-sleep",type=float,default=.2);p.add_argument("--preview",action="store_true");p.add_argument("--confirm");p.add_argument("--base-url",default=os.environ.get("NOTION_API_BASE",DEFAULT_BASE));p.add_argument("--raw-body-b64");p.add_argument("--signature");return p

def validate(a):
 if not 1<=a.page_size<=100:raise ValueError("--page-size must be 1..100")
 if not 1<=a.max_items<=10000 or not 1<=a.max_pages<=100:raise ValueError("pagination bounds invalid")
 if not 100<=a.timeout_ms<=60000 or not 0<=a.retries<=5 or not 0<=a.max_retry_sleep<=60:raise ValueError("retry/timeout bounds invalid")
 u=urllib.parse.urlsplit(a.base_url)
 if u.scheme not in {"http","https"} or not u.netloc:raise ValueError("invalid API base URL")
 if u.scheme!="https" and u.hostname not in {"127.0.0.1","localhost","::1"}:raise ValueError("non-TLS API base is allowed only for loopback tests")

def main():
 a=parser().parse_args();cmd=a.command
 try:
  validate(a);spec=SPECS[cmd]
  if spec.method is None:out=envelope(cmd,True,local(a))
  else:
   body=parse_body(a)
   if cmd=="page.archive":body={**body,"archived":True}
   if cmd=="page.restore":body={**body,"archived":False}
   req=canonical(spec,a,body);ih=intent_hash(req)
   if spec.safety!="readOnly":
    preview={"intent_hash":ih,"request":redact(req),"safety_class":spec.safety,"expected_effects":{"target":req["path"],"operation":req["method"]},"requires_source_of_truth_verification":bool(spec.verify)}
    if a.preview:out=envelope(cmd,True,{"preview":preview})
    elif a.confirm!=ih:raise ValueError("write requires --preview, then --confirm with the exact intent_hash")
    else:out=execute(a,spec,req)
   else:out=execute(a,spec,req)
 except ApiError as e:
  mutation=SPECS.get(cmd,Spec(None,None)).safety!="readOnly"; uncertain=mutation and e.status in (409,500,502,503,504,529)
  out=envelope(cmd,False,error={"category":category(e.status,e.code),"http_status":e.status,"code":e.code,"message":str(e),"retryable":False if mutation else e.status in (409,429,500,502,503,504,529),"details":{}},effects={"performed":False,"created":[],"updated":[],"deleted":[],"unknown":uncertain},notion_request_id=e.request_id,retry={"attempts":0,"retryable":False if mutation else e.status in (409,429,500,502,503,504,529),"retry_after_seconds":e.retry_after})
 except (ValueError,RuntimeError,OSError) as e:
  mutation=SPECS.get(cmd,Spec(None,None)).safety!="readOnly";unknown=mutation and "timed out or transport" in str(e)
  out=envelope(cmd,False,error={"category":"validation" if isinstance(e,ValueError) else "transport","http_status":None,"code":"invalid_input" if isinstance(e,ValueError) else "transport_error","message":str(e),"retryable":False,"details":{}},effects={"performed":False,"created":[],"updated":[],"deleted":[],"unknown":unknown})
 print(json.dumps(redact(out),ensure_ascii=False,separators=(",",":")))
 if not out["ok"]:raise SystemExit(2)
if __name__=="__main__":main()
