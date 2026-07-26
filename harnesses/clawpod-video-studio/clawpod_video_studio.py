#!/usr/bin/env python3
"""ClawPod Video Studio runtime adapter for a pinned OpenMontage checkout.
Secrets are accepted only from the process environment or mode-0600 files and
are never persisted, echoed, or placed on child argv.
"""
from __future__ import annotations
import argparse, contextlib, datetime as dt, fcntl, hashlib, json, os, re, shutil, signal, socket, stat, subprocess, sys, tempfile, time, urllib.error, urllib.request, uuid
from pathlib import Path
import yaml

VERSION="0.2.0"; UPSTREAM_COMMIT="c36e41223e819441748817105635ac4036d41b10"
MAX_JSON=1_000_000; MAX_LOG=250_000
PIPELINES=[("animated-explainer","production","education"),("animation","production","animation"),("avatar-spokesperson","production","avatar"),("character-animation","beta","animation"),("cinematic","production","cinematic"),("clip-factory","beta","repurpose"),("documentary-montage","beta","documentary"),("framework-smoke","beta/test","test"),("hybrid","production","hybrid"),("localization-dub","beta","localization"),("podcast-repurpose","beta","repurpose"),("screen-demo","production","screen"),("talking-head","beta","talking-head")]
PROVIDERS={
 "keyless":{"fields":[],"unlocks":["ffmpeg","ffprobe","piper","local-analysis"]},
 "fal":{"fields":["FAL_KEY"]},"atlas":{"fields":["ATLASCLOUD_API_KEY"]},"openai":{"fields":["OPENAI_API_KEY"]},
 "google":{"fields":["GOOGLE_API_KEY"]},"elevenlabs":{"fields":["ELEVENLABS_API_KEY"]},"kling":{"fields":["KLING_API_KEY"],"optional":["KLING_API_BASE_URL"]},
 "runway":{"fields":["RUNWAY_API_KEY"]},"heygen":{"fields":["HEYGEN_API_KEY"]},"pexels":{"fields":["PEXELS_API_KEY"]},
 "pixabay":{"fields":["PIXABAY_API_KEY"]},"unsplash":{"fields":["UNSPLASH_ACCESS_KEY"]},"xai":{"fields":["XAI_API_KEY"]},
 "suno":{"fields":["SUNO_API_KEY"]},"volcengine":{"fields":["VOLC_ACCESSKEY","VOLC_SECRETKEY"]},
 "azure":{"fields":["AZURE_SPEECH_KEY","AZURE_SPEECH_REGION"],"optional":["AZURE_SPEECH_ENDPOINT"]},
 "dashscope":{"fields":["DASHSCOPE_API_KEY"]},"doubao":{"fields":["DOUBAO_SPEECH_API_KEY"]},
 "freesound":{"fields":["FREESOUND_API_KEY"]},"higgsfield":{"fields":["HIGGSFIELD_API_KEY"],"optional":["HIGGSFIELD_API_SECRET"]},
 "replicate":{"fields":["REPLICATE_API_TOKEN"]},"modal":{"fields":["MODAL_LTX2_ENDPOINT_URL"]},
 "huggingface":{"fields":["HF_TOKEN"]},"nara":{"fields":["NARA_API_KEY"]},"coverr":{"fields":["COVERR_API_KEY"]},
 "pond5":{"fields":["POND5_API_KEY"]},"videvo":{"fields":["VIDEVO_API_KEY"]}}
TOOL_PROVIDER_ALIASES={
 "flux":"fal","minimax":"fal","recraft":"fal","veo":"fal","google_imagen":"google","google_tts":"google","gemini_omni":"google","grok":"xai","pixabay_music":"pixabay","kling_official":"kling","ltx-modal":"modal"}
TOOL_PROVIDER_OVERRIDES={"kling_video":"fal","minimax_video":"fal","veo_video":"fal","seedance_video":"fal","seedance_replicate":"replicate"}
VERIFY_ADAPTERS={
 "openai":("https://api.openai.com/v1/models",lambda s:{"Authorization":"Bearer "+s["OPENAI_API_KEY"]}),
 "xai":("https://api.x.ai/v1/models",lambda s:{"Authorization":"Bearer "+s["XAI_API_KEY"]}),
 "google":("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1",lambda s:{"x-goog-api-key":s["GOOGLE_API_KEY"]}),
 "elevenlabs":("https://api.elevenlabs.io/v1/user/subscription",lambda s:{"xi-api-key":s["ELEVENLABS_API_KEY"]}),
 "pexels":("https://api.pexels.com/v1/curated?per_page=1",lambda s:{"Authorization":s["PEXELS_API_KEY"]}),
 "unsplash":("https://api.unsplash.com/photos?per_page=1",lambda s:{"Authorization":"Client-ID "+s["UNSPLASH_ACCESS_KEY"]})}
COMMANDS="system.version system.preflight system.validate pipeline.list pipeline.inspect provider.summary provider.list provider.inspect provider.requirements connection.list connection.configure connection.verify connection.revoke project.create project.list project.inspect project.validate project.plan cost.estimate cost.inspect run.prepare run.start run.status run.inspect run.logs run.resume run.cancel checkpoint.inspect checkpoint.approve checkpoint.request-revision checkpoint.fail stage.prepare stage.validate stage.commit tool.prepare tool.run qa.run qa.inspect artifact.list artifact.inspect artifact.export backlot.status backlot.start backlot.open backlot.stop install.inspect install.plan-update install.apply-update install.rollback".split()
SECRET_RE=re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization|credential|bearer|accesskey)")

class E(Exception):
 def __init__(self,code,msg,category="validation",retryable=False,details=None,exit_code=2): self.code,self.msg,self.category,self.retryable,self.details,self.exit_code=code,msg,category,retryable,details or {},exit_code

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def require_future_expiry(value):
 if not isinstance(value,str): raise E("APPROVAL_REQUIRED","approval expiry is required",category="approval",exit_code=6)
 try: parsed=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
 except ValueError: raise E("INVALID_ARGUMENT","approvalExpiresAt must be ISO-8601")
 if parsed.tzinfo is None or parsed<=dt.datetime.now(dt.timezone.utc): raise E("APPROVAL_REQUIRED","approval is expired",category="approval",exit_code=6)
 return parsed.isoformat()
def stable(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def sha(v): return "sha256:"+hashlib.sha256(v if isinstance(v,bytes) else stable(v).encode()).hexdigest()
def verified_intent_digest(intent):
 payload={k:v for k,v in intent.items() if k!="inputDigest"}; actual=sha(payload)
 if intent.get("inputDigest")!=actual: raise E("DIGEST_MISMATCH","prepared intent digest is invalid",category="digest",exit_code=9)
 return actual
def approval_binding_digest(intent_digest,providers,operations,maximum_usd,approval_reference,expires_at):
 return sha({"intentDigest":intent_digest,"providers":sorted(providers),"operationDigests":[sha(op) for op in operations],"maximumUsd":float(maximum_usd),"approvalReference":approval_reference,"approvalExpiresAt":expires_at})
def tool_approval_binding_digest(tool_digest,spec,approval_reference,expires_at):
 return sha({"toolDigest":tool_digest,"provider":spec.get("provider"),"model":spec.get("model"),"operation":spec.get("operation"),"inputDigest":sha(spec.get("input",{})),"maximumUsd":float(spec.get("maximumUsd",0)),"approvalReference":approval_reference,"approvalExpiresAt":expires_at})
def checkpoint_approval_binding_digest(job_id,intent_digest,stage,artifact_digest,approval_reference,expires_at):
 return sha({"jobId":job_id,"intentDigest":intent_digest,"stage":stage,"artifactDigest":artifact_digest,"approvalReference":approval_reference,"approvalExpiresAt":expires_at})
def redact(v):
 if isinstance(v,dict):
  return {k:(redact(x) if not SECRET_RE.search(k) or (isinstance(x,dict) and set(x)<= {"pointerId","status","source","environment","fileEnvironment"}) else "[REDACTED]") for k,x in v.items()}
 if isinstance(v,list): return [redact(x) for x in v]
 if isinstance(v,str): return re.sub(r"(?i)(bearer\s+|(?:sk|key|token)[-_])[A-Za-z0-9._-]{8,}",r"\1[REDACTED]",v)
 return v
def envelope(cmd,ok=True,data=None,warnings=None,error=None,artifacts=None): return {"schemaVersion":"1.0","ok":ok,"command":cmd,"requestId":str(uuid.uuid4()),"timestamp":now(),"data":redact(data or {}),"warnings":warnings or [],"artifacts":artifacts or [],"page":None,"error":error}
def remediation(c): return {"AUTH_REQUIRED":"Inject required secrets through approved environment/file secret injection.","DIGEST_MISMATCH":"Restore the exact pinned checkout and documented patch.","PATH_VIOLATION":"Use a bounded relative path.","APPROVAL_REQUIRED":"Approve the unchanged prepared digest.","TIMEOUT":"Inspect partial state and explicitly resume if safe."}.get(c,"Correct the structured error and retry only when safe.")
def fail(cmd,e):
 print(stable(envelope(cmd,False,error={"code":e.code,"message":e.msg,"category":e.category,"retryable":e.retryable,"partial":e.code=="PARTIAL_FAILURE","details":redact(e.details),"remediation":remediation(e.code)}))); return e.exit_code

def load_json_arg(raw):
 if raw is None: return {}
 if len(raw)>MAX_JSON: raise E("INVALID_ARGUMENT","input is too large")
 try: v=json.loads(raw)
 except json.JSONDecodeError as z: raise E("INVALID_ARGUMENT",f"input is not valid JSON: {z.msg}")
 if not isinstance(v,dict): raise E("INVALID_ARGUMENT","input must be an object")
 return v
def atomic(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True,mode=0o700); fd,t=tempfile.mkstemp(prefix=".tmp-",dir=p.parent)
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,"w") as f: json.dump(obj,f,sort_keys=True,indent=2); f.flush(); os.fsync(f.fileno())
  os.replace(t,p)
 finally:
  try: os.unlink(t)
  except FileNotFoundError: pass
