#!/usr/bin/env python3
"""Offline-first guarded image provider orchestration harness."""
from __future__ import annotations
import argparse, base64, binascii, datetime as dt, hashlib, json, mimetypes, os, re, signal, struct, subprocess, sys, tempfile, time, uuid, types
import urllib.error, urllib.parse, urllib.request
from pathlib import Path
from typing import Any
sys.path.insert(0,str(Path(__file__).resolve().parent))
import professional_studio

VERSION="0.4.0"; SCHEMA="1.0"; MAX_COMPARE=4; MAX_COUNT=8; PRICE_MAX_AGE_DAYS=30
OPENAI_BASE="https://api.openai.com/v1"; HTTP_TIMEOUT=45; MAX_RESPONSE_BYTES=25*1024*1024
PROVIDERS={
 "openai":{"env":"OPENAI_API_KEY","auth":"api_key","models":["gpt-image-1"],"features":["generate","edit","mask","multi_image"]},
 "vertex":{"env":None,"auth":"adc_oauth_service_account","models":["imagen-3"],"features":["generate","edit","governance","synthid"],"requires":["project","location","iam"]},
 "bfl":{"env":"BFL_API_KEY","auth":"api_key","models":["flux-pro-1.1"],"features":["generate","edit","async","flux_control"]},
 "recraft":{"env":"RECRAFT_API_KEY","auth":"api_key","models":["recraft-v3"],"features":["generate","edit","vector","svg","design"]},
}
PRICES={"openai":{"gpt-image-1":0.04},"vertex":{"imagen-3":0.04},"bfl":{"flux-pro-1.1":0.05},"recraft":{"recraft-v3":0.04}}
COMMANDS="provider.list provider.status provider.requirements onboarding.interview connection.bind connection.status connection.verify connection.revoke request.validate request.estimate request.prepare image.generate image.edit image.compare job.start job.status job.collect artifact.inspect pricing.snapshot".split()+professional_studio.STUDIO_COMMANDS
INTERNAL_COMMANDS=["_job.worker"]
SECRET_RE=re.compile(r"(?i)(bearer\s+\S+|(?:sk|key|token|secret)[-_][A-Za-z0-9._-]{8,})")
SECRET_KEYS=re.compile(r"(?i)(api.?key|token|secret|password|authorization|credential)")

class E(Exception):
 def __init__(self,code,msg,exit_code=2,retryable=False,details=None): self.code,self.msg,self.exit_code,self.retryable,self.details=code,msg,exit_code,retryable,details or {}
def stable(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def sha(v): return "sha256:"+hashlib.sha256(v if isinstance(v,bytes) else stable(v).encode()).hexdigest()
def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00","Z")
def redact(v,key=""):
 if SECRET_KEYS.search(key) and key not in {"secretBindingDigest","bindingDigest"}: return "[REDACTED]"
 if isinstance(v,dict): return {k:redact(x,k) for k,x in v.items()}
 if isinstance(v,list): return [redact(x) for x in v]
 if isinstance(v,str): return SECRET_RE.sub("[REDACTED]",v)
 return v
def env(cmd,ok=True,data=None,error=None,effects="none"):
 out={"schemaVersion":SCHEMA,"ok":ok,"command":cmd,"requestId":str(uuid.uuid4()),"timestamp":now(),"effects":{"status":effects},"data":data or {},"warnings":[]}
 if error is not None: out["error"]=error
 return redact(out)
def fail(cmd,e):
 print(stable(env(cmd,False,error={"code":e.code,"message":e.msg,"retryable":e.retryable,"details":e.details}))); return e.exit_code

def closed(v,allowed,required=()):
 if not isinstance(v,dict): raise E("SCHEMA_VIOLATION","input must be an object")
 unknown=set(v)-set(allowed)
 if unknown: raise E("SCHEMA_VIOLATION","unknown fields",details={"fields":sorted(unknown)})
 missing=set(required)-set(v)
 if missing: raise E("SCHEMA_VIOLATION","missing fields",details={"fields":sorted(missing)})
def root(raw):
 p=Path(raw or os.getenv("CLAWPOD_IMAGE_STUDIO_STATE",str(Path.home()/".clawpod-image-studio"))).expanduser()
 if p.exists() and p.is_symlink(): raise E("PATH_VIOLATION","state root may not be a symlink")
 p.mkdir(parents=True,exist_ok=True,mode=0o700); os.chmod(p,0o700); return p.resolve()
def atomic(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True,mode=0o700); fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=".tmp-")
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,"w") as f: json.dump(obj,f,sort_keys=True); f.flush(); os.fsync(f.fileno())
  os.replace(tmp,path)
  dfd=os.open(path.parent,os.O_RDONLY); os.fsync(dfd); os.close(dfd)
 finally:
  try: os.unlink(tmp)
  except FileNotFoundError: pass
def atomic_bytes(path,data):
 path.parent.mkdir(parents=True,exist_ok=True,mode=0o700); fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=".tmp-")
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,"wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
  os.replace(tmp,path)
  dfd=os.open(path.parent,os.O_RDONLY); os.fsync(dfd); os.close(dfd)
 finally:
  try: os.unlink(tmp)
  except FileNotFoundError: pass
def readj(path,default):
 try: return json.loads(path.read_text())
 except FileNotFoundError: return default
 except Exception: raise E("STATE_INVALID","state is malformed")
def safe_output(base,raw):
 closed({"output":raw},{"output"},("output",))
 p=Path(raw)
 if p.is_absolute() or ".." in p.parts or not p.parts: raise E("PATH_VIOLATION","output must be a bounded relative path")
 q=(base/p).resolve(strict=False)
 if base!=q and base not in q.parents: raise E("PATH_VIOLATION","output escapes artifact root")
 cur=base
 for part in p.parts:
  cur/=part
  if cur.exists() and cur.is_symlink(): raise E("PATH_VIOLATION","symlink path forbidden")
 return q
