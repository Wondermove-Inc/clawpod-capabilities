#!/usr/bin/env python3
"""ClawPod Video Studio adapter backed by pinned OpenMontage. Never persists or prints secret values."""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, re, shutil, signal, stat, subprocess, sys, tempfile, time, uuid
from pathlib import Path

VERSION="0.1.0"
UPSTREAM_COMMIT="c36e41223e819441748817105635ac4036d41b10"
MAX_JSON=1_000_000; MAX_LOG=250_000
STATES={"queued","running","awaiting_human","succeeded","failed","partial","cancel_requested","cancelled","cancel_failed"}
PIPELINES=[
 ("animated-explainer","production","education"),("animation","production","animation"),("avatar-spokesperson","production","avatar"),
 ("character-animation","beta","animation"),("cinematic","production","cinematic"),("clip-factory","beta","repurpose"),
 ("documentary-montage","beta","documentary"),("framework-smoke","beta/test","test"),("hybrid","production","hybrid"),
 ("localization-dub","beta","localization"),("podcast-repurpose","beta","repurpose"),("screen-demo","production","screen"),
 ("talking-head","beta","talking-head")]
PROVIDERS={
 "keyless":{"fields":[],"unlocks":["archive.org","nasa","wikimedia","piper","ffmpeg"]},
 "fal":{"fields":["FAL_KEY"],"unlocks":["flux","veo","kling","minimax"]},
 "atlas":{"fields":["ATLASCLOUD_API_KEY"],"unlocks":["atlas-cloud-models"]},
 "openai":{"fields":["OPENAI_API_KEY"],"unlocks":["openai-tts","gpt-image"]},
 "google":{"fields":["GOOGLE_API_KEY"],"unlocks":["imagen","google-tts"]},
 "elevenlabs":{"fields":["ELEVENLABS_API_KEY"],"unlocks":["tts","music","sfx"]},
 "kling":{"fields":["KLING_API_KEY"],"optional":["KLING_API_BASE_URL"],"unlocks":["kling-direct"]},
 "runway":{"fields":["RUNWAY_API_KEY"],"unlocks":["runway-gen4"]},
 "heygen":{"fields":["HEYGEN_API_KEY"],"unlocks":["heygen-gateway"]},
 "pexels":{"fields":["PEXELS_API_KEY"],"unlocks":["stock-video","stock-image"]},
 "pixabay":{"fields":["PIXABAY_API_KEY"],"unlocks":["stock-video","stock-image","music"]},
 "unsplash":{"fields":["UNSPLASH_ACCESS_KEY"],"unlocks":["stock-image"]},
 "xai":{"fields":["XAI_API_KEY"],"unlocks":["grok-image","grok-video"]},
 "suno":{"fields":["SUNO_API_KEY"],"unlocks":["music"]},
 "volcengine":{"fields":["VOLC_ACCESSKEY","VOLC_SECRETKEY"],"unlocks":["jimeng"]}
}
COMMANDS=["system.version","system.preflight","system.validate","pipeline.list","pipeline.inspect","provider.summary","provider.list","provider.inspect","provider.requirements","connection.list","connection.configure","connection.verify","connection.revoke","project.create","project.list","project.inspect","project.validate","project.plan","cost.estimate","cost.inspect","run.prepare","run.start","run.status","run.inspect","run.logs","run.resume","run.cancel","checkpoint.inspect","checkpoint.approve","checkpoint.request-revision","checkpoint.fail","stage.prepare","stage.validate","stage.commit","tool.prepare","tool.run","qa.run","qa.inspect","artifact.list","artifact.inspect","artifact.export","backlot.status","backlot.start","backlot.open","backlot.stop","install.inspect","install.plan-update","install.apply-update","install.rollback"]

class E(Exception):
 def __init__(self,code,msg,category="validation",retryable=False,details=None,exit_code=2):
  self.code,self.msg,self.category,self.retryable,self.details,self.exit_code=code,msg,category,retryable,details or {},exit_code

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def stable(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def sha(v): return "sha256:"+hashlib.sha256((v if isinstance(v,bytes) else stable(v).encode())).hexdigest()
def redact(v):
 pat=re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization|credential|bearer)")
 if isinstance(v,dict):
  out={}
  for k,x in v.items():
   pointer_metadata=isinstance(x,dict) and set(x).issubset({"pointerId","status"}) and "pointerId" in x
   out[k]=redact(x) if (not pat.search(k) or pointer_metadata) else "[REDACTED]"
  return out
 if isinstance(v,list): return [redact(x) for x in v]
 return v