def readj(p,default=None):
 if not p.exists(): return default
 if p.stat().st_size>MAX_JSON: raise E("SCHEMA_VIOLATION","state file exceeds limit")
 try: return json.loads(p.read_text())
 except Exception: raise E("SCHEMA_VIOLATION","state file is malformed")
def root(a):
 p=Path(a.root or os.getenv("OPENMONTAGE_STATE_ROOT",str(Path.home()/".clawpod-video-studio")))
 if p.exists() and p.is_symlink(): raise E("PATH_VIOLATION","state root may not be a symlink")
 p.mkdir(parents=True,exist_ok=True,mode=0o700); p=p.resolve(); os.chmod(p,0o700); return p
def child(base,rel,exist=False):
 if not isinstance(rel,str) or not rel or "\0" in rel: raise E("PATH_VIOLATION","bounded relative path required")
 q=Path(rel)
 if q.is_absolute() or ".." in q.parts: raise E("PATH_VIOLATION","absolute/traversing paths forbidden")
 cur=base
 for part in q.parts:
  cur/=part
  if cur.exists() and cur.is_symlink(): raise E("PATH_VIOLATION","symlink components forbidden")
 out=(base/q).resolve(strict=False)
 if out!=base and base not in out.parents: raise E("PATH_VIOLATION","path escapes root")
 if exist and not out.exists(): raise E("NOT_FOUND","path not found",exit_code=3)
 return out
def project_dir(r,pid):
 if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?",pid or ""): raise E("INVALID_ARGUMENT","invalid projectId")
 return child(r/"projects",pid)
def get_project(r,pid):
 p=project_dir(r,pid); o=readj(p/"project.json")
 if not o: raise E("NOT_FOUND","project not found",exit_code=3)
 return p,o
def job_path(r,jid):
 if not re.fullmatch(r"job-[a-f0-9]{16}",jid or ""): raise E("INVALID_ARGUMENT","invalid jobId")
 return child(r/"jobs",jid+".json")
@contextlib.contextmanager
def state_lock(path):
 path.parent.mkdir(parents=True,exist_ok=True,mode=0o700); fd=os.open(path,os.O_RDWR|os.O_CREAT,0o600)
 try: fcntl.flock(fd,fcntl.LOCK_EX); yield
 finally: fcntl.flock(fd,fcntl.LOCK_UN); os.close(fd)
def pid_alive(pid):
 try: os.kill(int(pid),0); return True
 except (OSError,ValueError,TypeError): return False
def process_start_identity(pid):
 try: return Path(f"/proc/{int(pid)}/stat").read_text().split()[21]
 except Exception: return None
def owned_process_alive(pid,start_identity):
 if not pid_alive(pid): return False
 current=process_start_identity(pid)
 return current==start_identity if current and start_identity else False

def runtime_candidates(x=None):
 vals=[]
 for p in ((x or {}).get("runtimePath"),os.getenv("OPENMONTAGE_RUNTIME"),"/workspace/vendor/openmontage/"+UPSTREAM_COMMIT):
  if p and p not in vals: vals.append(p)
 return [Path(p).expanduser().resolve() for p in vals]
def runtime(x=None,required=True):
 for p in runtime_candidates(x):
  if (p/"pipeline_defs").is_dir() and (p/"tools").is_dir(): return p
 if required: raise E("RUNTIME_NOT_FOUND","pinned OpenMontage runtime not found",category="prerequisite",exit_code=8,details={"searched":[str(p) for p in runtime_candidates(x)]})
 return None
def file_sha(p): return "sha256:"+hashlib.sha256(p.read_bytes()).hexdigest()
def secure_file_sha(p):
 flags=os.O_RDONLY|getattr(os,"O_NOFOLLOW",0); fd=os.open(p,flags)
 try:
  st=os.fstat(fd)
  if not stat.S_ISREG(st.st_mode): raise E("PATH_VIOLATION","artifact must be a regular file")
  h=hashlib.sha256()
  while True:
   chunk=os.read(fd,1024*1024)
   if not chunk: break
   h.update(chunk)
  return "sha256:"+h.hexdigest()
 finally: os.close(fd)
def source_digest(rt):
 h=hashlib.sha256(); excluded={".git",".clawpod-venv","node_modules","__pycache__",".pytest_cache",".env",".clawpod-runtime-lock.json"}
 for p in sorted(rt.rglob("*"),key=lambda z:str(z.relative_to(rt))):
  rel=p.relative_to(rt)
  if any(part in excluded for part in rel.parts) or not p.is_file() or p.is_symlink(): continue
  h.update(str(rel).encode()+b"\0"); h.update(hashlib.sha256(p.read_bytes()).digest())
 return "sha256:"+h.hexdigest()
def validate_runtime(x=None):
 rt=runtime(x); package=Path(__file__).parent; lock=readj(package/"upstream.lock.json",{}); deps=readj(package/"dependencies.lock.json",{})
 def git(*args):
  q=subprocess.run(["git","-C",str(rt),*args],text=True,capture_output=True,timeout=5)
  return q.stdout.strip() if q.returncode==0 else None
 marker=readj(rt/".clawpod-runtime-lock.json",{}) or {}; commit=git("rev-parse","HEAD") or marker.get("commit"); tree=git("rev-parse","HEAD^{tree}") or marker.get("tree"); dirty=[]
 if (rt/".git").exists():
  status_out=git("status","--porcelain","--untracked-files=all") or ""; allowed_patch={item.get("path") for item in lock.get("patchedFiles",[])}
  for line in status_out.splitlines():
   path=(line[3:] if len(line)>2 and line[2]==" " else line[2:]).strip().strip('"')
   if path in allowed_patch or path.startswith(".clawpod-venv/") or path.startswith("remotion-composer/node_modules/"): continue
   dirty.append(line)
 all_links=[p for p in rt.rglob("*") if p.is_symlink()]; unsafe_links=[str(p.relative_to(rt)) for p in all_links if not any(z in p.relative_to(rt).parts for z in (".git",".clawpod-venv","node_modules"))]; escaping_links=[]
 for link in all_links:
  try:
   target=link.resolve(strict=False)
   rel=str(link.relative_to(rt)); allowed_python=rel in (".clawpod-venv/bin/python",".clawpod-venv/bin/python3",f".clawpod-venv/bin/python{sys.version_info.major}.{sys.version_info.minor}") and target==Path(sys.executable).resolve()
   if target!=rt and rt not in target.parents and not allowed_python: escaping_links.append(rel)
  except Exception: escaping_links.append(str(link.relative_to(rt)))
 checks={"commit":{"expected":UPSTREAM_COMMIT,"actual":commit,"ok":commit==UPSTREAM_COMMIT},"tree":{"expected":lock.get("treeDigest","git:").removeprefix("git:"),"actual":tree,"ok":tree==lock.get("treeDigest","git:").removeprefix("git:")},"plaintextEnv":{"expected":False,"actual":(rt/".env").exists(),"ok":not (rt/".env").exists()},"workingTree":{"expected":[],"actual":dirty,"ok":not dirty},"sourceSymlinks":{"expected":[],"actual":unsafe_links,"ok":not unsafe_links},"escapingDependencySymlinks":{"expected":[],"actual":escaping_links,"ok":not escaping_links}}
 if marker: checks["sourceDigest"]={"expected":marker.get("sourceDigest"),"actual":source_digest(rt),"ok":bool(marker.get("sourceDigest")) and source_digest(rt)==marker.get("sourceDigest")}
 pylock=package/deps.get("pythonLock",{}).get("path","requirements.lock"); npmlock=rt/deps.get("npmLock",{}).get("path","remotion-composer/package-lock.json")
 checks["pythonLock"]={"expected":deps.get("pythonLock",{}).get("digest"),"actual":file_sha(pylock) if pylock.exists() else None,"ok":pylock.exists() and file_sha(pylock)==deps.get("pythonLock",{}).get("digest")}
 checks["npmLock"]={"expected":deps.get("npmLock",{}).get("digest"),"actual":file_sha(npmlock) if npmlock.exists() else None,"ok":npmlock.exists() and file_sha(npmlock)==deps.get("npmLock",{}).get("digest")}
 checks["pythonRuntime"]={"expected":True,"actual":(rt/".clawpod-venv/bin/python").exists(),"ok":(rt/".clawpod-venv/bin/python").exists()}
 checks["nodeRuntime"]={"expected":True,"actual":(rt/"remotion-composer/node_modules").is_dir(),"ok":(rt/"remotion-composer/node_modules").is_dir()}
 for item in lock.get("patches",[]):
  p=Path(__file__).parent/item["path"]; checks["patch:"+item["id"]]={"expected":item["sha256"],"actual":file_sha(p) if p.exists() else None,"ok":p.exists() and file_sha(p)==item["sha256"]}
 for item in lock.get("patchedFiles",[]):
  p=rt/item["path"]; checks["file:"+item["path"]]={"expected":item["sha256"],"actual":file_sha(p) if p.exists() else None,"ok":p.exists() and file_sha(p)==item["sha256"]}
 valid=all(c["ok"] for c in checks.values())
 return {"valid":valid,"runtimePath":str(rt),"checks":checks,"pipelineCount":len(list((rt/"pipeline_defs").glob("*.yaml")))}