def provider_for(req):
 if req.get("provider"): return req["provider"]
 fmt=req.get("format","png").lower(); purpose=req.get("purpose","").lower(); features=set(req.get("features",[]))
 if fmt=="svg" or features & {"vector","design"}: return "recraft"
 if features & {"governance","synthid"} or req.get("enterpriseGovernance"): return "vertex"
 if features & {"flux_control","photoreal"} or "photoreal" in purpose: return "bfl"
 return "openai"
def validate_request(req,operation=None):
 allowed={"operation","provider","model","prompt","count","output","format","purpose","features","options","inputs","mask","project","location","iam","enterpriseGovernance","safetyPolicy","rightsPolicy","publicationPolicy","legs","maxUsd","expiresAt","bindingDigest","preparedDigest","legDigests","aggregateDigest"}
 closed(req,allowed,("prompt","output"))
 op=operation or req.get("operation","generate")
 if op not in {"generate","edit","compare"}: raise E("SCHEMA_VIOLATION","unsupported operation")
 if not isinstance(req["prompt"],str) or not req["prompt"].strip(): raise E("SCHEMA_VIOLATION","prompt is required")
 out=Path(req["output"]) if isinstance(req["output"],str) else Path("/")
 if out.is_absolute() or ".." in out.parts or not out.parts: raise E("PATH_VIOLATION","output must be a bounded relative path")
 if not isinstance(req.get("count",1),int) or isinstance(req.get("count",1),bool) or not 1<=req.get("count",1)<=MAX_COUNT: raise E("SCHEMA_VIOLATION","count outside cap")
 for policy in ("safetyPolicy","rightsPolicy","publicationPolicy"):
  if policy not in req or not isinstance(req[policy],str) or not req[policy]: raise E("POLICY_REQUIRED",f"{policy} is separately required",exit_code=6)
 p=provider_for(req)
 if p not in PROVIDERS: raise E("SCHEMA_VIOLATION","unknown provider")
 if p=="vertex" and not all(req.get(x) for x in ("project","location","iam")): raise E("VERTEX_CONFIG_REQUIRED","Vertex project, location, and IAM lifecycle are required",exit_code=6)
 if op=="edit" and not req.get("inputs"): raise E("SCHEMA_VIOLATION","edit requires inputs")
 return {**req,"operation":op,"provider":p,"model":req.get("model") or PROVIDERS[p]["models"][0],"count":req.get("count",1),"format":req.get("format","png"),"options":req.get("options",{})}
def estimate(req):
 r=validate_request(req); unit=PRICES[r["provider"]].get(r["model"])
 if unit is None: raise E("PRICE_UNKNOWN","model has no pinned price",exit_code=6)
 return {"provider":r["provider"],"model":r["model"],"count":r["count"],"estimatedUsd":round(unit*r["count"],6),"pricingAsOf":"2026-08-01","pricingStale":False}
def conn_path(r): return r/"connections.json"
def connections(r): return readj(conn_path(r),{})
def required_binding(provider,record):
 if provider=="vertex": return sha({"provider":"vertex","auth":"adc_oauth_service_account","project":record.get("project"),"location":record.get("location"),"iam":record.get("iam")})
 return sha({"provider":provider,"environment":PROVIDERS[provider]["env"],"pointer":record.get("pointer")})
def prepare(req,r):
 v=validate_request(req); c=connections(r).get(v["provider"],{})
 if c.get("state") not in {"connected","configured_unverified"}: raise E("NOT_CONNECTED","provider binding unavailable",exit_code=5)
 binding=required_binding(v["provider"],c); est=estimate(v); maxusd=v.get("maxUsd")
 if not isinstance(maxusd,(int,float)) or isinstance(maxusd,bool) or maxusd<est["estimatedUsd"]: raise E("COST_CEILING_REQUIRED","maxUsd must cover estimate",exit_code=6)
 expires=v.get("expiresAt")
 try: expiry=dt.datetime.fromisoformat(expires.replace("Z","+00:00")) if isinstance(expires,str) else None
 except ValueError: expiry=None
 if not expiry or expiry<=dt.datetime.now(dt.timezone.utc): raise E("APPROVAL_EXPIRED","future expiry required",exit_code=6)
 intent={k:v[k] for k in sorted(v) if k not in {"preparedDigest","bindingDigest","legDigests","aggregateDigest"}}
 digest=sha({"intent":intent,"maxUsd":float(maxusd),"expiresAt":expires,"bindingDigest":binding})
 out={**intent,"estimate":est,"bindingDigest":binding,"preparedDigest":digest}
 atomic(r/"prepared"/(digest.removeprefix("sha256:")+".json"),out); return out
def assert_prepared(req,r,op):
 v=validate_request(req,op); d=req.get("preparedDigest")
 if not isinstance(d,str): raise E("APPROVAL_REQUIRED","preparedDigest required",exit_code=6)
 stored=readj(r/"prepared"/(d.removeprefix("sha256:")+".json"),None)
 if not stored: raise E("DIGEST_MISMATCH","prepared intent not found",exit_code=6)
 current=validate_request({k:v for k,v in req.items() if k not in {"preparedDigest","bindingDigest","legDigests","aggregateDigest"}},op)
 expected={k:v for k,v in stored.items() if k not in {"estimate","bindingDigest","preparedDigest"}}
 if stable(current)!=stable(expected) or req.get("bindingDigest")!=stored["bindingDigest"]: raise E("DIGEST_MISMATCH","intent, cost, expiry, or secret binding changed",exit_code=6)
 if required_binding(stored["provider"],connections(r).get(stored["provider"],{}))!=stored["bindingDigest"]: raise E("DIGEST_MISMATCH","current secret binding changed",exit_code=6)
 try: expiry=dt.datetime.fromisoformat(stored["expiresAt"].replace("Z","+00:00"))
 except (KeyError,ValueError,AttributeError): raise E("APPROVAL_EXPIRED","prepared expiry is invalid",exit_code=6)
 if expiry<=dt.datetime.now(dt.timezone.utc): raise E("APPROVAL_EXPIRED","prepared approval expired",exit_code=6)
 if float(stored["maxUsd"])<float(stored["estimate"]["estimatedUsd"]): raise E("COST_CEILING_REQUIRED","prepared cost ceiling no longer covers estimate",exit_code=6)
 return stored

