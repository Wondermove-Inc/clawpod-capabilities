"""Secret-free, revisioned Notion onboarding state machine and mock UI adapter."""
from __future__ import annotations
import hashlib, json, os, tempfile, time, uuid
from pathlib import Path
from typing import Any

TERMINAL={"ready","cancelled","failed","timed_out"}
HANDOFFS={"login_required","mfa_required","permission_approval_required","root_approval_required","secret_capture_required","captcha_required"}
SECRET_WORDS=("token","secret","password","authorization","cookie","otp","mfa_code")

def _clean(v:Any,key="")->Any:
 if any(x in key.lower() for x in SECRET_WORDS): return "[REDACTED]"
 if isinstance(v,dict): return {k:_clean(x,k) for k,x in v.items() if k.lower() not in {"screenshot","html","dom"}}
 if isinstance(v,list): return [_clean(x,key) for x in v]
 if isinstance(v,str) and (v.startswith("ntn_") or "Bearer " in v): return "[REDACTED]"
 return v

def _load(path:Path)->dict:
 try:return json.loads(path.read_text())
 except FileNotFoundError:raise ValueError("onboarding session not found")

def _save(path:Path,state:dict)->None:
 path.parent.mkdir(parents=True,exist_ok=True)
 safe=_clean(state)
 raw=json.dumps(safe,sort_keys=True,separators=(",",":"))
 fd,tmp=tempfile.mkstemp(prefix=".notion-onboard-",dir=path.parent)
 try:
  with os.fdopen(fd,"w") as f:f.write(raw);f.flush();os.fsync(f.fileno())
  os.chmod(tmp,0o600);os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def _event(state:dict,kind:str,detail:dict|None=None)->None:
 state["audit"].append(_clean({"seq":len(state["audit"])+1,"at":int(time.time()),"kind":kind,"detail":detail or {}}))

def plan(mode="internal",workspace=None,roots=None,capabilities=None)->dict:
 roots=roots or []; caps=sorted(set(capabilities or ["read_content"]))
 return {"mode":mode,"workspace":workspace,"roots":roots,"minimum_capabilities":caps,
  "external_effects_performed":False,"primary_path":"internal_integration","paths":{
   "internal":"automate safe form fields; require exact workspace, root, and final permission approval",
   "pat":"personal/development token; protected capture still required",
   "oauth":"planning and authorization navigation only; client configuration and token exchange are not automated"},
  "stops":["login/MFA","CAPTCHA or human verification","exact workspace/root approval","final permission confirmation","protected secret capture"],
  "revocation":"Revoke the integration/PAT in Notion, remove root connections, then delete the protected secret pointer."}

def _fixture(path:str|None)->dict:
 if not path:return {"steps":["login_required"]}
 obj=json.loads(Path(path).read_text())
 if not isinstance(obj,dict) or not isinstance(obj.get("steps"),list):raise ValueError("adapter fixture requires a steps array")
 return obj

def _advance(state:dict,fixture:dict,approved:set[str],credential_present:bool)->None:
 steps=fixture["steps"]; i=state["adapter_cursor"]
 while i<len(steps):
  step=steps[i]; step={"kind":step} if isinstance(step,str) else step; kind=step.get("kind")
  if kind in {"fill_safe_fields","navigate","select_workspace","configure_capabilities","connect_roots"}:
   if kind=="select_workspace" and step.get("workspace") not in (None,state["workspace"]):
    state.update(status="failed",handoff={"reason":"wrong_workspace","expected":state["workspace"],"observed":step.get("workspace")});_event(state,"wrong_workspace",state["handoff"]);return
   _event(state,"adapter_step",{"kind":kind});i+=1;state["adapter_cursor"]=i;continue
  reason=kind
  if reason=="captcha": reason="captcha_required"
  if reason in HANDOFFS:
   if reason=="secret_capture_required" and credential_present:i+=1;state["adapter_cursor"]=i;_event(state,"credential_injected",{"source":"protected_runtime"});continue
   if reason in approved:i+=1;state["adapter_cursor"]=i;_event(state,"handoff_resolved",{"reason":reason});continue
   state.update(status="waiting",handoff={"reason":reason,"checkpoint":i,"instructions":step.get("instructions",reason.replace("_"," "))});_event(state,"handoff_required",state["handoff"]);return
  if kind=="complete":state.update(status="verification_required",handoff={"reason":"runtime_verification_required"});_event(state,"ui_complete");return
  raise ValueError(f"unsupported adapter fixture step: {kind}")
 state.update(status="verification_required",handoff={"reason":"runtime_verification_required"})

def command(cmd:str,*,state_path:str,mode="internal",workspace=None,roots=None,capabilities=None,fixture_path=None,expected_revision=None,approve=None,timeout_seconds=900,credential_present=False,now=None)->dict:
 path=Path(state_path);now=int(now or time.time())
 if cmd=="onboard.plan":return plan(mode,workspace,roots,capabilities)
 if cmd=="onboard.start":
  if path.exists():
   old=_load(path)
   if old.get("status") not in TERMINAL:return {**old,"idempotent":True}
  state={"schema_version":1,"session_id":str(uuid.uuid4()),"revision":0,"status":"running","mode":mode,"workspace":workspace,"roots":roots or [],"allowedRoots":roots or [],"minimum_capabilities":sorted(set(capabilities or ["read_content"])),"created_at":now,"updated_at":now,"expires_at":now+timeout_seconds,"adapter_cursor":0,"handoff":None,"audit":[]}
  _event(state,"started",{"mode":mode,"workspace":workspace});_advance(state,_fixture(fixture_path),set(),credential_present);state["revision"]+=1;_save(path,state);return state
 state=_load(path)
 expired=now>=state["expires_at"] and state["status"] not in TERMINAL
 if cmd in {"onboard.status","onboard.inspect"}:
  if not expired:return state
  return {**state,"status":"timed_out","handoff":{"reason":"timeout","recovery":"resume with the current revision or restart after reviewing the saved plan"},"derived":True}
 if expected_revision is None or int(expected_revision)!=state["revision"]:raise ValueError(f"stale revision; expected current revision {state['revision']}")
 if expired:
  state.update(status="timed_out",handoff={"reason":"timeout","recovery":"restart with onboard.start after reviewing the saved plan"});state["revision"]+=1;_event(state,"timed_out");_save(path,state);return state
 if cmd=="onboard.cancel":
  state.update(status="cancelled",handoff=None,updated_at=now);state["revision"]+=1;_event(state,"cancelled",{"cleanup":"browser task state discarded; revoke provider integration separately if already approved"});_save(path,state);return state
 if cmd=="onboard.resume":
  if state["status"] in TERMINAL:return {**state,"idempotent":True}
  approved=set(approve or [])
  state.update(status="running",handoff=None,updated_at=now);_advance(state,_fixture(fixture_path),approved,credential_present);state["revision"]+=1;_save(path,state);return state
 raise ValueError("unknown onboarding command")