def require_valid_runtime(x=None):
 v=validate_runtime(x)
 if not v["valid"]: raise E("DIGEST_MISMATCH","pinned runtime validation failed",category="digest",exit_code=9,details=v)
 return Path(v["runtimePath"]),v

def pipeline_contract(rt,pid):
 f=rt/"pipeline_defs"/(pid+".yaml")
 if not f.exists(): raise E("NOT_FOUND","pipeline manifest not found",exit_code=3)
 try: doc=yaml.safe_load(f.read_text())
 except Exception as exc: raise E("UPSTREAM_CONTRACT_INVALID","pipeline manifest YAML is invalid",category="contract",details={"type":type(exc).__name__})
 if not isinstance(doc,dict) or doc.get("name")!=pid or not isinstance(doc.get("stages"),list): raise E("UPSTREAM_CONTRACT_INVALID","pipeline manifest structure is invalid",category="contract")
 stages=[]
 for raw in doc["stages"]:
  if not isinstance(raw,dict) or not isinstance(raw.get("name"),str): raise E("UPSTREAM_CONTRACT_INVALID","pipeline stage is malformed",category="contract")
  tools=[]
  for key in ("tools_available","required_tools","optional_tools"):
   vals=raw.get(key,[]); tools.extend(vals if isinstance(vals,list) else [])
  sub=[]
  for item in raw.get("sub_stages",[]) or []:
   if isinstance(item,dict):
    subtools=item.get("tools_available",[]) if isinstance(item.get("tools_available",[]),list) else []; tools.extend(subtools); sub.append({"name":item.get("name"),"tools":sorted(set(subtools)),"humanApprovalDefault":bool(item.get("human_approval_default",False))})
  stages.append({"name":raw["name"],"skill":raw.get("skill"),"tools":sorted(set(z for z in tools if isinstance(z,str))),"requiredArtifacts":raw.get("required_artifacts_in",[]) or [],"optionalArtifacts":raw.get("optional_artifacts_in",[]) or [],"produces":raw.get("produces",[]) or [],"checkpointRequired":bool(raw.get("checkpoint_required",False)),"humanApprovalDefault":bool(raw.get("human_approval_default",False)),"subStages":sub})
 return {"manifest":str(f.relative_to(rt)),"manifestDigest":file_sha(f),"stages":stages,"stageCount":len(stages),"orchestration":doc.get("orchestration",{}),"defaultCheckpointPolicy":doc.get("default_checkpoint_policy")}


def resolve_secrets(provider,bindings):
 values={}; missing=[]
 for field in PROVIDERS[provider].get("fields",[]):
  b=bindings.get(field,{}) if isinstance(bindings,dict) else {}
  source=b.get("source","environment") if isinstance(b,dict) else "environment"
  env_name=b.get("environment",field) if isinstance(b,dict) else field
  file_name=b.get("fileEnvironment",field+"_FILE") if isinstance(b,dict) else field+"_FILE"
  if source not in ("environment","file"): raise E("INVALID_ARGUMENT","secret source must be environment or file")
  if source=="environment" and os.getenv(env_name): values[field]=os.environ[env_name]
  elif source=="file" and os.getenv(file_name):
   p=Path(os.environ[file_name]); mode=stat.S_IMODE(p.stat().st_mode) if p.is_file() else -1
   if mode!=0o600: raise E("SECRET_FILE_PERMISSIONS","secret file must be mode 0600",category="auth",exit_code=5)
   values[field]=p.read_text().rstrip("\r\n")
  else: missing.append(field)
 if missing: raise E("AUTH_REQUIRED","required injected secret is missing",category="auth",exit_code=5,details={"missing":missing})
 return values

LOCAL_EXECUTABLES={"ffprobe":"ffprobe","ffmpeg":"ffmpeg"}
def upstream_python(rt): return str(rt/".clawpod-venv/bin/python") if (rt/".clawpod-venv/bin/python").exists() else sys.executable

def registry_call(rt,request,timeout=90,cancel_file=None,secret_values=None,cancel_nonce=None):
 runner=Path(__file__).parent/"openmontage_runner.py"
 env={k:v for k,v in os.environ.items() if not SECRET_RE.search(k)}
 env["OPENMONTAGE_RUNTIME"]=str(rt); env.update(secret_values or {})
 start=time.monotonic(); p=subprocess.Popen([upstream_python(rt),str(runner)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,start_new_session=True)
 assert p.stdin is not None; p.stdin.write(stable(request)); p.stdin.close()
 try:
  while p.poll() is None:
   if cancel_file and cancel_file.exists() and cancel_file.read_text(errors="ignore")==cancel_nonce: os.killpg(p.pid,signal.SIGTERM); raise E("CANCELLED","tool cancelled",category="cancel",exit_code=10)
   if time.monotonic()-start>timeout: os.killpg(p.pid,signal.SIGTERM); raise E("TIMEOUT","tool exceeded timeout",category="timeout",retryable=True,exit_code=10)
   time.sleep(.05)
  out=p.stdout.read() if p.stdout else ""; err=p.stderr.read() if p.stderr else ""
 except E:
  try: p.wait(timeout=2)
  except subprocess.TimeoutExpired: os.killpg(p.pid,signal.SIGKILL)
  raise
 try: result=json.loads(out)
 except Exception: raise E("UPSTREAM_PROTOCOL_ERROR","OpenMontage runner returned invalid JSON",category="upstream",details={"exitCode":p.returncode},exit_code=7)
 if p.returncode or not result.get("ok"):
  code=result.get("error",{}).get("code","UPSTREAM_TOOL_FAILED")
  raise E(code,"OpenMontage tool operation failed",category="upstream",details={"exitCode":p.returncode,"error":result.get("error",{})},exit_code=7)
 return result.get("data",{}),round(time.monotonic()-start,3)

def tool_spec(rt,name):
 if name in LOCAL_EXECUTABLES:
  path=shutil.which(LOCAL_EXECUTABLES[name])
  if not path: raise E("RUNTIME_NOT_FOUND","local executable unavailable",exit_code=8)
  return {"name":name,"runtime":"local","provider":"local","executable":path}
 info,_=registry_call(rt,{"operation":"inspect","tool":name})
 return info

def verify_provider(provider,secrets):
 if provider not in VERIFY_ADAPTERS: raise E("VERIFIER_UNAVAILABLE","no reviewed non-billable verification endpoint adapter is registered",category="provider",exit_code=8,details={"provider":provider,"billingAttempted":False})
 url,headers=VERIFY_ADAPTERS[provider]; req=urllib.request.Request(url,headers={**headers(secrets),"Accept":"application/json","User-Agent":"ClawPod-Video-Studio/"+VERSION})
 try:
  with urllib.request.urlopen(req,timeout=10) as response:
   body=response.read(250_000); status=response.status
 except urllib.error.HTTPError as exc:
  if exc.code in (401,403): raise E("AUTH_INVALID","provider rejected the injected credential",category="auth",exit_code=5,details={"provider":provider,"httpStatus":exc.code,"billingAttempted":False})
  raise E("PROVIDER_UNAVAILABLE","provider verification endpoint failed",category="provider",retryable=exc.code in (408,409,425,429) or exc.code>=500,exit_code=7,details={"provider":provider,"httpStatus":exc.code,"billingAttempted":False})
 except (urllib.error.URLError,TimeoutError): raise E("PROVIDER_UNAVAILABLE","provider verification endpoint is unreachable",category="provider",retryable=True,exit_code=7,details={"provider":provider,"billingAttempted":False})
 try: parsed=json.loads(body)
 except Exception: parsed=None
 summary={"responseType":type(parsed).__name__,"itemCount":len(parsed) if isinstance(parsed,list) else len(parsed.get("data",[])) if isinstance(parsed,dict) and isinstance(parsed.get("data"),list) else None}
 return {"provider":provider,"status":"connected","verification":{"adapter":"non-billable-read","httpStatus":status,"billingAttempted":False,"summary":summary,"verifiedAt":now()}}

def canonical_tool_provider(info,name):
 provider=TOOL_PROVIDER_OVERRIDES.get(name,TOOL_PROVIDER_ALIASES.get(info.get("provider"),info.get("provider")))
 return None if provider in (None,"local","ffmpeg","ffprobe","openmontage","multi","selector") else provider

def run_tool(rt,spec,cancel_file=None,secret_values=None,cancel_nonce=None):
 name=spec.get("tool"); inp=spec.get("input",{}); timeout=min(max(float(spec.get("timeoutSeconds",60)),0.1),3600)
 if not isinstance(inp,dict): raise E("INVALID_ARGUMENT","tool input must be object")
 info=tool_spec(rt,name); start=time.monotonic()
 if name=="ffprobe":
  argv=[info["executable"],"-v","error","-show_format","-show_streams","-of","json",str(Path(inp.get("path","")))]
 elif name=="ffmpeg":
  args=inp.get("args",[])
  if not isinstance(args,list) or not all(isinstance(z,str) for z in args) or any(SECRET_RE.search(z) for z in args): raise E("INVALID_ARGUMENT","ffmpeg args must be a secret-free string list")
  forbidden_protocol=re.compile(r"(?:^|[=,;])(?:file|concat|subfile|crypto|http|https|tcp|udp|srt|rtmp|rtsp):",re.I)
  if any(Path(z).is_absolute() or ".." in Path(z).parts or "://" in z or forbidden_protocol.search(z) for z in args): raise E("PATH_VIOLATION","ffmpeg argv may use only project-relative paths and protocol-free local filter expressions")
  argv=[info["executable"],"-nostdin","-hide_banner",*args]
 else:
  result,duration=registry_call(rt,{"operation":"run","tool":name,"input":inp},timeout,cancel_file,secret_values,cancel_nonce)
  return {"tool":name,"exitCode":0,"durationSeconds":duration,"result":result,"upstream":info}
 env={k:v for k,v in os.environ.items() if not SECRET_RE.search(k)}
 p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,cwd=spec.get("_projectPath"),start_new_session=True)
 try:
  while p.poll() is None:
   if cancel_file and cancel_file.exists() and cancel_file.read_text(errors="ignore")==cancel_nonce: os.killpg(p.pid,signal.SIGTERM); raise E("CANCELLED","tool cancelled",category="cancel",exit_code=10)
   if time.monotonic()-start>timeout: os.killpg(p.pid,signal.SIGTERM); raise E("TIMEOUT","tool exceeded timeout",category="timeout",retryable=True,exit_code=10)
   time.sleep(.05)
  out=p.stdout.read() if p.stdout else ""; err=p.stderr.read() if p.stderr else ""
 except E:
  try: p.wait(timeout=2)
  except subprocess.TimeoutExpired: os.killpg(p.pid,signal.SIGKILL)
  raise
 if p.returncode: raise E("UPSTREAM_TOOL_FAILED","local tool failed",category="upstream",details={"exitCode":p.returncode,"output":redact((out+"\n"+err)[-MAX_LOG:])},exit_code=7)
 try: result=json.loads(out)
 except Exception: result={"stdout":redact(out[-MAX_LOG:]),"stderr":redact(err[-MAX_LOG:])}
 return {"tool":name,"exitCode":0,"durationSeconds":round(time.monotonic()-start,3),"result":result,"upstream":info}