def _api_key():
 key=os.getenv("OPENAI_API_KEY")
 if not key: raise E("CREDENTIAL_UNAVAILABLE","OPENAI_API_KEY was not injected at runtime",exit_code=5)
 return key
def _read_limited(response,limit=MAX_RESPONSE_BYTES):
 data=response.read(limit+1)
 if len(data)>limit: raise E("PROVIDER_RESPONSE_INVALID","provider response exceeded size limit",exit_code=8)
 return data
def _open(request,timeout=HTTP_TIMEOUT): return urllib.request.urlopen(request,timeout=timeout)
def _http_error(err,paid):
 status=getattr(err,"code",None)
 if status in (401,403): return E("PROVIDER_AUTH_FAILED","OpenAI rejected the protected credential",exit_code=5,details={"httpStatus":status,"billingState":"not_accepted"})
 if status==429: return E("PROVIDER_RATE_LIMITED","OpenAI rate limited the request before acceptance",exit_code=8,retryable=not paid,details={"httpStatus":429,"billingState":"not_accepted" if paid else "not_applicable","automaticRetry":False})
 if status and 400<=status<500: return E("PROVIDER_REJECTED","OpenAI rejected the request before a successful response",exit_code=8,retryable=False,details={"httpStatus":status,"billingState":"not_accepted","automaticRetry":False})
 return E("BILLING_AMBIGUOUS" if paid else "PROVIDER_UNAVAILABLE","OpenAI response was ambiguous; do not automatically retry the paid request" if paid else "OpenAI verification unavailable",exit_code=10 if paid else 8,retryable=False if paid else True,details={"httpStatus":status,"billingState":"unknown" if paid else "not_applicable","automaticRetry":False})
def openai_verify(opener=_open):
 req=urllib.request.Request(OPENAI_BASE+"/models/gpt-image-1",headers={"Authorization":"Bearer "+_api_key(),"Accept":"application/json"})
 try:
  with opener(req,HTTP_TIMEOUT) as response: doc=json.loads(_read_limited(response,1024*1024))
 except urllib.error.HTTPError as e: raise _http_error(e,False)
 except (TimeoutError,urllib.error.URLError,OSError): raise E("PROVIDER_UNAVAILABLE","OpenAI non-billable model-readiness check unavailable",8,True)
 except (json.JSONDecodeError,UnicodeDecodeError): raise E("PROVIDER_RESPONSE_INVALID","OpenAI readiness response was malformed",8)
 if not isinstance(doc,dict) or doc.get("id")!="gpt-image-1": raise E("PROVIDER_RESPONSE_INVALID","OpenAI readiness response did not confirm gpt-image-1",8)
 return {"verified":True,"method":"GET /v1/models/gpt-image-1","billingAttempted":False}
def _decode_openai_item(item,opener):
 if not isinstance(item,dict): raise E("PROVIDER_RESPONSE_INVALID","OpenAI image item was malformed",8,details={"billingState":"accepted"})
 if isinstance(item.get("b64_json"),str):
  try: return base64.b64decode(item["b64_json"],validate=True)
  except (binascii.Error,ValueError): raise E("PROVIDER_RESPONSE_INVALID","OpenAI returned invalid base64 image data",8,details={"billingState":"accepted"})
 url=item.get("url")
 if isinstance(url,str):
  parsed=urllib.parse.urlparse(url)
  if parsed.scheme!="https" or not parsed.hostname: raise E("PROVIDER_RESPONSE_INVALID","OpenAI returned an unsafe image URL",8,details={"billingState":"accepted"})
  try:
   with opener(urllib.request.Request(url,headers={"Accept":"image/*"}),HTTP_TIMEOUT) as response: return _read_limited(response)
  except Exception: raise E("BILLING_AMBIGUOUS","image generation succeeded but result download was not confirmed; do not resubmit",10,False,{"billingState":"accepted_output_unavailable","automaticRetry":False})
 raise E("PROVIDER_RESPONSE_INVALID","OpenAI response contained neither b64_json nor URL",8,details={"billingState":"accepted"})
def openai_generate(payload,opener=_open):
 if payload.get("operation")!="generate": raise E("PROVIDER_OPERATION_UNSUPPORTED","live OpenAI transport currently supports generation only",6)
 options=payload.get("options") or {}; allowed={"size","quality","background","output_format","output_compression","moderation"}
 if not isinstance(options,dict): raise E("SCHEMA_VIOLATION","options must be an object")
 unknown=set(options)-allowed
 if unknown: raise E("SCHEMA_VIOLATION","unsupported OpenAI options",details={"fields":sorted(unknown)})
 body={**options,"model":payload["model"],"prompt":payload["prompt"],"n":payload["count"]}
 req=urllib.request.Request(OPENAI_BASE+"/images/generations",data=stable(body).encode(),method="POST",headers={"Authorization":"Bearer "+_api_key(),"Content-Type":"application/json","Accept":"application/json"})
 try:
  with opener(req,HTTP_TIMEOUT) as response: raw=_read_limited(response)
 except urllib.error.HTTPError as e: raise _http_error(e,True)
 except (TimeoutError,urllib.error.URLError,OSError): raise E("BILLING_AMBIGUOUS","OpenAI submission outcome is unknown; do not automatically retry",10,False,{"billingState":"unknown","automaticRetry":False})
 try: doc=json.loads(raw)
 except (json.JSONDecodeError,UnicodeDecodeError): raise E("PROVIDER_RESPONSE_INVALID","OpenAI returned malformed JSON after accepting the request",8,False,{"billingState":"unknown","automaticRetry":False})
 data=doc.get("data") if isinstance(doc,dict) else None
 if not isinstance(data,list) or len(data)!=payload["count"]: raise E("PROVIDER_RESPONSE_INVALID","OpenAI returned an unexpected image count",8,False,{"billingState":"unknown","automaticRetry":False})
 return {"items":[_decode_openai_item(item,opener) for item in data],"providerRequestId":doc.get("id"),"revisedPrompts":[item.get("revised_prompt") for item in data if isinstance(item,dict) and item.get("revised_prompt")]}