def envelope(cmd,ok=True,data=None,warnings=None,error=None,artifacts=None,page=None):
 return {"schemaVersion":"1.0","ok":ok,"command":cmd,"requestId":str(uuid.uuid4()),"timestamp":now(),"data":redact(data or {}),"warnings":warnings or [],"artifacts":artifacts or [],"page":page,"error":error}

def fail(cmd,e):
 err={"code":e.code,"message":e.msg,"category":e.category,"retryable":e.retryable,"partial":e.code=="PARTIAL_FAILURE","providerStatus":None,"details":redact(e.details),"remediation":remediation(e.code)}
 print(stable(envelope(cmd,False,error=err))); return e.exit_code

def remediation(code):
 return {"PREREQUISITE_MISSING":"Install or configure the reported prerequisite, then rerun preflight.","APPROVAL_REQUIRED":"Prepare the exact intent and obtain approval for its unchanged digest.","AUTH_REQUIRED":"Complete protected provider onboarding.","UPSTREAM_CONTRACT_INVALID":"Use a fixed pinned upstream revision or an approved documented patch.","PATH_VIOLATION":"Use a relative path beneath the configured private root.","CONFLICT":"Refresh state and retry against the current revision."}.get(code,"Inspect the structured details and correct the request before retrying.")

def load_json_arg(raw,name="input"):
 if raw is None: return {}
 if len(raw)>MAX_JSON: raise E("INVALID_ARGUMENT",f"{name} is too large")
 try: v=json.loads(raw)
 except json.JSONDecodeError as x: raise E("INVALID_ARGUMENT",f"{name} is not valid JSON: {x.msg}")
 if not isinstance(v,dict): raise E("INVALID_ARGUMENT",f"{name} must be an object")
 return v

def root(args):
 p=Path(args.root or os.getenv("OPENMONTAGE_STATE_ROOT",str(Path.home()/".clawpod-video-studio")))
 p.mkdir(parents=True,exist_ok=True,mode=0o700)
 if p.is_symlink(): raise E("PATH_VIOLATION","state root may not be a symlink")
 rp=p.resolve(); os.chmod(rp,0o700); return rp

def child(base,rel,exist=False):
 if not isinstance(rel,str) or not rel or "\x00" in rel: raise E("PATH_VIOLATION","bounded relative path required")
 q=Path(rel)
 if q.is_absolute() or ".." in q.parts: raise E("PATH_VIOLATION","absolute/traversing paths are forbidden")
 cur=base
 for part in q.parts:
  cur=cur/part
  if cur.exists() and cur.is_symlink(): raise E("PATH_VIOLATION","symlink components are forbidden")
 out=(base/q).resolve(strict=False)
 if base not in out.parents and out!=base: raise E("PATH_VIOLATION","path escapes configured root")
 if exist and not out.exists(): raise E("NOT_FOUND","path not found",exit_code=3)
 return out

def atomic(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 fd,tmp=tempfile.mkstemp(prefix=".tmp-",dir=path.parent)
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,"w",encoding="utf-8") as f: json.dump(obj,f,ensure_ascii=False,sort_keys=True,indent=2); f.flush(); os.fsync(f.fileno())
  os.replace(tmp,path)
 finally:
  try: os.unlink(tmp)
  except FileNotFoundError: pass

def readj(path,default=None):
 if not path.exists(): return default
 if path.stat().st_size>MAX_JSON: raise E("SCHEMA_VIOLATION","state file exceeds limit")
 try: return json.loads(path.read_text())
 except json.JSONDecodeError: raise E("SCHEMA_VIOLATION","state file is malformed")

def project_dir(r,pid):
 if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?",pid or ""): raise E("INVALID_ARGUMENT","projectId must be kebab-case, 1-64 chars")
 return child(r/"projects",pid)

def require_pointer(v):
 if not isinstance(v,dict) or not v: raise E("INVALID_ARGUMENT","bindings must be a nonempty provider-field to secret-pointer object")
 out={}
 for field,p in v.items():
  if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,80}",field): raise E("INVALID_ARGUMENT","invalid provider field")
  if isinstance(p,str): ptr=p
  elif isinstance(p,dict): ptr=p.get("pointerId")
  else: ptr=None
  if not isinstance(ptr,str) or not re.fullmatch(r"(?:secret|memsec|ptr)[A-Za-z0-9:_-]{6,180}",ptr): raise E("INVALID_ARGUMENT",f"{field} must reference a protected secret pointer, not plaintext")
  out[field]={"pointerId":ptr,"status":"configured_unverified"}
 return out