PATH_FIELD_RE=re.compile(r"(?:path|dir|directory|file|filename)$",re.I)
def has_path_fields(value):
 if isinstance(value,dict): return any(PATH_FIELD_RE.search(k) or has_path_fields(v) for k,v in value.items() if isinstance(k,str))
 if isinstance(value,list): return any(has_path_fields(v) for v in value)
 return False
def bound_tool_input(project,inputs,materialize=False):
 def walk(value,key=""):
  if isinstance(value,dict): return {k:walk(v,k) for k,v in value.items()}
  if isinstance(value,list): return [walk(v,key) for v in value]
  if isinstance(value,str) and PATH_FIELD_RE.search(key):
   target=child(project,value,exist=not key.lower().startswith(("output","destination","target")))
   return str(target) if materialize else str(target.relative_to(project))
  return value
 return walk(inputs)

def confine_result_artifacts(result,project):
 payload=result.get("result",{}) if isinstance(result,dict) else {}; confined=[]
 for raw in payload.get("artifacts",[]) if isinstance(payload,dict) else []:
  if not project or not isinstance(raw,str): continue
  candidate=Path(raw); candidate=candidate if candidate.is_absolute() else project/candidate
  try:
   resolved=candidate.resolve(strict=True)
   if project not in resolved.parents or resolved.is_symlink() or not resolved.is_file(): continue
   confined.append({"relativePath":str(resolved.relative_to(project)),"sha256":secure_file_sha(resolved),"bytes":resolved.stat().st_size})
  except (OSError,ValueError): continue
 if isinstance(payload,dict): payload["artifacts"]=confined
 return result

def qa_media(f):
 probe=shutil.which("ffprobe")
 if not probe: raise E("RUNTIME_NOT_FOUND","ffprobe is required for media QA",exit_code=8)
 p=subprocess.run([probe,"-v","error","-show_format","-show_streams","-of","json",str(f)],text=True,capture_output=True,timeout=30)
 if p.returncode: return {"status":"failed","checks":{"container":{"passed":False,"detail":p.stderr[-1000:]}}}
 meta=json.loads(p.stdout); streams=meta.get("streams",[]); video=[s for s in streams if s.get("codec_type")=="video"]; audio=[s for s in streams if s.get("codec_type")=="audio"]; subs=[s for s in streams if s.get("codec_type")=="subtitle"]
 ffmpeg=shutil.which("ffmpeg"); frame_decode=False; audio_decode=None
 if ffmpeg and video:
  frame_decode=subprocess.run([ffmpeg,"-v","error","-i",str(f),"-map","0:v:0","-frames:v","1","-f","null","-"],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=30).returncode==0
 if ffmpeg and audio:
  audio_decode=subprocess.run([ffmpeg,"-v","error","-i",str(f),"-map","0:a:0","-t","1","-f","null","-"],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=30).returncode==0
 duration=float(meta.get("format",{}).get("duration") or 0); checks={"container":{"passed":bool(meta.get("format",{}).get("format_name"))},"duration":{"passed":duration>0,"seconds":duration},"video":{"passed":bool(video),"streams":len(video),"width":video[0].get("width") if video else None,"height":video[0].get("height") if video else None},"frames":{"passed":frame_decode,"decoded":frame_decode},"audio":{"passed":audio_decode if audio else False,"streams":len(audio),"decoded":audio_decode},"subtitles":{"passed":bool(subs),"streams":len(subs)},"delivery":{"passed":f.suffix.lower() in (".mp4",".mov",".mkv",".webm") and f.stat().st_size>0}}
 required=("container","duration","video","frames","delivery"); return {"status":"passed" if all(checks[k]["passed"] for k in required) else "failed","checks":checks,"metadata":meta}

def worker(r,jid,nonce):
 jp=job_path(r,jid); startp=jp.with_suffix(".start"); deadline=time.monotonic()+5
 while time.monotonic()<deadline and (not startp.exists() or startp.read_text(errors="ignore")!=nonce): time.sleep(.01)
 if not startp.exists() or startp.read_text(errors="ignore")!=nonce: return 13
 job=readj(jp); lp=jp.with_suffix(".log"); cp=jp.with_suffix(".checkpoint.json"); cancel=jp.with_suffix(".cancel")
 if not job or job.get("ownerNonce")!=nonce: return 13
 def save(**kw):
  with state_lock(jp.with_suffix(".lock")):
   current=readj(jp,job) or job; current.update(kw); current["heartbeatAt"]=now(); job.clear(); job.update(current); atomic(jp,job)
 try:
  rt,_=require_valid_runtime(job.get("runtimeInput",{})); save(state="running",ownedPid=os.getpid())
  intent=job.get("intentSnapshot")
  if not isinstance(intent,dict) or verified_intent_digest(intent)!=job.get("intentDigest"): raise E("DIGEST_MISMATCH","immutable job intent snapshot is invalid",category="digest",exit_code=9)
  ops=intent.get("operations",[]); completed=readj(cp,{"completed":0}).get("completed",0)
  for i,op in enumerate(ops[completed:],completed):
   if cancel.exists() and cancel.read_text(errors="ignore")==nonce: save(state="cancelled",finishedAt=now(),ownedPid=None,ownerStartIdentity=None); return 0
   save(stage=(op.get("stage") if isinstance(op,dict) else str(op)),progress={"completed":i,"total":len(ops),"percent":round(100*i/max(1,len(ops)),1)})
   with lp.open("a") as log: log.write(stable(redact({"at":now(),"event":"stage_start","index":i,"operation":op}))+"\n")
   if isinstance(op,dict) and op.get("checkpoint"):
    gate=readj(project_dir(r,job["projectId"])/"checkpoint.json",{}) or {}
    expected_gate_job=job.get("resumedFrom") if job.get("resumeCheckpointStage")==op["checkpoint"] else job["jobId"]
    gate_valid=gate.get("status")=="completed" and gate.get("stage")==op["checkpoint"] and gate.get("jobId")==expected_gate_job and gate.get("intentDigest")==job["intentDigest"]
    if gate_valid:
     try: require_future_expiry(gate.get("approvalExpiresAt"))
     except E: gate_valid=False
    if not gate_valid:
     atomic(cp,{"completed":i,"planDigest":job["planDigest"],"intentDigest":job["intentDigest"],"updatedAt":now()}); save(state="awaiting_human",stage=op["checkpoint"],progress={"completed":i,"total":len(ops),"percent":round(100*i/max(1,len(ops)),1)},ownedPid=None,ownerStartIdentity=None); return 0
   if isinstance(op,dict) and op.get("tool"):
    work_project=project_dir(r,job["projectId"]); op={**op,"input":bound_tool_input(work_project,op.get("input",{}),True),"_projectPath":str(work_project)}
    secret_values={}; provider=op.get("provider")
    cost_path=project_dir(r,job["projectId"])/"cost.json"; costs=readj(cost_path,{"estimatedUsd":job.get("maximumAuthorizedUsd",0),"actualUsd":0,"maximumAuthorizedUsd":job.get("maximumAuthorizedUsd",0),"entries":[]}); remaining=round(float(job.get("maximumAuthorizedUsd",0))-float(costs.get("actualUsd",0)),6)
    if provider:
     require_future_expiry(job.get("approvalExpiresAt")); op_ceiling=float(op.get("maximumUsd",0))
     if op_ceiling<=0 or op_ceiling>remaining: raise E("COST_CEILING_EXCEEDED","insufficient remaining authorization for provider operation",category="cost",details={"remainingAuthorizedUsd":remaining,"operationMaximumUsd":op_ceiling,"sideEffectOccurred":False},exit_code=11)
     con=readj(r/"connections.json",{}) or {}
     if provider not in con: raise E("AUTH_REQUIRED","operation provider is not configured",category="auth",exit_code=5)
     secret_values=resolve_secrets(provider,con[provider].get("bindings",{}))
    tool_result=confine_result_artifacts(run_tool(rt,op,cancel,secret_values,nonce),work_project); actual=float(tool_result.get("result",{}).get("cost_usd",0) or 0)
    costs["actualUsd"]=round(float(costs.get("actualUsd",0))+actual,6); costs["entries"].append({"at":now(),"tool":op["tool"],"provider":provider,"model":op.get("model"),"operationDigest":sha(op),"actualUsd":actual,"artifacts":tool_result.get("result",{}).get("artifacts",[])}); atomic(cost_path,costs)
    if costs["actualUsd"]>float(job.get("maximumAuthorizedUsd",0)): raise E("COST_CEILING_EXCEEDED","provider-reported cost exceeds the exact job ceiling",category="cost",details={"actualUsd":costs["actualUsd"],"maximumAuthorizedUsd":job.get("maximumAuthorizedUsd",0),"sideEffectOccurred":True},exit_code=11)
   atomic(cp,{"completed":i+1,"planDigest":job["planDigest"],"intentDigest":job["intentDigest"],"updatedAt":now()})
  save(state="succeeded",progress={"completed":len(ops),"total":len(ops),"percent":100},finishedAt=now(),ownedPid=None,ownerStartIdentity=None); return 0
 except E as e:
  save(state="cancelled" if e.code=="CANCELLED" else "failed",finishedAt=now(),ownedPid=None,ownerStartIdentity=None,lastError={"code":e.code,"message":e.msg,"details":redact(e.details)}); return e.exit_code
 except Exception as e: save(state="failed",finishedAt=now(),ownedPid=None,ownerStartIdentity=None,lastError={"code":"INTERNAL_ERROR","type":type(e).__name__}); return 12