def transport(provider,payload,opener=_open):
 mode=os.getenv("CLAWPOD_IMAGE_STUDIO_TRANSPORT","openai-live" if provider=="openai" and os.getenv("OPENAI_API_KEY") else "disabled")
 if mode=="disabled": raise E("NETWORK_DISABLED","live provider transport is disabled by default",exit_code=8)
 if mode=="mock-outage": raise E("PROVIDER_OUTAGE","provider unavailable",exit_code=8,retryable=True)
 if mode=="mock-ambiguous": raise E("BILLING_AMBIGUOUS","provider response was ambiguous; do not automatically retry paid operation",exit_code=10,retryable=False,details={"billingState":"unknown","automaticRetry":False})
 if mode=="openai-live":
  if provider!="openai": raise E("NETWORK_DISABLED","live transport is enabled only for OpenAI Images",8)
  return openai_generate(payload,opener)
 if mode!="mock-success": raise E("NETWORK_DISABLED","unsupported transport mode",exit_code=8)
 png=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"+struct.pack(">II",1,1)+b"\x08\x06\x00\x00\x00"
 return {"items":[b"<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16'><rect width='16' height='16'/></svg>" if payload["format"]=="svg" else png],"providerRequestId":"mock-"+sha(payload)[7:19],"revisedPrompts":[]}
def inspect_artifact(path):
 b=path.read_bytes(); mime="application/octet-stream"; dimensions=None
 if b.startswith(b"\x89PNG\r\n\x1a\n") and len(b)>=24: mime="image/png"; dimensions={"width":struct.unpack(">I",b[16:20])[0],"height":struct.unpack(">I",b[20:24])[0]}
 elif b.startswith((b"\xff\xd8\xff",)): mime="image/jpeg"
 elif b.startswith((b"RIFF",)) and b[8:12]==b"WEBP": mime="image/webp"
 elif b.lstrip().startswith(b"<svg"): mime="image/svg+xml"
 qa={"nonEmpty":bool(b),"decoded":mime.startswith("image/") and bool(b),"svgParsed":None}
 if mime=="image/svg+xml":
  import xml.etree.ElementTree as ET
  try:
   root=ET.fromstring(b); qa["svgParsed"]=root.tag.endswith("svg")
   def num(name):
    m=re.match(r"([0-9]+(?:\.[0-9]+)?)",root.attrib.get(name,"")); return int(float(m.group(1))) if m else None
   w,h=num("width"),num("height"); dimensions={"width":w,"height":h} if w and h else None
  except ET.ParseError: qa["svgParsed"]=False
 if not qa["decoded"]: raise E("ARTIFACT_INVALID","provider output is not a recognized image",8,False,{"billingState":"accepted"})
 return {"path":str(path),"bytes":len(b),"sha256":sha(b),"mimeType":mime,"dimensions":dimensions,"qa":qa,"provenance":{"harness":"clawpod-image-studio","version":VERSION}}
def run_image(req,r,op):
 prepared=assert_prepared(req,r,op); p=safe_output(r/"artifacts",prepared["output"]); p.parent.mkdir(parents=True,exist_ok=True)
 result=transport(prepared["provider"],prepared)
 artifacts=[]
 for i,b in enumerate(result["items"]):
  target=p if len(result["items"])==1 else p.with_name(f"{p.stem}-{i+1}{p.suffix}")
  target=safe_output(r/"artifacts",str(target.relative_to(r/"artifacts"))); atomic_bytes(target,b); artifacts.append(inspect_artifact(target))
 for art in artifacts: art["provenance"].update({"provider":prepared["provider"],"model":prepared["model"],"operation":prepared["operation"],"preparedDigest":prepared["preparedDigest"],"providerRequestId":result.get("providerRequestId")})
 return {"state":"succeeded","provider":prepared["provider"],"providerRequestId":result.get("providerRequestId"),"artifact":artifacts[0] if len(artifacts)==1 else None,"artifacts":artifacts,"revisedPrompts":result.get("revisedPrompts",[]),"estimatedUsd":prepared["estimate"]["estimatedUsd"],"actualUsd":None,"costReconciliation":"provider response did not include a final billed amount","billingState":"accepted","automaticRetry":False}

# OpenAI's image endpoint is synchronous. These helpers wrap exactly one paid
# submission in a detached, durable local worker; they never retry it.
JOB_ID_RE=re.compile(r"job_[0-9a-f]{32}")
JOB_TERMINAL={"succeeded","failed","ambiguous","cancelled"}
JOB_RESERVE_SECONDS=10
def _job_dir(r,job_id):
 if not isinstance(job_id,str) or not JOB_ID_RE.fullmatch(job_id): raise E("INVALID_JOB_ID","jobId is invalid")
 return r/"jobs"/job_id
def _job_read(r,job_id):
 p=_job_dir(r,job_id)/"state.json"
 if not p.is_file() or p.is_symlink(): raise E("JOB_NOT_FOUND","job does not exist",3)
 return readj(p,None)
def _pid_start(pid):
 try:
  fields=Path(f"/proc/{pid}/stat").read_text().rsplit(")",1)[1].split()
  return None if fields[0]=="Z" else int(fields[19])
 except (OSError,ValueError,IndexError):
  try:
   value=subprocess.check_output(["ps","-o","lstart=","-p",str(pid)],text=True,stderr=subprocess.DEVNULL,timeout=1).strip()
   return value or None
  except (OSError,subprocess.SubprocessError): return None
def _pid_alive(identity):
 return isinstance(identity,dict) and _pid_start(identity.get("pid"))==identity.get("startTime")
def _job_write(jd,current,**changes):
 nxt={**current,**changes,"updatedAt":now(),"revision":int(current.get("revision",0))+1}
 atomic(jd/"state.json",nxt); return nxt
def _safe_job_error(code,message,details=None):
 return {"code":code,"message":message,"retryable":False,"details":details or {}}
