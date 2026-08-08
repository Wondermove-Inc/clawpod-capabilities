#!/usr/bin/env python3
"""Offline-first guarded image provider orchestration harness."""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, mimetypes, os, re, stat, sys, tempfile, uuid
from pathlib import Path
from typing import Any

VERSION="0.1.0"; SCHEMA="1.0"; MAX_COMPARE=4; MAX_COUNT=8; PRICE_MAX_AGE_DAYS=30
PROVIDERS={
 "openai":{"env":"OPENAI_API_KEY","auth":"api_key","models":["gpt-image-1"],"features":["generate","edit","mask","multi_image"]},
 "vertex":{"env":None,"auth":"adc_oauth_service_account","models":["imagen-3"],"features":["generate","edit","governance","synthid"],"requires":["project","location","iam"]},
 "bfl":{"env":"BFL_API_KEY","auth":"api_key","models":["flux-pro-1.1"],"features":["generate","edit","async","flux_control"]},
 "recraft":{"env":"RECRAFT_API_KEY","auth":"api_key","models":["recraft-v3"],"features":["generate","edit","vector","svg","design"]},
}
PRICES={"openai":{"gpt-image-1":0.04},"vertex":{"imagen-3":0.04},"bfl":{"flux-pro-1.1":0.05},"recraft":{"recraft-v3":0.04}}
COMMANDS="provider.list provider.status provider.requirements onboarding.interview connection.bind connection.status connection.verify connection.revoke request.validate request.estimate request.prepare image.generate image.edit image.compare job.status job.collect artifact.inspect pricing.snapshot".split()
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
 check=prepare({k:v for k,v in req.items() if k not in {"preparedDigest","bindingDigest","legDigests","aggregateDigest"}},r)
 if check["preparedDigest"]!=d or req.get("bindingDigest")!=stored["bindingDigest"]: raise E("DIGEST_MISMATCH","intent or secret binding changed",exit_code=6)
 return stored

def transport(provider,payload):
 mode=os.getenv("CLAWPOD_IMAGE_STUDIO_TRANSPORT","disabled")
 if mode=="disabled": raise E("NETWORK_DISABLED","live provider transport is disabled by default",exit_code=8)
 if mode=="mock-outage": raise E("PROVIDER_OUTAGE","provider unavailable",exit_code=8,retryable=True)
 if mode=="mock-ambiguous": raise E("BILLING_AMBIGUOUS","provider response was ambiguous; do not automatically retry paid operation",exit_code=10,retryable=False,details={"billingState":"unknown","automaticRetry":False})
 if mode!="mock-success": raise E("NETWORK_DISABLED","only injected transports are supported",exit_code=8)
 return {"bytes":b"<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16'><rect width='16' height='16'/></svg>" if payload["format"]=="svg" else b"\x89PNG\r\n\x1a\nmock","mime":"image/svg+xml" if payload["format"]=="svg" else "image/png","providerJobId":"mock-"+sha(payload)[7:19]}
def inspect_artifact(path):
 b=path.read_bytes(); mime="image/svg+xml" if path.suffix.lower()==".svg" else (mimetypes.guess_type(path.name)[0] or "application/octet-stream")
 qa={"nonEmpty":bool(b),"svgParsed":None}
 if mime=="image/svg+xml":
  import xml.etree.ElementTree as ET
  try: root=ET.fromstring(b); qa["svgParsed"]=root.tag.endswith("svg")
  except ET.ParseError: qa["svgParsed"]=False
 return {"path":path.name,"bytes":len(b),"sha256":sha(b),"mimeType":mime,"qa":qa,"provenance":{"harness":"clawpod-image-studio","version":VERSION}}
def run_image(req,r,op):
 prepared=assert_prepared(req,r,op); p=safe_output(r/"artifacts",prepared["output"]); p.parent.mkdir(parents=True,exist_ok=True)
 result=transport(prepared["provider"],prepared)
 p.write_bytes(result["bytes"]); art=inspect_artifact(p)
 return {"state":"succeeded","provider":prepared["provider"],"providerJobId":result["providerJobId"],"artifact":art,"actualUsd":prepared["estimate"]["estimatedUsd"],"automaticRetry":False}
def execute(cmd,x,r):
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
  mode=os.getenv("CLAWPOD_IMAGE_STUDIO_VERIFY","disabled")
  if mode=="disabled": return {"provider":p,"state":"configured_unverified","verified":False,"billingAttempted":False,"reason":"no injected non-billable verifier"}
  if mode=="mock-outage": raise E("PROVIDER_OUTAGE","verification unavailable",8,True)
  if mode!="mock-success": raise E("NETWORK_DISABLED","unsupported verifier",8)
  rec["state"]="connected"; rec["verification"]={"at":now(),"billingAttempted":False}; cs[p]=rec; atomic(conn_path(r),cs); return {"provider":p,"state":"connected","verified":True,"billingAttempted":False}
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
 if cmd=="job.status":
  closed(x,{"provider","jobId"},("provider","jobId")); return {"state":"unknown","provider":x["provider"],"jobId":x["jobId"],"reason":"no live transport configured"}
 if cmd=="job.collect": raise E("NETWORK_DISABLED","collect requires an injected provider transport",8)
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
  p=Parser(); p.add_argument("command",choices=COMMANDS); p.add_argument("--input-json",default="{}"); p.add_argument("--root")
  a=p.parse_args(argv); cmd=a.command
  try: x=json.loads(a.input_json)
  except json.JSONDecodeError: raise E("INVALID_ARGUMENT","input-json must be valid JSON")
  if not isinstance(x,dict): raise E("SCHEMA_VIOLATION","input must be object")
  data=execute(cmd,x,root(a.root)); print(stable(env(cmd,True,data=data,effects="artifact_written" if cmd.startswith("image.") else "state_updated" if cmd.startswith("connection.") else "none"))); return 0
 except E as e: return fail(cmd,e)
if __name__=="__main__": raise SystemExit(main())