def list_projects(r):
 d=r/"projects"; d.mkdir(parents=True,exist_ok=True)
 return [readj(x/"project.json",{}) for x in sorted(d.iterdir()) if x.is_dir() and (x/"project.json").exists()][:100]

def get_project(r,pid):
 p=project_dir(r,pid); obj=readj(p/"project.json")
 if not obj: raise E("NOT_FOUND","project not found",exit_code=3)
 return p,obj

def job_path(r,jid):
 if not re.fullmatch(r"job-[a-f0-9]{16}",jid or ""): raise E("INVALID_ARGUMENT","invalid jobId")
 return child(r/"jobs",jid+".json")

def handler(cmd,a,x):
 r=root(a)
 if cmd=="system.version": return {"capabilityVersion":VERSION,"upstreamCommit":UPSTREAM_COMMIT,"schemaVersion":"1.0"},[]
 if cmd=="system.preflight":
  deps={"python":{"ok":sys.version_info>=(3,10),"version":sys.version.split()[0]},"node":{"ok":bool(shutil.which("node")),"path":shutil.which("node")},"ffmpeg":{"ok":bool(shutil.which("ffmpeg")),"path":shutil.which("ffmpeg")},"git":{"ok":bool(shutil.which("git")),"path":shutil.which("git")}}
  return {"readyLocal":all(v["ok"] for k,v in deps.items() if k in ("python","node","ffmpeg")),"dependencies":deps,"stateRoot":str(r),"connected":bool(readj(r/"connections.json",{}))},[]
 if cmd=="system.validate":
  return {"valid":True,"pipelines":len(PIPELINES),"knownDefects":[],"localPatches":["openmontage-documentary-category"]},[]
 if cmd in ("pipeline.list","pipeline.inspect"):
  items=[{"id":n,"stability":s,"category":c,"contractValid":True} for n,s,c in PIPELINES]
  if cmd.endswith("inspect"):
   pid=x.get("pipelineId") or a.pipeline_id; m=next((z for z in items if z["id"]==pid),None)
   if not m: raise E("NOT_FOUND","pipeline not found",exit_code=3)
   return m,[]
  return {"items":items,"count":len(items)},[]
 if cmd in ("provider.requirements","provider.list","provider.summary","provider.inspect"):
  con=readj(r/"connections.json",{}) or {}
  items=[{"provider":k,**v,"connectionState":con.get(k,{}).get("status","deferred")} for k,v in PROVIDERS.items()]
  if cmd=="provider.summary": return {"total":len(items),"connected":sum(i["connectionState"] in ("connected","configured_unverified") for i in items),"installedButNotConnected":not bool(con)},[]
  if cmd=="provider.inspect":
   name=x.get("provider") or a.provider; item=next((i for i in items if i["provider"]==name),None)
   if not item: raise E("NOT_FOUND","provider not found",exit_code=3)
   return item,[]
  return {"items":items,"count":len(items)},[]
 if cmd=="connection.list": return {"items":[{"provider":k,**v} for k,v in (readj(r/"connections.json",{}) or {}).items()]},[]
 if cmd=="connection.configure":
  provider=x.get("provider") or a.provider
  if provider not in PROVIDERS: raise E("INVALID_ARGUMENT","unknown provider")
  bindings=require_pointer(x.get("bindings"))
  required=set(PROVIDERS[provider].get("fields",[])); missing=sorted(required-set(bindings))
  con=readj(r/"connections.json",{}) or {}; con[provider]={"status":"missing_companion_field" if missing else "configured_unverified","bindings":bindings,"missing":missing,"updatedAt":now(),"revocation":"Revoke the key in the provider console, then remove this local binding."}; atomic(r/"connections.json",con)
  return {"provider":provider,**con[provider]},[]
 if cmd=="connection.verify":
  provider=x.get("provider") or a.provider; con=readj(r/"connections.json",{}) or {}
  if provider not in con: raise E("AUTH_REQUIRED","provider is not configured",category="auth",exit_code=5)
  if not x.get("secretResolverAvailable",False): return {"provider":provider,"status":"configured_unverified","reason":"runtime protected-secret resolver not supplied"},[]
  raise E("PREREQUISITE_MISSING","live zero-cost verifier adapter is not installed",exit_code=8)
 if cmd=="connection.revoke":
  provider=x.get("provider") or a.provider
  if x.get("confirm")!="remove-binding": raise E("APPROVAL_REQUIRED","confirm=remove-binding is required",category="approval",exit_code=6)
  con=readj(r/"connections.json",{}) or {}; existed=con.pop(provider,None); atomic(r/"connections.json",con); return {"provider":provider,"removed":bool(existed),"secretDeleted":False},[]
 if cmd=="project.create":
  pid=x.get("projectId") or a.project_id; p=project_dir(r,pid); key=x.get("idempotencyKey"); cur=readj(p/"project.json")
  intent={"projectId":pid,"pipelineId":x.get("pipelineId"),"title":x.get("title",pid)}; dig=sha(intent)
  if cur:
   if key and cur.get("idempotencyKey")==key and cur.get("inputDigest")==dig: return cur,[]
   raise E("CONFLICT","project already exists with different intent",exit_code=4)
  if intent["pipelineId"] not in [n for n,_,_ in PIPELINES]: raise E("INVALID_ARGUMENT","unknown pipelineId")
  p.mkdir(parents=True,mode=0o700); [child(p,z).mkdir(exist_ok=True) for z in ("artifacts","assets","renders","history")]
  obj={**intent,"revision":1,"status":"created","createdAt":now(),"idempotencyKey":key,"inputDigest":dig}; atomic(p/"project.json",obj); return obj,[]
 if cmd=="project.list": return {"items":list_projects(r)},[]
 if cmd in ("project.inspect","project.validate"):
  p,obj=get_project(r,x.get("projectId") or a.project_id)
  if cmd.endswith("validate"): return {"projectId":obj["projectId"],"valid":all(child(p,z).is_dir() for z in ("artifacts","assets","renders","history")),"revision":obj["revision"]},[]
  return {**obj,"artifacts":len(list((p/"artifacts").glob("*"))),"renders":len(list((p/"renders").glob("*")))},[]
 if cmd=="project.plan":
  p,obj=get_project(r,x.get("projectId") or a.project_id); expected=x.get("expectedRevision",obj["revision"])
  if expected!=obj["revision"]: raise E("CONFLICT","project revision changed",exit_code=4)
  plan=x.get("plan");
  if not isinstance(plan,dict): raise E("INVALID_ARGUMENT","plan object required")
  pd=sha(plan); record={"schemaVersion":"1.0","plan":plan,"planDigest":pd,"createdAt":now(),"revision":obj["revision"]}; atomic(p/"plan.json",record); obj["revision"]+=1; obj["status"]="planned"; atomic(p/"project.json",obj); return record,[]
 if cmd in ("cost.estimate","cost.inspect"):
  pid=x.get("projectId") or a.project_id; p,obj=get_project(r,pid); ledger=readj(p/"cost.json",{"estimatedUsd":0,"reservedUsd":0,"actualUsd":0,"maximumAuthorizedUsd":0,"entries":[]})
  if cmd=="cost.estimate": return {**ledger,"assumptions":x.get("assumptions",[]),"confidence":"unknown"},[]
  return ledger,[]
 if cmd=="run.prepare":
  p,obj=get_project(r,x.get("projectId") or a.project_id); plan=readj(p/"plan.json")
  if not plan: raise E("PREREQUISITE_MISSING","project plan is missing",exit_code=8)
  ops=x.get("operations",[]); est=float(x.get("maximumUsd",0)); providers=x.get("providers",[])
  intent={"intentId":"intent-"+uuid.uuid4().hex[:16],"projectId":obj["projectId"],"projectRevision":obj["revision"],"planDigest":plan["planDigest"],"upstreamCommit":UPSTREAM_COMMIT,"operations":ops,"providers":providers,"maximumUsd":est,"sideEffects":x.get("sideEffects",[]),"expiresAt":(dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=30)).isoformat()}; intent["inputDigest"]=sha(intent); atomic(p/"intent.json",intent); return intent,[]
 if cmd in ("run.start","run.resume"):
  p,obj=get_project(r,x.get("projectId") or a.project_id); intent=readj(p/"intent.json")
  if not intent: raise E("PREREQUISITE_MISSING","prepared intent missing",exit_code=8)
  if x.get("intentId")!=intent["intentId"] or x.get("planDigest")!=intent["planDigest"]: raise E("APPROVAL_REQUIRED","intent or plan digest changed",category="approval",exit_code=6)
  paid=intent["maximumUsd"]>0 or bool(intent["providers"])
  if paid and (not x.get("approvalReference") or float(x.get("maximumAuthorizedUsd",-1))<intent["maximumUsd"]): raise E("APPROVAL_REQUIRED","exact paid-operation approval binding required",category="approval",details={"planDigest":intent["planDigest"],"maximumUsd":intent["maximumUsd"]},exit_code=6)
  jid="job-"+uuid.uuid4().hex[:16]; job={"jobId":jid,"projectId":obj["projectId"],"planDigest":intent["planDigest"],"state":"awaiting_human","stage":"proposal","progress":{"completed":0,"total":len(intent["operations"]),"unit":"operation","percent":0},"heartbeatAt":now(),"startedAt":now(),"finishedAt":None,"attempt":1,"cost":{"estimatedUsd":intent["maximumUsd"],"reservedUsd":0,"actualUsd":0,"maximumAuthorizedUsd":x.get("maximumAuthorizedUsd",0)},"gate":{"required":True,"stage":"proposal","artifactDigest":None},"partialArtifacts":[],"lastError":None,"ownedPid":None}; jp=job_path(r,jid); jp.parent.mkdir(parents=True,exist_ok=True); atomic(jp,job); return job,[]
 if cmd in ("run.status","run.inspect"):
  job=readj(job_path(r,x.get("jobId") or a.job_id));
  if not job: raise E("NOT_FOUND","job not found",exit_code=3)
  return job,[]
 if cmd=="run.logs":
  jid=x.get("jobId") or a.job_id; lp=job_path(r,jid).with_suffix(".log"); txt=lp.read_text(errors="replace")[-MAX_LOG:] if lp.exists() else ""; return {"jobId":jid,"text":redact(txt),"truncated":lp.exists() and lp.stat().st_size>MAX_LOG},[]
 if cmd=="run.cancel":
  jid=x.get("jobId") or a.job_id; jp=job_path(r,jid); job=readj(jp)
  if not job: raise E("NOT_FOUND","job not found",exit_code=3)
  if x.get("confirm")!="cancel-job": raise E("APPROVAL_REQUIRED","confirm=cancel-job required",category="approval",exit_code=6)
  pid=job.get("ownedPid")
  if pid:
   try: os.kill(pid,0)
   except OSError: pid=None
  if pid: raise E("CANCEL_FAILED","refusing to signal a process without an adapter ownership nonce",category="destructive",exit_code=11)
  job["state"]="cancelled"; job["finishedAt"]=now(); atomic(jp,job); return job,[]
 if cmd.startswith("checkpoint."):
  p,obj=get_project(r,x.get("projectId") or a.project_id); cp=readj(p/"checkpoint.json",{"projectId":obj["projectId"],"status":"in_progress","stage":"research","revision":0})
  if cmd=="checkpoint.inspect": return cp,[]
  action=cmd.split(".",1)[1]
  if action=="approve" and not x.get("artifactDigest"): raise E("INVALID_ARGUMENT","artifactDigest required")
  cp.update({"status":"completed" if action=="approve" else "failed" if action=="fail" else "in_progress","action":action,"artifactDigest":x.get("artifactDigest"),"revision":cp.get("revision",0)+1,"updatedAt":now()}); atomic(p/"checkpoint.json",cp); return cp,[]
 if cmd.startswith("stage."):
  pid=x.get("projectId") or a.project_id; p,obj=get_project(r,pid)
  if cmd=="stage.prepare": return {"projectId":pid,"stage":x.get("stage"),"requiresSkillDrivenOrchestration":True,"upstreamCommit":UPSTREAM_COMMIT},[]
  if cmd=="stage.validate": return {"valid":isinstance(x.get("artifact"),dict),"stage":x.get("stage")},[]
  if not isinstance(x.get("artifact"),dict): raise E("INVALID_ARGUMENT","artifact object required")
  rel=f"artifacts/{x.get('stage','unknown')}.json"; ap=child(p,rel); atomic(ap,x["artifact"]); return {"relativePath":rel,"sha256":sha(ap.read_bytes()),"stage":x.get("stage")},[]
 if cmd.startswith("tool."):
  spec={"tool":x.get("tool"),"input":x.get("input",{}),"provider":x.get("provider"),"model":x.get("model"),"maximumUsd":x.get("maximumUsd",0)}; dig=sha(spec)
  if cmd=="tool.prepare": return {"toolDigest":dig,**spec,"requiresApproval":bool(spec["provider"] or spec["maximumUsd"])},[]
  if x.get("toolDigest")!=dig: raise E("APPROVAL_REQUIRED","tool input/provider/model/cost digest changed",category="approval",exit_code=6)
  raise E("PREREQUISITE_MISSING","live upstream tool runner is not activated in the build artifact",exit_code=8)
 if cmd in ("qa.run","qa.inspect"):
  p,obj=get_project(r,x.get("projectId") or a.project_id); qp=p/"artifacts"/"qa.json"
  if cmd=="qa.inspect": return readj(qp,{"status":"not_run"}),[]
  target=x.get("relativePath"); fp=child(p,target,exist=True); checks={"exists":fp.is_file(),"bytes":fp.stat().st_size,"ffprobeAvailable":bool(shutil.which("ffprobe"))}; result={"status":"passed" if checks["exists"] and checks["bytes"]>0 else "failed","checks":checks,"target":target,"updatedAt":now()}; atomic(qp,result); return result,[]
 if cmd.startswith("artifact."):
  p,obj=get_project(r,x.get("projectId") or a.project_id); files=[]
  for d in ("artifacts","assets","renders"):
   for f in child(p,d).glob("*"):
    if f.is_file() and not f.is_symlink(): files.append({"relativePath":str(f.relative_to(p)),"bytes":f.stat().st_size,"sha256":sha(f.read_bytes())})
  if cmd=="artifact.list": return {"items":files},[]
  rel=x.get("relativePath"); f=child(p,rel,exist=True); item={"relativePath":rel,"bytes":f.stat().st_size,"sha256":sha(f.read_bytes())}
  if cmd=="artifact.inspect": return item,[]
  out=child(p,x.get("output","artifacts/export-manifest.json")); atomic(out,{"projectId":obj["projectId"],"items":files,"createdAt":now()}); return {"relativePath":str(out.relative_to(p)),"items":len(files)},[]
 if cmd.startswith("backlot."):
  state=readj(r/"backlot.json",{"running":False,"ownedPid":None,"url":None})
  if cmd=="backlot.status": return state,[]
  if cmd=="backlot.open": raise E("PREREQUISITE_MISSING","browser opening is delegated to the desktop/browser capability",exit_code=8)
  if cmd=="backlot.start": raise E("PREREQUISITE_MISSING","pinned upstream Backlot runtime is not installed",exit_code=8)
  if x.get("confirm")!="stop-backlot": raise E("APPROVAL_REQUIRED","confirm=stop-backlot required",category="approval",exit_code=6)
  if state.get("ownedPid"): raise E("CANCEL_FAILED","owned Backlot process termination is unavailable in build mode",exit_code=11)
  return {"running":False,"stopped":False},[]
 if cmd.startswith("install."):
  lock=readj(Path(__file__).parent/"upstream.lock.json",{})
  if cmd=="install.inspect": return {"capabilityVersion":VERSION,"upstream":lock,"connected":bool(readj(r/"connections.json",{})),"onboardingRequired":True},[]
  if cmd=="install.plan-update": return {"current":lock,"requested":x.get("upstreamCommit"),"mutationRequired":x.get("upstreamCommit") not in (None,UPSTREAM_COMMIT),"approvalRequired":True},[]
  raise E("PREREQUISITE_MISSING","transactional installer lifecycle is not activated in the build artifact",category="install",exit_code=8)
 raise E("INVALID_ARGUMENT","unsupported command")

def parser():
 p=argparse.ArgumentParser(); p.add_argument("command",choices=COMMANDS); p.add_argument("--root"); p.add_argument("--input-json"); p.add_argument("--project-id"); p.add_argument("--pipeline-id"); p.add_argument("--provider"); p.add_argument("--job-id"); return p

def main():
 a=parser().parse_args(); cmd=a.command
 try:
  x=load_json_arg(a.input_json); data,w=handler(cmd,a,x); print(stable(envelope(cmd,data=data,warnings=w))); return 0
 except E as e: return fail(cmd,e)
 except Exception as e: return fail(cmd,E("INTERNAL_ERROR","internal adapter failure",category="internal",details={"type":type(e).__name__},exit_code=12))
if __name__=="__main__": raise SystemExit(main())