def _job_recover(r,state):
 if state.get("state") in JOB_TERMINAL: return state
 jd=_job_dir(r,state["jobId"]); deadline=dt.datetime.fromisoformat(state["deadlineAt"].replace("Z","+00:00"))
 overdue=dt.datetime.now(dt.timezone.utc)>deadline+dt.timedelta(seconds=5)
 alive=_pid_alive(state.get("pidIdentity"))
 if alive and not overdue: return state
 if alive and overdue:
  ident=state["pidIdentity"]
  try:
   if os.getpgid(ident["pid"])==ident.get("pgid")==ident["pid"]: os.killpg(ident["pgid"],signal.SIGTERM)
  except (ProcessLookupError,PermissionError,OSError): pass
  time.sleep(.05)
  if _pid_alive(ident):
   try:
    if os.getpgid(ident["pid"])==ident.get("pgid")==ident["pid"]: os.killpg(ident["pgid"],signal.SIGKILL)
   except (ProcessLookupError,PermissionError,OSError): pass
 phase=state.get("phase","bootstrap")
 if phase in {"bootstrap","preflight"}:
  return _job_write(jd,state,state="failed",billingState="not_submitted",error=_safe_job_error("WORKER_EXITED","worker ended before provider submission"))
 billing="accepted_output_unavailable" if phase in {"provider_response","artifact_commit"} else "unknown"
 terminal="failed" if billing.startswith("accepted") else "ambiguous"
 return _job_write(jd,state,state=terminal,billingState=billing,error=_safe_job_error("WORKER_EXITED","worker ended after the paid submission boundary"))
def _job_public(state):
 keys=("jobId","state","phase","billingState","automaticRetry","createdAt","updatedAt","deadlineAt","providerRequestId","revision")
 out={k:state[k] for k in keys if k in state}; out["terminal"]=state.get("state") in JOB_TERMINAL
 if state.get("error"): out["error"]=state["error"]
 return out
def job_start(req,r):
 allowed={"operation","provider","model","prompt","count","output","format","options","safetyPolicy","rightsPolicy","publicationPolicy","maxUsd","expiresAt","bindingDigest","preparedDigest","timeoutSeconds"}
 closed(req,allowed,("operation","provider","model","prompt","output","safetyPolicy","rightsPolicy","publicationPolicy","maxUsd","expiresAt","bindingDigest","preparedDigest"))
 timeout=req.get("timeoutSeconds",300)
 if not isinstance(timeout,int) or isinstance(timeout,bool) or not 60<=timeout<=300: raise E("SCHEMA_VIOLATION","timeoutSeconds must be an integer from 60 through 300")
 approved={k:v for k,v in req.items() if k!="timeoutSeconds"}; prepared=assert_prepared(approved,r,"generate")
 if prepared["provider"]!="openai" or prepared["operation"]!="generate": raise E("PROVIDER_OPERATION_UNSUPPORTED","detached jobs support OpenAI generation only",6)
 _api_key() # protected environment only; never copied into durable state or argv
 for jd in (r/"jobs").glob("job_*") if (r/"jobs").exists() else ():
  try: old=readj(jd/"state.json",None)
  except E: continue
  if old and old.get("preparedDigest")==prepared["preparedDigest"]:
   raise E("PAID_JOB_EXISTS","a job already exists for this approved paid intent",6,False,{"jobId":old["jobId"],"state":old["state"]})
 job_id="job_"+uuid.uuid4().hex; jd=_job_dir(r,job_id); jd.mkdir(parents=True,mode=0o700); os.chmod(jd,0o700)
 created=now(); deadline=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=timeout)).isoformat().replace("+00:00","Z")
 request_doc={"schemaVersion":1,"jobId":job_id,"approved":approved,"timeoutSeconds":timeout}
 state={"schemaVersion":1,"jobId":job_id,"provider":"openai","operation":"generate","preparedDigest":prepared["preparedDigest"],"bindingDigest":prepared["bindingDigest"],"state":"queued","phase":"bootstrap","billingState":"not_submitted","automaticRetry":False,"createdAt":created,"updatedAt":created,"deadlineAt":deadline,"pidIdentity":None,"providerRequestId":None,"artifactPaths":[],"error":None,"revision":1}
 atomic(jd/"request.json",request_doc); atomic(jd/"state.json",state)
 argv=[sys.executable,str(Path(__file__).resolve()),"_job.worker","--root",str(r),"--input-json",stable({"jobId":job_id})]
 try:
  with open(os.devnull,"rb") as inp, open(os.devnull,"ab") as out:
   child=subprocess.Popen(argv,stdin=inp,stdout=out,stderr=out,start_new_session=True,close_fds=True,env=os.environ.copy())
  ident={"pid":child.pid,"pgid":child.pid,"startTime":None}
  end=time.monotonic()+5
  while ident["startTime"] is None and time.monotonic()<end:
   ident["startTime"]=_pid_start(child.pid)
   if child.poll() is not None: break
   time.sleep(.01)
  if ident["startTime"] is None: raise OSError("worker bootstrap failed")
  state=_job_write(jd,_job_read(r,job_id),pidIdentity=ident)
  atomic(jd/"worker.pid",ident)
 except (OSError,subprocess.SubprocessError):
  _job_write(jd,state,state="failed",billingState="not_submitted",error=_safe_job_error("WORKER_BOOTSTRAP_FAILED","detached worker could not start"))
  raise E("WORKER_BOOTSTRAP_FAILED","detached worker could not start",8)
 return {"jobId":job_id,"state":"queued","billingState":"not_submitted","automaticRetry":False,"statusCommand":"job.status","collectCommand":"job.collect"}