def handler(cmd,a,x):
 r=root(a)
 if not x.get("runtimePath") and (r/"runtime").is_dir(): x={**x,"runtimePath":str(r/"runtime")}
 if cmd=="system.version": return {"capabilityVersion":VERSION,"upstreamCommit":UPSTREAM_COMMIT,"schemaVersion":"1.0"},[]
 if cmd=="system.preflight":
  rt=runtime(x,False); deps={n:{"ok":bool(shutil.which(n)),"path":shutil.which(n)} for n in ("git","node","ffmpeg","ffprobe")}; deps["python"]={"ok":sys.version_info>=(3,10),"version":sys.version.split()[0]}
  validation=validate_runtime(x) if rt else {"valid":False,"runtimePath":None}; return {"readyLocal":all(v["ok"] for v in deps.values()) and validation["valid"],"dependencies":deps,"runtime":validation,"stateRoot":str(r)},[]
 if cmd=="system.validate":
  _,v=require_valid_runtime(x); contracts={p[0]:pipeline_contract(Path(v["runtimePath"]),p[0]) for p in PIPELINES}; return {**v,"pipelines":contracts,"localPatches":["openmontage-documentary-category"]},[]
 if cmd.startswith("pipeline."):
  rt,v=require_valid_runtime(x); items=[{"id":n,"stability":s,"category":c,"contractValid":True,**pipeline_contract(rt,n)} for n,s,c in PIPELINES]
  if cmd=="pipeline.list": return {"items":items,"count":len(items)},[]
  pid=x.get("pipelineId") or a.pipeline_id; item=next((z for z in items if z["id"]==pid),None)
  if not item: raise E("NOT_FOUND","pipeline not found",exit_code=3)
  return item,[]
 if cmd.startswith("provider."):
  con=readj(r/"connections.json",{}) or {}; items=[{"provider":k,**v,"connectionState":con.get(k,{}).get("status","deferred"),"verificationAdapter":"keyless-local" if k=="keyless" else "non-billable-read" if k in VERIFY_ADAPTERS else "unavailable"} for k,v in PROVIDERS.items()]
  if cmd=="provider.summary":
   connected=sum(i["connectionState"]=="connected" for i in items); return {"total":len(items),"connected":connected,"installedButNotConnected":connected==0},[]
  if cmd=="provider.inspect":
   z=next((i for i in items if i["provider"]==(x.get("provider") or a.provider)),None)
   if not z: raise E("NOT_FOUND","provider not found",exit_code=3)
   return z,[]
  return {"items":items,"count":len(items)},[]
 if cmd=="connection.list": return {"items":[{"provider":k,**v} for k,v in (readj(r/"connections.json",{}) or {}).items()]},[]
 if cmd=="connection.configure":
  provider=x.get("provider") or a.provider
  if provider not in PROVIDERS: raise E("INVALID_ARGUMENT","unknown provider")
  b=x.get("bindings",{});
  if not isinstance(b,dict): raise E("INVALID_ARGUMENT","bindings must be object")
  allowed=set(PROVIDERS[provider].get("fields",[])+PROVIDERS[provider].get("optional",[])); clean={}
  for field,v in b.items():
   if field not in allowed or not isinstance(v,dict): raise E("INVALID_ARGUMENT",f"{field} must use protected secret-pointer metadata")
   ptr=v.get("pointerId"); source=v.get("source","environment")
   if not isinstance(ptr,str) or not re.fullmatch(r"(?:secret|memsec|ptr)[A-Za-z0-9:_-]{6,180}",ptr): raise E("INVALID_ARGUMENT",f"{field} must reference a protected secret pointer")
   if source not in ("environment","file"): raise E("INVALID_ARGUMENT","secret source must be environment or file")
   permitted={"pointerId","source","environment"} if source=="environment" else {"pointerId","source","fileEnvironment"}
   if set(v)-permitted: raise E("INVALID_ARGUMENT","only pointer and injection metadata are allowed")
   clean[field]={"pointerId":ptr,"source":source,"status":"configured_unverified"}
   if source=="environment": clean[field]["environment"]=v.get("environment",field)
   else: clean[field]["fileEnvironment"]=v.get("fileEnvironment",field+"_FILE")
  missing=sorted(set(PROVIDERS[provider].get("fields",[]))-set(clean)); con=readj(r/"connections.json",{}) or {}; con[provider]={"status":"missing_companion_field" if missing else "configured_unverified","bindings":clean,"missing":missing,"updatedAt":now()}; atomic(r/"connections.json",con); return {"provider":provider,**con[provider]},[]
 if cmd=="connection.verify":
  provider=x.get("provider") or a.provider; con=readj(r/"connections.json",{}) or {}
  if provider=="keyless":
   result={"provider":"keyless","status":"connected","verification":{"adapter":"local-binary-presence","billable":False,"ffmpeg":bool(shutil.which("ffmpeg")),"ffprobe":bool(shutil.which("ffprobe"))}}; con[provider]={"status":"connected","bindings":{},"lastVerifiedAt":now(),"verificationAdapter":"local-binary-presence"}; atomic(r/"connections.json",con); return result,[]
  if not x.get("approvalReference"): raise E("APPROVAL_REQUIRED","provider verification requires separate secret-use and network-read approval",category="approval",exit_code=6)
  if provider not in con or not con[provider].get("bindings"): raise E("AUTH_REQUIRED","provider not configured",category="auth",exit_code=5)
  try: result=verify_provider(provider,resolve_secrets(provider,con[provider].get("bindings",{})))
  except E as e:
   if e.code=="AUTH_INVALID": con[provider].update(status="invalid",lastVerificationError="AUTH_INVALID",lastVerifiedAt=now()); atomic(r/"connections.json",con)
   raise
  con[provider].update(status="connected",lastVerifiedAt=now(),verificationAdapter=result["verification"]["adapter"]); atomic(r/"connections.json",con); return result,[]
 if cmd=="connection.revoke":
  if x.get("confirm")!="remove-binding": raise E("APPROVAL_REQUIRED","confirm=remove-binding required",category="approval",exit_code=6)
  con=readj(r/"connections.json",{}) or {}; provider=x.get("provider") or a.provider; old=con.get(provider); con[provider]={"status":"revoked","bindings":{},"revokedAt":now(),"secretDeleted":False}; atomic(r/"connections.json",con); return {"provider":provider,"removed":bool(old),"status":"revoked","secretDeleted":False},[]
 if cmd=="project.create":
  pid=x.get("projectId") or a.project_id; rt,_=require_valid_runtime(x); pipeline=x.get("pipelineId"); pipeline_contract(rt,pipeline); p=project_dir(r,pid); cur=readj(p/"project.json"); intent={"projectId":pid,"pipelineId":pipeline,"title":x.get("title",pid)}; dig=sha(intent)
  if cur:
   if x.get("idempotencyKey") and cur.get("idempotencyKey")==x["idempotencyKey"] and cur["inputDigest"]==dig: return cur,[]
   raise E("CONFLICT","project exists",exit_code=4)
  p.mkdir(parents=True); [child(p,z).mkdir(exist_ok=True) for z in ("artifacts","assets","renders","history")]; obj={**intent,"revision":1,"status":"created","createdAt":now(),"idempotencyKey":x.get("idempotencyKey"),"inputDigest":dig}; atomic(p/"project.json",obj); return obj,[]
 if cmd=="project.list":
  d=r/"projects"; d.mkdir(parents=True,exist_ok=True); return {"items":[readj(z/"project.json",{}) for z in d.iterdir() if z.is_dir() and (z/"project.json").exists()]},[]
 if cmd in ("project.inspect","project.validate"):
  p,o=get_project(r,x.get("projectId") or a.project_id); return ({"projectId":o["projectId"],"valid":all(child(p,z).is_dir() for z in ("artifacts","assets","renders","history")),"revision":o["revision"]} if cmd.endswith("validate") else o),[]
 if cmd=="project.plan":
  p,o=get_project(r,x.get("projectId") or a.project_id); plan=x.get("plan")
  if not isinstance(plan,dict): raise E("INVALID_ARGUMENT","plan object required")
  if x.get("expectedRevision",o["revision"])!=o["revision"]: raise E("CONFLICT","project revision changed",exit_code=4)
  rec={"plan":plan,"planDigest":sha(plan),"createdAt":now()}; atomic(p/"plan.json",rec); o.update(revision=o["revision"]+1,status="planned"); atomic(p/"project.json",o); return rec,[]
 if cmd.startswith("cost."):
  p,_=get_project(r,x.get("projectId") or a.project_id); return readj(p/"cost.json",{"estimatedUsd":0,"actualUsd":0,"maximumAuthorizedUsd":0,"entries":[]}),[]
 if cmd=="run.prepare":
  p,o=get_project(r,x.get("projectId") or a.project_id); plan=readj(p/"plan.json")
  if not plan: raise E("PLAN_MISSING","project plan is missing",exit_code=8)
  rt,v=require_valid_runtime(x); ops=x.get("operations",[])
  if not isinstance(ops,list): raise E("INVALID_ARGUMENT","operations must be list")
  contract=pipeline_contract(rt,o["pipelineId"]); stages={s["name"] for s in contract["stages"]}; normalized=[]; inferred_providers=set()
  for op in ops:
   if isinstance(op,str):
    if op not in stages: raise E("UPSTREAM_CONTRACT_INVALID","operation stage is not declared by the selected pipeline",category="contract",details={"stage":op})
    normalized.append(op); continue
   if isinstance(op,dict) and op.get("checkpoint"):
    if op.get("checkpoint") not in stages or set(op)!={"checkpoint"}: raise E("INVALID_ARGUMENT","checkpoint operation must name one declared stage")
    normalized.append({"checkpoint":op["checkpoint"]}); continue
   if not isinstance(op,dict) or not op.get("tool") or not isinstance(op.get("input",{}),dict): raise E("INVALID_ARGUMENT","each operation must be a declared stage, checkpoint, or typed tool operation")
   info=tool_spec(rt,op["tool"]); item=dict(op); item["input"]=bound_tool_input(p,item.get("input",{}),False)
   if info.get("runtime") in ("api","hybrid"):
    inferred=canonical_tool_provider(info,op["tool"])
    if item.get("provider") and inferred not in (None,"multi","selector") and item["provider"]!=inferred: raise E("UPSTREAM_CONTRACT_INVALID","operation provider does not match the pinned tool contract",category="contract")
    item["provider"]=item.get("provider") or inferred
    if not item.get("provider"): raise E("UPSTREAM_CONTRACT_INVALID","external tool does not declare a provider",category="contract")
   if item.get("provider"):
    item["maximumUsd"]=float(item.get("maximumUsd",0))
    if item["maximumUsd"]<=0: raise E("COST_CEILING_REQUIRED","every provider operation requires a positive maximumUsd",category="approval",exit_code=6)
    inferred_providers.add(item["provider"])
   normalized.append(item)
  declared=set(x.get("providers",[]))
  if inferred_providers-declared: raise E("APPROVAL_REQUIRED","all external operation providers must be declared before approval",category="approval",exit_code=6,details={"missingProviders":sorted(inferred_providers-declared)})
  maximum=float(x.get("maximumUsd",0)); reserved=sum(float(op.get("maximumUsd",0)) for op in normalized if isinstance(op,dict) and op.get("provider"))
  if reserved>maximum: raise E("COST_CEILING_EXCEEDED","operation ceilings exceed the prepared job ceiling",category="cost",exit_code=6,details={"reservedUsd":reserved,"maximumUsd":maximum})
  intent={"intentId":"intent-"+uuid.uuid4().hex[:16],"projectId":o["projectId"],"pipelineId":o["pipelineId"],"pipelineManifestDigest":contract["manifestDigest"],"planDigest":plan["planDigest"],"operations":normalized,"providers":sorted(declared),"maximumUsd":maximum,"runtimeDigest":sha(v["checks"]),"createdAt":now()}; intent["inputDigest"]=sha(intent); atomic(p/"intent.json",intent); return intent,[]
 if cmd in ("run.start","run.resume"):
  p,o=get_project(r,x.get("projectId") or a.project_id); resume_checkpoint=None; old=None; resume_lock=None
  if cmd=="run.resume":
   if not x.get("jobId"): raise E("INVALID_ARGUMENT","run.resume requires the prior jobId")
   oldp=job_path(r,x["jobId"]); old=readj(oldp)
   if not old or old.get("state") not in ("awaiting_human","failed","cancelled"): raise E("CONFLICT","prior job is not in a resumable terminal state",exit_code=4)
   if old.get("ownedPid") and owned_process_alive(old["ownedPid"],old.get("ownerStartIdentity")): raise E("CONFLICT","prior worker is still alive",exit_code=4)
   intent=old.get("intentSnapshot"); resume_checkpoint=readj(oldp.with_suffix(".checkpoint.json")); resume_lock=oldp.with_suffix(".resume.lock")
   if not isinstance(intent,dict) or not resume_checkpoint: raise E("CONFLICT","no immutable resumable checkpoint exists",exit_code=4)
   try: fd=os.open(resume_lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.write(fd,b"claimed"); os.close(fd)
   except FileExistsError: raise E("CONFLICT","checkpoint already has a resume descendant",exit_code=4)
  else: intent=readj(p/"intent.json")
  try:
   if not intent: raise E("INTENT_MISSING","prepared intent missing",exit_code=8)
   intent_digest=verified_intent_digest(intent)
   if x.get("intentId")!=intent["intentId"] or x.get("planDigest")!=intent["planDigest"]: raise E("APPROVAL_REQUIRED","prepared intent changed",category="approval",exit_code=6)
   if resume_checkpoint and (resume_checkpoint.get("planDigest")!=intent["planDigest"] or resume_checkpoint.get("intentDigest")!=intent_digest): raise E("CONFLICT","checkpoint does not match immutable intent",exit_code=4)
   external=bool(intent["maximumUsd"]>0 or intent["providers"]); approval_expiry=None; binding=None
   if external:
    if not x.get("approvalReference") or float(x.get("maximumAuthorizedUsd",-1))!=float(intent["maximumUsd"]): raise E("APPROVAL_REQUIRED","exact external execution approval required",category="approval",exit_code=6)
    approval_expiry=require_future_expiry(x.get("approvalExpiresAt")); binding=approval_binding_digest(intent_digest,intent["providers"],intent["operations"],intent["maximumUsd"],x["approvalReference"],approval_expiry)
    if x.get("approvalBindingDigest")!=binding: raise E("APPROVAL_REQUIRED","approval binding digest does not match the exact intent",category="approval",exit_code=6,details={"expectedApprovalBindingDigest":binding})
   con=readj(r/"connections.json",{}) or {}
   for provider in intent["providers"]:
    if provider not in PROVIDERS or provider not in con: raise E("AUTH_REQUIRED","prepared provider is not configured",category="auth",exit_code=5,details={"provider":provider})
    resolve_secrets(provider,con[provider].get("bindings",{}))
   rt,_=require_valid_runtime(x); jid="job-"+uuid.uuid4().hex[:16]; nonce=uuid.uuid4().hex; job={"jobId":jid,"projectId":o["projectId"],"planDigest":intent["planDigest"],"intentDigest":intent_digest,"intentSnapshot":intent,"state":"queued","stage":None,"progress":{"completed":resume_checkpoint.get("completed",0) if resume_checkpoint else 0,"total":len(intent["operations"]),"percent":round(100*resume_checkpoint.get("completed",0)/max(1,len(intent["operations"])),1) if resume_checkpoint else 0},"heartbeatAt":now(),"startedAt":now(),"finishedAt":None,"ownerNonce":nonce,"ownedPid":None,"runtimeInput":{"runtimePath":str(rt)},"maximumAuthorizedUsd":intent["maximumUsd"],"approvalReference":x.get("approvalReference"),"approvalExpiresAt":approval_expiry,"approvalBindingDigest":binding,"resumedFrom":x.get("jobId") if resume_checkpoint else None,"resumeCheckpointStage":old.get("stage") if old and old.get("state")=="awaiting_human" else None,"lastError":None}; jp=job_path(r,jid); jp.parent.mkdir(parents=True,exist_ok=True); atomic(jp,job)
   if resume_checkpoint: atomic(jp.with_suffix(".checkpoint.json"),resume_checkpoint)
   proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"_worker","--root",str(r),"--job-id",jid,"--nonce",nonce],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True); job["ownedPid"]=proc.pid; job["ownerStartIdentity"]=process_start_identity(proc.pid); atomic(jp,job); startp=jp.with_suffix(".start"); fd,tmp=tempfile.mkstemp(prefix=".start-",dir=startp.parent); os.fchmod(fd,0o600); os.write(fd,nonce.encode()); os.close(fd); os.replace(tmp,startp); return job,[]
  except Exception:
   if resume_lock and resume_lock.exists(): resume_lock.unlink()
   raise
 if cmd in ("run.status","run.inspect"):
  j=readj(job_path(r,x.get("jobId") or a.job_id));
  if not j: raise E("NOT_FOUND","job not found",exit_code=3)
  if j["state"] in ("queued","running","cancel_requested") and j.get("ownedPid") and not owned_process_alive(j["ownedPid"],j.get("ownerStartIdentity")):
   jp=job_path(r,j["jobId"])
   with state_lock(jp.with_suffix(".lock")):
    j=readj(jp,j)
    if j["state"] in ("queued","running","cancel_requested") and j.get("ownedPid") and not owned_process_alive(j["ownedPid"],j.get("ownerStartIdentity")): j.update(state="failed",lastError={"code":"WORKER_LOST_OR_PID_REUSED"},finishedAt=now(),ownedPid=None,ownerStartIdentity=None); atomic(jp,j)
  return j,[]
 if cmd=="run.logs":
  jp=job_path(r,x.get("jobId") or a.job_id); text=jp.with_suffix(".log").read_text(errors="replace")[-MAX_LOG:] if jp.with_suffix(".log").exists() else ""; return {"jobId":jp.stem,"text":redact(text)},[]
 if cmd=="run.cancel":
  jp=job_path(r,x.get("jobId") or a.job_id)
  with state_lock(jp.with_suffix(".lock")):
   j=readj(jp)
   if not j: raise E("NOT_FOUND","job not found",exit_code=3)
   if j.get("state") in ("succeeded","failed","cancelled","awaiting_human"): return {**j,"cancelIdempotent":True},[]
   if x.get("confirm")!="cancel-job" or x.get("ownerNonce")!=j.get("ownerNonce"): raise E("APPROVAL_REQUIRED","confirm=cancel-job and matching ownerNonce required",category="approval",exit_code=6)
   cancelp=jp.with_suffix(".cancel"); fd,tmp=tempfile.mkstemp(prefix=".cancel-",dir=cancelp.parent); os.fchmod(fd,0o600); os.write(fd,j["ownerNonce"].encode()); os.close(fd); os.replace(tmp,cancelp); j["state"]="cancel_requested"; atomic(jp,j); return j,[]
 if cmd.startswith("checkpoint."):
  p,o=get_project(r,x.get("projectId") or a.project_id); cp=readj(p/"checkpoint.json",{"projectId":o["projectId"],"status":"in_progress","revision":0})
  if cmd=="checkpoint.inspect": return cp,[]
  action=cmd.split(".",1)[1]
  if action=="approve":
   required=("jobId","stage","relativePath","artifactDigest","approvalReference","approvalExpiresAt","approvalBindingDigest")
   if any(not x.get(k) for k in required): raise E("INVALID_ARGUMENT","checkpoint approval requires exact job, stage, artifact, reference, expiry, and binding digest")
   job=readj(job_path(r,x["jobId"]));
   if not job or job.get("projectId")!=o["projectId"] or job.get("state")!="awaiting_human" or job.get("stage")!=x["stage"]: raise E("CONFLICT","checkpoint does not match an awaiting job stage",exit_code=4)
   artifact=child(p,x["relativePath"],True); actual=secure_file_sha(artifact)
   if actual!=x["artifactDigest"]: raise E("DIGEST_MISMATCH","reviewed artifact digest does not match",category="digest",exit_code=9,details={"actual":actual})
   expiry=require_future_expiry(x["approvalExpiresAt"]); binding=checkpoint_approval_binding_digest(job["jobId"],job["intentDigest"],x["stage"],actual,x["approvalReference"],expiry)
   if x["approvalBindingDigest"]!=binding: raise E("APPROVAL_REQUIRED","checkpoint approval binding digest does not match",category="approval",exit_code=6,details={"expectedApprovalBindingDigest":binding})
   cp.update(status="completed",action=action,jobId=job["jobId"],intentDigest=job["intentDigest"],stage=x["stage"],relativePath=str(artifact.relative_to(p)),artifactDigest=actual,approvalReference=x["approvalReference"],approvalBindingDigest=binding,approvalExpiresAt=expiry,revision=cp["revision"]+1,updatedAt=now())
  else: cp.update(status="failed" if action=="fail" else "in_progress",action=action,jobId=x.get("jobId",cp.get("jobId")),stage=x.get("stage",cp.get("stage")),revision=cp["revision"]+1,updatedAt=now())
  atomic(p/"checkpoint.json",cp); return cp,[]
 if cmd.startswith("stage."):
  p,o=get_project(r,x.get("projectId") or a.project_id); rt,_=require_valid_runtime(x); contract=pipeline_contract(rt,o["pipelineId"]); stage=x.get("stage"); info=next((z for z in contract["stages"] if z["name"]==stage),None)
  if not info: raise E("INVALID_ARGUMENT","stage not declared by pipeline")
  if cmd=="stage.prepare": return {"projectId":o["projectId"],"stage":stage,"upstreamContract":info,"manifestDigest":contract["manifestDigest"]},[]
  if cmd=="stage.validate": return {"valid":isinstance(x.get("artifact"),dict),"stage":stage,"upstreamContract":info},[]
  if not isinstance(x.get("artifact"),dict): raise E("INVALID_ARGUMENT","artifact object required")
  ap=child(p,"artifacts/"+stage+".json"); atomic(ap,x["artifact"]); return {"relativePath":str(ap.relative_to(p)),"sha256":file_sha(ap),"stage":stage},[]
 if cmd.startswith("tool."):
  rt,_=require_valid_runtime(x); info=tool_spec(rt,x.get("tool")); runtime_kind=info.get("runtime","local"); inferred_provider=canonical_tool_provider(info,x.get("tool")) if runtime_kind in ("api","hybrid") else None
  if x.get("provider") and inferred_provider not in (None,"multi","selector") and x["provider"]!=inferred_provider: raise E("UPSTREAM_CONTRACT_INVALID","provider does not match the pinned tool contract",category="contract")
  provider=x.get("provider") or inferred_provider
  if runtime_kind in ("api","hybrid") and not provider: raise E("INVALID_ARGUMENT","multi-provider tool requires an explicit configured provider")
  model=x.get("model") or (x.get("input",{}).get("model") if isinstance(x.get("input",{}),dict) else None)
  project_id=x.get("projectId") or a.project_id; project=None
  if has_path_fields(x.get("input",{})):
   if not project_id: raise E("INVALID_ARGUMENT","path-bearing tool input requires projectId")
   project,_=get_project(r,project_id)
  bounded_input=bound_tool_input(project,x.get("input",{}),False) if project else x.get("input",{})
  spec={"tool":x.get("tool"),"projectId":project_id,"input":bounded_input,"provider":provider,"model":model,"operation":x.get("operation","execute"),"maximumUsd":float(x.get("maximumUsd",0)),"timeoutSeconds":x.get("timeoutSeconds",60)}; dig=sha(spec); external=runtime_kind in ("api","hybrid") or bool(provider)
  if cmd=="tool.prepare":
   if runtime_kind=="api" and spec["maximumUsd"]<=0: raise E("COST_CEILING_REQUIRED","API tool requires a positive maximumUsd",category="approval",exit_code=6)
   return {"toolDigest":dig,**spec,"requiresApproval":external or bool(spec["maximumUsd"]),"upstreamContract":info},[]
  if x.get("toolDigest")!=dig: raise E("APPROVAL_REQUIRED","tool digest changed",category="approval",exit_code=6)
  secret_values={}
  if external:
   if not x.get("approvalReference") or float(x.get("maximumAuthorizedUsd",-1))!=spec["maximumUsd"]: raise E("APPROVAL_REQUIRED","exact external execution approval and cost ceiling required",category="approval",exit_code=6)
   expiry=require_future_expiry(x.get("approvalExpiresAt")); binding=tool_approval_binding_digest(dig,spec,x["approvalReference"],expiry)
   if x.get("approvalBindingDigest")!=binding: raise E("APPROVAL_REQUIRED","tool approval binding digest does not match",category="approval",exit_code=6,details={"expectedApprovalBindingDigest":binding})
   if provider not in PROVIDERS: raise E("INVALID_ARGUMENT","tool provider has no protected-secret mapping")
   con=readj(r/"connections.json",{}) or {}
   if provider not in con: raise E("AUTH_REQUIRED","provider is not configured",category="auth",exit_code=5)
   secret_values=resolve_secrets(provider,con[provider].get("bindings",{}))
  execution_spec={**spec,"input":bound_tool_input(project,spec["input"],True) if project else spec["input"],"_projectPath":str(project) if project else None}
  result=confine_result_artifacts(run_tool(rt,execution_spec,secret_values=secret_values),project); actual=float(result.get("result",{}).get("cost_usd",0) or 0); result["cost"]={"actualUsd":actual,"maximumAuthorizedUsd":spec["maximumUsd"],"withinCeiling":actual<=spec["maximumUsd"]}
  if actual>spec["maximumUsd"]: raise E("COST_CEILING_EXCEEDED","provider reported cost above approved ceiling",category="cost",details={"actualUsd":actual,"maximumAuthorizedUsd":spec["maximumUsd"],"sideEffectOccurred":True},exit_code=11)
  return result,[]
 if cmd in ("qa.run","qa.inspect"):
  p,_=get_project(r,x.get("projectId") or a.project_id); qp=p/"artifacts"/"qa.json"
  if cmd=="qa.inspect": return readj(qp,{"status":"not_run"}),[]
  f=child(p,x.get("relativePath"),True); result={**qa_media(f),"target":str(f.relative_to(p)),"sha256":file_sha(f),"updatedAt":now()}; atomic(qp,result); return result,[]
 if cmd.startswith("artifact."):
  p,o=get_project(r,x.get("projectId") or a.project_id); files=[]
  for d in ("artifacts","assets","renders"):
   for f in child(p,d).rglob("*"):
    if f.is_file() and not f.is_symlink(): files.append({"relativePath":str(f.relative_to(p)),"bytes":f.stat().st_size,"sha256":file_sha(f)})
  if cmd=="artifact.list": return {"items":files},[]
  f=child(p,x.get("relativePath"),True); item={"relativePath":str(f.relative_to(p)),"bytes":f.stat().st_size,"sha256":file_sha(f)}
  if cmd=="artifact.inspect": return item,[]
  out=child(p,x.get("output","artifacts/export-manifest.json")); atomic(out,{"projectId":o["projectId"],"items":files,"createdAt":now()}); return {"relativePath":str(out.relative_to(p)),"items":len(files)},[]
 if cmd.startswith("backlot."):
  sf=r/"backlot.json"; s=readj(sf,{"running":False,"ownedPid":None,"ownerNonce":None,"ownerStartIdentity":None,"url":None})
  if s.get("ownedPid") and not owned_process_alive(s["ownedPid"],s.get("ownerStartIdentity")): s={"running":False,"ownedPid":None,"ownerNonce":None,"ownerStartIdentity":None,"url":None}; atomic(sf,s)
  if cmd=="backlot.status": return s,[]
  if cmd=="backlot.open": return {**s,"browserActionRequired":True},["Use the approved desktop/browser capability to open the loopback URL."]
  if cmd=="backlot.start":
   if s["running"]: return s,[]
   rt,_=require_valid_runtime(x); host=x.get("host","127.0.0.1")
   if host not in ("127.0.0.1","localhost","::1"): raise E("INVALID_ARGUMENT","Backlot must bind loopback")
   port=int(x.get("port",0));
   if port==0:
    z=socket.socket(); z.bind(("127.0.0.1",0)); port=z.getsockname()[1]; z.close()
   py=rt/".clawpod-venv/bin/python"; exe=str(py if py.exists() else Path(sys.executable)); nonce=uuid.uuid4().hex
   env={k:os.environ[k] for k in ("PATH","HOME","LANG","LC_ALL","TMPDIR") if k in os.environ}; env.update({"OPENMONTAGE_PROJECTS_DIR":str(r/"projects"),"CLAWPOD_BACKLOT_NONCE":nonce,"PYTHONUNBUFFERED":"1"})
   proc=subprocess.Popen([exe,"-m","backlot","serve","--port",str(port)],cwd=rt,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True); time.sleep(.5)
   if proc.poll() is not None: raise E("BACKLOT_START_FAILED","Backlot exited during startup",exit_code=7)
   s={"running":True,"ownedPid":proc.pid,"ownerNonce":nonce,"ownerStartIdentity":process_start_identity(proc.pid),"url":f"http://127.0.0.1:{port}"}; atomic(sf,s); return s,[]
  if x.get("confirm")!="stop-backlot": raise E("APPROVAL_REQUIRED","confirm=stop-backlot required",category="approval",exit_code=6)
  if s.get("ownedPid") and x.get("ownerNonce")!=s.get("ownerNonce"): raise E("OWNERSHIP_MISMATCH","Backlot owner nonce required",category="destructive",exit_code=11)
  if s.get("ownedPid") and owned_process_alive(s["ownedPid"],s.get("ownerStartIdentity")): os.killpg(s["ownedPid"],signal.SIGTERM)
  stopped={"running":False,"ownedPid":None,"ownerNonce":None,"ownerStartIdentity":None,"url":None,"stopped":bool(s.get("ownedPid"))}; atomic(sf,stopped); return stopped,[]
 if cmd.startswith("install."):
  lock=readj(Path(__file__).parent/"upstream.lock.json",{}); current=runtime(x,False); install=r/"runtime"; backup=r/"runtime.backup"; planp=r/"install-plan.json"
  if cmd=="install.inspect":
   con=readj(r/"connections.json",{}) or {}
   return {"capabilityVersion":VERSION,"upstream":lock,"discovered":validate_runtime({"runtimePath":str(current)}) if current else None,"managedRuntime":str(install) if install.exists() else None,"onboardingRequired":True,"connected":any(v.get("status")=="connected" for v in con.values())},[]
  if cmd=="install.plan-update":
   source=Path(x.get("sourcePath",str(current) if current else "" )).resolve(); v=validate_runtime({"runtimePath":str(source)}); plan={"sourcePath":str(source),"sourceDigest":source_digest(source),"validationDigest":sha(v["checks"]),"targetPath":str(install),"valid":v["valid"],"createdAt":now()}; plan["planDigest"]=sha(plan); atomic(planp,plan); return plan,[]
  if x.get("confirm") not in ("apply-update","rollback"): raise E("APPROVAL_REQUIRED","transaction confirmation required",category="approval",exit_code=6)
  if cmd=="install.apply-update":
   plan=readj(planp)
   if not plan or x.get("planDigest")!=plan.get("planDigest") or not plan["valid"]: raise E("DIGEST_MISMATCH","valid unchanged install plan required",exit_code=9)
   src=Path(plan["sourcePath"]); v=validate_runtime({"runtimePath":str(src)})
   if source_digest(src)!=plan["sourceDigest"] or sha(v["checks"])!=plan["validationDigest"]: raise E("DIGEST_MISMATCH","source changed after planning",exit_code=9)
   temp=r/("runtime.new-"+uuid.uuid4().hex[:8])
   try:
    shutil.copytree(src,temp,symlinks=True,ignore=shutil.ignore_patterns(".git",".env","__pycache__",".pytest_cache"),copy_function=shutil.copy2)
    atomic(temp/".clawpod-runtime-lock.json",{"commit":UPSTREAM_COMMIT,"tree":v["checks"]["tree"]["actual"],"sourceDigest":source_digest(src),"installedAt":now()})
    post=validate_runtime({"runtimePath":str(temp)})
    if not post["valid"]: raise E("DIGEST_MISMATCH","staged runtime failed post-copy validation",exit_code=9,details=post)
    previous=r/("runtime.previous-"+uuid.uuid4().hex[:8]); moved_current=False
    if install.exists(): os.replace(install,previous); moved_current=True
    try:
     os.replace(temp,install); active=validate_runtime({"runtimePath":str(install)})
     if not active["valid"]: raise E("DIGEST_MISMATCH","activated runtime failed validation",exit_code=9,details=active)
     if moved_current:
      if backup.exists(): shutil.rmtree(backup)
      os.replace(previous,backup)
    except Exception:
     if install.exists():
      invalid=r/("runtime.invalid-"+uuid.uuid4().hex[:8]); os.replace(install,invalid)
     if moved_current and previous.exists() and not install.exists(): os.replace(previous,install)
     raise
   except Exception:
    if temp.exists(): shutil.rmtree(temp)
    raise
   return {"applied":True,"targetPath":str(install),"backupAvailable":backup.exists(),"validation":active},[]
  if not backup.exists(): raise E("NOT_FOUND","no install backup",exit_code=3)
  failed=r/("runtime.failed-"+uuid.uuid4().hex[:8]); moved_current=False
  if install.exists(): os.replace(install,failed); moved_current=True
  try: os.replace(backup,install)
  except Exception:
   if moved_current and failed.exists() and not install.exists(): os.replace(failed,install)
   raise
  restored=validate_runtime({"runtimePath":str(install)})
  if not restored["valid"]:
   broken=r/("runtime.invalid-"+uuid.uuid4().hex[:8]); os.replace(install,broken)
   if failed.exists(): os.replace(failed,install)
   raise E("DIGEST_MISMATCH","rollback candidate failed validation; previous runtime was restored",category="digest",exit_code=9,details={"restored":restored,"invalidPath":str(broken)})
  return {"rolledBack":True,"targetPath":str(install),"replacedPath":str(failed) if failed.exists() else None,"validation":restored},[]
 raise E("INVALID_ARGUMENT","unsupported command")

def parser():
 p=argparse.ArgumentParser(); p.add_argument("command",choices=COMMANDS+["_worker"]); p.add_argument("--root"); p.add_argument("--input-json"); p.add_argument("--project-id"); p.add_argument("--pipeline-id"); p.add_argument("--provider"); p.add_argument("--job-id"); p.add_argument("--nonce"); return p
def main():
 a=parser().parse_args()
 if a.command=="_worker": return worker(root(a),a.job_id,a.nonce)
 try: data,w=handler(a.command,a,load_json_arg(a.input_json)); print(stable(envelope(a.command,data=data,warnings=w))); return 0
 except E as e: return fail(a.command,e)
 except Exception as e: return fail(a.command,E("INTERNAL_ERROR","internal adapter failure",category="internal",details={"type":type(e).__name__},exit_code=12))
if __name__=="__main__": raise SystemExit(main())