def _detached_openai_generate(payload,timeout,opener=_open):
 options=payload.get("options") or {}; allowed={"size","quality","background","output_format","output_compression","moderation"}
 if not isinstance(options,dict) or set(options)-allowed: raise E("SCHEMA_VIOLATION","unsupported OpenAI options")
 body={**options,"model":payload["model"],"prompt":payload["prompt"],"n":payload["count"]}; transport_deadline=time.monotonic()+timeout
 def bounded_open(request,_timeout=None): return opener(request,max(1,transport_deadline-time.monotonic()))
 key=_api_key(); req=urllib.request.Request(OPENAI_BASE+"/images/generations",data=stable(body).encode(),method="POST",headers={"Authorization":"Bearer "+key,"Content-Type":"application/json","Accept":"application/json"}); del key; os.environ.pop("OPENAI_API_KEY",None)
 try:
  with bounded_open(req) as response: raw=_read_limited(response)
 except urllib.error.HTTPError as e: raise _http_error(e,True)
 except (TimeoutError,urllib.error.URLError,OSError): raise E("BILLING_AMBIGUOUS","OpenAI submission outcome is unknown; do not automatically retry",10,False,{"billingState":"unknown","automaticRetry":False})
 try: doc=json.loads(raw)
 except (json.JSONDecodeError,UnicodeDecodeError): raise E("PROVIDER_RESPONSE_INVALID","OpenAI success response was malformed; do not automatically retry",10,False,{"billingState":"accepted_output_unavailable","automaticRetry":False})
 data=doc.get("data") if isinstance(doc,dict) else None
 if not isinstance(data,list) or len(data)!=payload["count"]: raise E("PROVIDER_RESPONSE_INVALID","OpenAI returned an unexpected image count; do not automatically retry",10,False,{"billingState":"accepted_output_unavailable","automaticRetry":False})
 return {"items":[_decode_openai_item(item,bounded_open) for item in data],"providerRequestId":doc.get("id"),"revisedPrompts":[item.get("revised_prompt") for item in data if isinstance(item,dict) and item.get("revised_prompt")]}
def job_worker(r,job_id):
 jd=_job_dir(r,job_id); state=_job_read(r,job_id); request_doc=readj(jd/"request.json",None)
 if not request_doc: _job_write(jd,state,state="failed",billingState="not_submitted",error=_safe_job_error("REQUEST_INVALID","durable request is unavailable")); return {}
 def term(_sig,_frame):
  s=_job_read(r,job_id); before=s.get("phase") in {"bootstrap","preflight"}; _job_write(jd,s,state="failed" if before else "ambiguous",billingState="not_submitted" if before else "unknown",error=_safe_job_error("WORKER_TERMINATED","worker was terminated")); raise SystemExit(143)
 signal.signal(signal.SIGTERM,term); approved=request_doc["approved"]
 try:
  state=_job_write(jd,state,state="running",phase="preflight")
  prepared=assert_prepared(approved,r,"generate"); _api_key()
  remaining=(dt.datetime.fromisoformat(state["deadlineAt"].replace("Z","+00:00"))-dt.datetime.now(dt.timezone.utc)).total_seconds()-JOB_RESERVE_SECONDS
  if remaining<=0: raise E("JOB_TIMEOUT","deadline expired before provider submission",8)
  state=_job_write(jd,state,phase="provider_request",billingState="unknown")
  mode=os.getenv("CLAWPOD_IMAGE_STUDIO_TRANSPORT","openai-live")
  if mode=="mock-success": result=transport("openai",prepared)
  elif mode=="mock-timeout": time.sleep(float(os.getenv("CLAWPOD_IMAGE_STUDIO_MOCK_DELAY","61"))); raise TimeoutError()
  elif mode=="mock-crash": os._exit(91)
  elif mode=="openai-live": result=_detached_openai_generate(prepared,max(1,remaining))
  else: raise E("NETWORK_DISABLED","unsupported detached transport mode",8)
  state=_job_write(jd,state,phase="provider_response",billingState="accepted",providerRequestId=result.get("providerRequestId"))
  p=safe_output(r/"artifacts",prepared["output"]); artifacts=[]; state=_job_write(jd,state,phase="artifact_commit")
  for i,b in enumerate(result["items"]):
   target=p if len(result["items"])==1 else p.with_name(f"{p.stem}-{i+1}{p.suffix}"); target=safe_output(r/"artifacts",str(target.relative_to(r/"artifacts"))); atomic_bytes(target,b); art=inspect_artifact(target); art["provenance"].update({"provider":"openai","model":prepared["model"],"operation":"generate","preparedDigest":prepared["preparedDigest"],"providerRequestId":result.get("providerRequestId")}); artifacts.append(art)
  result_doc={"artifacts":artifacts,"revisedPrompts":result.get("revisedPrompts",[]),"estimatedUsd":prepared["estimate"]["estimatedUsd"],"actualUsd":None,"costReconciliation":"provider response did not include a final billed amount"}; atomic(jd/"result.json",result_doc)
  _job_write(jd,state,state="succeeded",billingState="accepted",artifactPaths=[a["path"] for a in artifacts]); return {}
 except E as e:
  state=_job_read(r,job_id); billing=e.details.get("billingState") or ("not_submitted" if state.get("phase") in {"bootstrap","preflight"} else "unknown")
  ambiguous=billing=="unknown" and state.get("phase") not in {"bootstrap","preflight"}
  _job_write(jd,state,state="ambiguous" if ambiguous else "failed",billingState=billing,error=_safe_job_error(e.code,e.msg,{k:v for k,v in e.details.items() if k in {"httpStatus","billingState","automaticRetry"}})); return {}
 except (TimeoutError,urllib.error.URLError,OSError):
  state=_job_read(r,job_id); _job_write(jd,state,state="ambiguous",billingState="unknown",error=_safe_job_error("BILLING_AMBIGUOUS","submission outcome is unknown; do not automatically retry")); return {}
def job_status(r,job_id): return _job_public(_job_recover(r,_job_read(r,job_id)))
def job_collect(r,job_id):
 state=_job_recover(r,_job_read(r,job_id))
 if state["state"] not in JOB_TERMINAL: raise E("JOB_NOT_READY","job is not terminal; poll this same job",4,True,{"jobId":job_id,"state":state["state"],"automaticRetry":False})
 if state["state"]!="succeeded": return _job_public(state)
 doc=readj(_job_dir(r,job_id)/"result.json",None)
 if not doc: raise E("ARTIFACT_INVALID","terminal result metadata is missing",8)
 checked=[]
 for expected in doc.get("artifacts",[]):
  path=Path(expected.get("path","")); base=(r/"artifacts").resolve()
  try: rel=path.resolve(strict=False).relative_to(base); bounded=safe_output(base,str(rel))
  except (ValueError,E): raise E("ARTIFACT_INVALID","artifact path is invalid",8)
  if not bounded.is_file() or bounded.is_symlink(): raise E("ARTIFACT_INVALID","artifact is missing",8)
  actual=inspect_artifact(bounded)
  if actual["sha256"]!=expected.get("sha256"): raise E("ARTIFACT_INVALID","artifact hash changed",8)
  checked.append(expected)
 return {"state":"succeeded","provider":"openai","providerRequestId":state.get("providerRequestId"),"artifact":checked[0] if len(checked)==1 else None,"artifacts":checked,"revisedPrompts":doc.get("revisedPrompts",[]),"estimatedUsd":doc.get("estimatedUsd"),"actualUsd":doc.get("actualUsd"),"costReconciliation":doc.get("costReconciliation"),"billingState":"accepted","automaticRetry":False}
def execute(cmd,x,r):
 if cmd in professional_studio.STUDIO_COMMANDS: return professional_studio.execute(types.SimpleNamespace(**globals()),cmd,x,r)
 if cmd=="provider.list": return {"items":[{"id":p,**v} for p,v in PROVIDERS.items()],"networkDefault":"disabled"}
 if cmd=="provider.requirements":
  closed(x,{"provider"},("provider",)); p=x["provider"]
  if p not in PROVIDERS: raise E("SCHEMA_VIOLATION","unknown provider")
  return {"provider":p,**PROVIDERS[p],"secretBinding":{"parameter":"secretRefs","prepareRunMustMatch":True,"manifestStoresPointer":False},"liveReady":False}
 if cmd in {"provider.status","connection.status"}:
  closed(x,{"provider"}); cs=connections(r); items=[]
  for p in ([x["provider"]] if x.get("provider") else PROVIDERS):
   rec=cs.get(p,{"state":"deferred"}); items.append({"provider":p,"state":rec.get("state","deferred"),"liveReady":rec.get("state")=="connected","verification":rec.get("verification")})
  return {"items":items}
 if cmd=="onboarding.interview":
  closed(x,{"intendedUse","providers","models","budgetUsd","dataConstraints","project","location","iam","safetyPolicy","rightsPolicy","publicationPolicy"})
  questions=["intended use","providers/models","budget ceiling","data constraints","Vertex project/location/IAM","safety policy","rights policy","publication policy"]
  missing=[q for q,k in zip(questions,["intendedUse","providers","budgetUsd","dataConstraints","project","safetyPolicy","rightsPolicy","publicationPolicy"]) if k not in x]
  return {"complete":not missing,"missing":missing,"states":["connected","configured_unverified","deferred","revoked"],"next":"bind protected owner-scoped credentials only after explicit approval","vertexAuth":"ADC/OAuth/service account lifecycle, never API-key substitution"}
 if cmd=="connection.bind":
  closed(x,{"provider","pointer","project","location","iam","defer"},("provider",)); p=x["provider"]
  if p not in PROVIDERS: raise E("SCHEMA_VIOLATION","unknown provider")
  cs=connections(r)
  if x.get("defer"): rec={"state":"deferred"}
  elif p=="vertex":
   if "pointer" in x: raise E("SCHEMA_VIOLATION","Vertex does not accept an API-key pointer")
   if not all(x.get(k) for k in ("project","location","iam")): raise E("VERTEX_CONFIG_REQUIRED","project, location, IAM required")
   rec={"state":"configured_unverified","project":x["project"],"location":x["location"],"iam":x["iam"]}
  else:
   ptr=x.get("pointer")
   if not isinstance(ptr,str) or not re.fullmatch(r"(?:msp_|secret:)[A-Za-z0-9:_-]{6,}",ptr): raise E("POINTER_REQUIRED","safe pointer metadata required; plaintext is forbidden")
   if SECRET_RE.search(ptr): raise E("PLAINTEXT_SECRET_FORBIDDEN","plaintext secret forbidden")
   rec={"state":"configured_unverified","pointer":ptr}
  cs[p]=rec; atomic(conn_path(r),cs); return {"provider":p,"state":rec["state"],"bindingDigest":required_binding(p,rec) if rec["state"]=="configured_unverified" else None}
 if cmd=="connection.verify":
  closed(x,{"provider","nonBillable"},("provider",)); p=x["provider"]; cs=connections(r); rec=cs.get(p)
  if not rec or rec.get("state") not in {"configured_unverified","connected"}: raise E("NOT_CONNECTED","binding unavailable",5)
  if x.get("nonBillable") is not True: raise E("NONBILLABLE_REQUIRED","verification must be explicitly non-billable",6)
  mode=os.getenv("CLAWPOD_IMAGE_STUDIO_VERIFY","openai-live" if p=="openai" and os.getenv("OPENAI_API_KEY") else "disabled")
  if mode=="disabled": return {"provider":p,"state":"configured_unverified","verified":False,"billingAttempted":False,"reason":"non-billable verification transport disabled"}
  if mode=="mock-outage": raise E("PROVIDER_OUTAGE","verification unavailable",8,True)
  if mode=="openai-live":
   if p!="openai": return {"provider":p,"state":"configured_unverified","verified":False,"billingAttempted":False,"reason":"no documented non-billable verifier implemented for this provider"}
   verification=openai_verify()
  elif mode=="mock-success": verification={"billingAttempted":False,"method":"mock"}
  else: raise E("NETWORK_DISABLED","unsupported verifier",8)
  rec["state"]="connected"; rec["verification"]={"at":now(),**verification}; cs[p]=rec; atomic(conn_path(r),cs); return {"provider":p,"state":"connected","verified":True,**verification}
 if cmd=="connection.revoke":
  closed(x,{"provider","confirm"},("provider","confirm"));
  if x["confirm"]!="revoke-binding": raise E("CONFIRMATION_REQUIRED","confirm revoke-binding",6)
  cs=connections(r); cs[x["provider"]]={"state":"revoked"}; atomic(conn_path(r),cs); return {"provider":x["provider"],"state":"revoked"}
 if cmd=="request.validate": return {"valid":True,"request":validate_request(x),"routeReason":"explicit" if x.get("provider") else "capability routing"}
 if cmd=="request.estimate": return estimate(x)
 if cmd=="pricing.snapshot":
  closed(x,{"asOf"}); asof=x.get("asOf","2026-08-01")
  try: age=(dt.date.today()-dt.date.fromisoformat(asof)).days
  except ValueError: raise E("SCHEMA_VIOLATION","asOf must be ISO date")
  return {"asOf":asof,"prices":PRICES,"ageDays":age,"stale":age>PRICE_MAX_AGE_DAYS,"maxAgeDays":PRICE_MAX_AGE_DAYS}
 if cmd=="request.prepare":
  if x.get("operation")=="compare" or x.get("legs"):
   closed(x,{"operation","prompt","output","count","format","purpose","features","options","inputs","mask","safetyPolicy","rightsPolicy","publicationPolicy","legs","maxUsd","expiresAt"},("prompt","output","legs","maxUsd","expiresAt","safetyPolicy","rightsPolicy","publicationPolicy"))
   legs=x["legs"]
   if not isinstance(legs,list) or not 2<=len(legs)<=MAX_COMPARE: raise E("COMPARE_CAP","compare requires 2-4 legs")
   prepared=[]; total=0.0
   for i,leg in enumerate(legs):
    if not isinstance(leg,dict): raise E("SCHEMA_VIOLATION","leg must be object")
    merged={k:v for k,v in x.items() if k not in {"legs","maxUsd"}}; merged.update(leg); merged["operation"]="generate"; merged["output"]=f"compare/{i}-"+Path(x["output"]).name
    e=estimate(merged); total+=e["estimatedUsd"]; merged["maxUsd"]=e["estimatedUsd"]; prepared.append(prepare(merged,r))
   if total>float(x["maxUsd"]): raise E("COST_CEILING_REQUIRED","aggregate compare estimate exceeds maxUsd",6,details={"estimatedUsd":total})
   legdig=[p["preparedDigest"] for p in prepared]; agg=sha({"legs":legdig,"maxUsd":float(x["maxUsd"]),"expiresAt":x["expiresAt"]})
   doc={"operation":"compare","legs":prepared,"legDigests":legdig,"aggregateDigest":agg,"estimatedUsd":total,"maxUsd":float(x["maxUsd"]),"expiresAt":x["expiresAt"]}; atomic(r/"compare"/(agg[7:]+".json"),doc); return doc
  return prepare(x,r)
 if cmd in {"image.generate","image.edit"}: return run_image(x,r,"generate" if cmd.endswith("generate") else "edit")
 if cmd=="image.compare":
  closed(x,{"aggregateDigest","legDigests","bindingDigests"},("aggregateDigest","legDigests","bindingDigests")); doc=readj(r/"compare"/(x["aggregateDigest"].removeprefix("sha256:")+".json"),None)
  if not doc or x["legDigests"]!=doc["legDigests"] or len(x["bindingDigests"])!=len(doc["legs"]): raise E("DIGEST_MISMATCH","compare aggregate or legs changed",6)
  results=[]
  for i,leg in enumerate(doc["legs"]):
   payload={k:v for k,v in leg.items() if k not in {"estimate"}}; payload["preparedDigest"]=leg["preparedDigest"]; payload["bindingDigest"]=x["bindingDigests"][i]
   try: results.append({"ok":True,"data":run_image(payload,r,"generate")})
   except E as e: results.append({"ok":False,"error":{"code":e.code,"retryable":e.retryable}})
  ok=sum(1 for z in results if z["ok"]); return {"state":"succeeded" if ok==len(results) else "partial" if ok else "failed","completed":ok,"failed":len(results)-ok,"results":results,"automaticPaidRetry":False}
 if cmd=="job.start": return job_start(x,r)
 if cmd=="job.status":
  closed(x,{"jobId"},("jobId",)); return job_status(r,x["jobId"])
 if cmd=="job.collect":
  closed(x,{"jobId"},("jobId",)); return job_collect(r,x["jobId"])
 if cmd=="_job.worker":
  closed(x,{"jobId"},("jobId",)); return job_worker(r,x["jobId"])
 if cmd=="artifact.inspect":
  closed(x,{"path"},("path",)); p=safe_output(r/"artifacts",x["path"])
  if not p.is_file() or p.is_symlink(): raise E("NOT_FOUND","artifact unavailable",3)
  return inspect_artifact(p)
 raise E("INVALID_COMMAND","unknown command")

class Parser(argparse.ArgumentParser):
 def error(self,msg): raise E("INVALID_ARGUMENT",msg)
def main(argv=None):
 cmd="unknown"
 try:
  p=Parser(); p.add_argument("command",choices=COMMANDS+INTERNAL_COMMANDS); p.add_argument("--input-json",default="{}"); p.add_argument("--root")
  a=p.parse_args(argv); cmd=a.command
  try: x=json.loads(a.input_json)
  except json.JSONDecodeError: raise E("INVALID_ARGUMENT","input-json must be valid JSON")
  if not isinstance(x,dict): raise E("SCHEMA_VIOLATION","input must be object")
  data=execute(cmd,x,root(a.root)); local_write=cmd in professional_studio.STUDIO_COMMANDS and cmd not in {"project.get","project.list","shot.list","audit.verify"}; print(stable(env(cmd,True,data=data,effects="artifact_written" if cmd.startswith("image.") or cmd in {"contact_sheet.create","delivery.package"} else "state_updated" if cmd.startswith("connection.") or local_write else "none"))); return 0
 except E as e: return fail(cmd,e)
if __name__=="__main__": raise SystemExit(main())
