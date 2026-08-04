"""Secret-free, revisioned Notion onboarding state machine and desktop task contract."""
from __future__ import annotations
import json,os,re,stat,tempfile,time,uuid
from pathlib import Path
from typing import Any
TERMINAL={"ready","cancelled","failed","timed_out"}
HANDOFFS={"login_required","mfa_required","permission_approval_required","root_approval_required","secret_capture_required","captcha_required"}
SECRET_WORDS=("token","secret","password","authorization","cookie","otp","mfa_code")
NAME_RE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DEFAULT_STEPS=["navigate","login_required","select_workspace","configure_capabilities","permission_approval_required","connect_roots","root_approval_required","reveal_integration_token","secret_capture_required","complete"]

def _clean(v:Any,key="")->Any:
 if any(x in key.lower() for x in SECRET_WORDS):return "[REDACTED]"
 if isinstance(v,dict):return {k:_clean(x,k) for k,x in v.items() if k.lower() not in {"screenshot","html","dom"}}
 if isinstance(v,list):return [_clean(x,key) for x in v]
 if isinstance(v,str) and (v.startswith("ntn_") or "Bearer " in v):return "[REDACTED]"
 return v

def state_path(root_raw:str,session:str,state_name:str)->Path:
 if not root_raw:raise ValueError("--output-root is required")
 if not NAME_RE.fullmatch(session or "") or not NAME_RE.fullmatch(state_name or ""):raise ValueError("session and state-name must be bounded relative names")
 root=Path(root_raw)
 try:st=root.lstat()
 except FileNotFoundError:raise ValueError("output root must already exist")
 if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):raise ValueError("output root must be a real directory, not a symlink")
 if st.st_mode & 0o077:raise ValueError("output root must be private (owner-only permissions)")
 resolved=root.resolve(strict=True); child=resolved/session
 if child.exists() or child.is_symlink():
  cst=child.lstat()
  if stat.S_ISLNK(cst.st_mode) or not stat.S_ISDIR(cst.st_mode):raise ValueError("session path must be a real child directory")
  if cst.st_mode & 0o077:raise ValueError("session directory must be private")
 else:child.mkdir(mode=0o700)
 path=child/state_name
 if path.exists() or path.is_symlink():
  pst=path.lstat()
  if stat.S_ISLNK(pst.st_mode) or not stat.S_ISREG(pst.st_mode):raise ValueError("state file must be a regular non-symlink file")
 if resolved not in path.resolve(strict=False).parents:raise ValueError("state path escapes output root")
 return path

def _load(path:Path)->dict:
 try:return json.loads(path.read_text())
 except FileNotFoundError:raise ValueError("onboarding session not found")

def _save(path:Path,state:dict)->None:
 if path.is_symlink():raise ValueError("refusing symlink state file")
 raw=json.dumps(_clean(state),sort_keys=True,separators=(",",":"));fd,tmp=tempfile.mkstemp(prefix=".notion-onboard-",dir=path.parent)
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,"w") as f:f.write(raw);f.flush();os.fsync(f.fileno())
  if path.is_symlink():raise ValueError("refusing symlink state file")
  os.replace(tmp,path);os.chmod(path,0o600)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def _event(s:dict,k:str,d:dict|None=None):s["audit"].append(_clean({"seq":len(s["audit"])+1,"at":int(time.time()),"kind":k,"detail":d or {}}))
def plan(mode="internal",workspace=None,roots=None,capabilities=None):
 return {"mode":mode,"workspace":workspace,"roots":roots or [],"capability_profile":"full","selected_capabilities":sorted(set(capabilities or ["read_content","insert_content","update_content","read_comments","insert_comments","read_user_information"])),"external_effects_performed":False,"primary_path":"internal_integration","token_issuance_guide":["Open Notion Settings > Connections (or My integrations) and create an Internal Integration.","Choose the exact approved workspace and approved integration name.","Select the owner-approved full capability profile: content read/insert/update, comments read/insert, and user information access as supported by Notion.","Granting broad integration capabilities does not pre-authorize live writes; each mutation still requires Harness preview, exact intent approval, execution, and verification.","Share only approved page/database roots and verify each exact root; allowedRoots remains enforced.","Reveal/copy the token only at the protected-handoff checkpoint, then hand it directly to the owner agent through protected secret capture, never chat/files/screenshots/logs."],"exposed_token_recovery":"Any token pasted into chat or another ordinary channel is exposed: revoke/rotate it in Notion, then capture only the replacement through protected secret storage.","paths":{"internal":"simplest default; guided Internal Integration issuance with exact approval gates","pat":"personal/development only; protected capture required","oauth":"navigation planning only without configured provider client"},"stops":["login/MFA","CAPTCHA or human verification","exact workspace/root approval","final permission confirmation","protected secret capture"],"revocation":"Revoke in Notion, disconnect roots, delete protected pointer, cancel local session."}

def desktop_task(mode="internal",workspace=None,roots=None,capabilities=None):
 return {"kind":"desktop_task_template","provider":"notion","live_selectors_validated":False,"pure":True,"placeholders":{"workspace":workspace,"integration_name":"<approved integration name>","capabilities":sorted(set(capabilities or ["read_content","insert_content","update_content","read_comments","insert_comments","read_user_information"])),"roots":roots or []},"rules":{"capture_screenshots":False,"capture_dom":False,"scrape_credentials":False,"submit_without_approval":False,"stop_on":["login","mfa","captcha","human_verification","workspace_mismatch","ui_drift","permission_confirmation","secret_field"]},"steps":[{"action":"navigate","target":"Notion integration settings","verify":"page identity and expected heading; otherwise ui_drift"},{"action":"fill_safe_fields","fields":["integration_name"],"verify":"read back non-secret value"},{"action":"select_workspace","value":"${workspace}","verify":"exact workspace text; handoff workspace approval before continuing"},{"action":"configure_capabilities","value":"${capabilities}","verify":"exact minimum set, no broader capability"},{"action":"gate","reason":"permission_approval_required","position":"before final create/authorize submit"},{"action":"connect_roots","value":"${roots}","verify":"exact root identity before each connection"},{"action":"gate","reason":"root_approval_required","position":"before each root confirmation"},{"action":"reveal_integration_token","verify":"only after exact workspace, full capability profile, roots, and final permission approval; never capture screen/DOM/log"},{"action":"gate","reason":"secret_capture_required","instruction":"user copies the newly issued token and hands it directly to the owner agent through protected secret capture only; never chat/files/screenshots/logs. If pasted in chat, treat as exposed and revoke/rotate before capture."}],"recovery":{"ui_drift":"stop, report last verified step and visible non-secret labels, update adapter only after review","resume":"feed exact handoff result and current revision to onboard.resume"}}

def _fixture()->dict:
 path=os.environ.get("NOTION_ONBOARD_TEST_FIXTURE")
 if not path:return {"steps":DEFAULT_STEPS}
 if os.environ.get("NOTION_ONBOARD_TEST_MODE")!="1":raise ValueError("fixture injection is disabled outside explicit test mode")
 obj=json.loads(Path(path).read_text())
 if not isinstance(obj,dict) or not isinstance(obj.get("steps"),list):raise ValueError("test adapter fixture requires steps")
 return obj

def _advance(s:dict,fixture:dict,approved:set[str],credential:bool):
 steps=fixture["steps"];i=s["adapter_cursor"]
 while i<len(steps):
  step=steps[i];step={"kind":step} if isinstance(step,str) else step;k=step.get("kind")
  if k in {"fill_safe_fields","navigate","select_workspace","configure_capabilities","connect_roots","reveal_integration_token"}:
   if k=="select_workspace" and step.get("workspace") not in (None,s["workspace"]):s.update(status="failed",handoff={"reason":"wrong_workspace","expected":s["workspace"],"observed":step.get("workspace")});_event(s,"wrong_workspace",s["handoff"]);return
   _event(s,"adapter_step",{"kind":k,"verified":True});i+=1;s["adapter_cursor"]=i;continue
  reason="captcha_required" if k=="captcha" else k
  if reason in HANDOFFS:
   if reason=="secret_capture_required" and credential:i+=1;s["adapter_cursor"]=i;_event(s,"credential_injected",{"source":"protected_runtime"});continue
   if reason in approved:i+=1;s["adapter_cursor"]=i;_event(s,"handoff_resolved",{"reason":reason});continue
   s.update(status="waiting",handoff={"reason":reason,"checkpoint":i,"instructions":step.get("instructions",reason.replace("_"," "))});_event(s,"handoff_required",s["handoff"]);return
  if k=="complete":s.update(status="verification_required",handoff={"reason":"runtime_verification_required"});_event(s,"ui_complete");return
  raise ValueError(f"unsupported adapter step: {k}")

def command(cmd:str,*,output_root:str,session:str,state_name="state.json",mode="internal",workspace=None,roots=None,capabilities=None,expected_revision=None,approve=None,timeout_seconds=900,credential_present=False,now=None):
 if cmd=="onboard.plan":return plan(mode,workspace,roots,capabilities)
 if cmd in {"onboard.desktop.plan","onboard.desktop.task"}:return desktop_task(mode,workspace,roots,capabilities)
 path=state_path(output_root,session,state_name);now=int(now or time.time())
 if cmd=="onboard.start":
  if path.exists():
   old=_load(path)
   if old.get("status") not in TERMINAL:return {**old,"idempotent":True}
  s={"schema_version":1,"session_id":str(uuid.uuid4()),"revision":0,"status":"running","mode":mode,"workspace":workspace,"roots":roots or [],"allowedRoots":roots or [],"capability_profile":"full","selected_capabilities":sorted(set(capabilities or ["read_content","insert_content","update_content","read_comments","insert_comments","read_user_information"])),"created_at":now,"updated_at":now,"expires_at":now+timeout_seconds,"adapter_cursor":0,"handoff":None,"audit":[]};_event(s,"started",{"mode":mode,"workspace":workspace});_advance(s,_fixture(),set(),credential_present);s["revision"]+=1;_save(path,s);return s
 s=_load(path);expired=now>=s["expires_at"] and s["status"] not in TERMINAL
 if cmd in {"onboard.status","onboard.inspect"}:return s if not expired else {**s,"status":"timed_out","handoff":{"reason":"timeout","recovery":"resume or restart after review"},"derived":True}
 if expected_revision is None or int(expected_revision)!=s["revision"]:raise ValueError(f"stale revision; expected current revision {s['revision']}")
 if expired:s.update(status="timed_out",handoff={"reason":"timeout","recovery":"restart after review"});s["revision"]+=1;_event(s,"timed_out");_save(path,s);return s
 if cmd=="onboard.cancel":s.update(status="cancelled",handoff=None,updated_at=now);s["revision"]+=1;_event(s,"cancelled",{"cleanup":"local task discarded; revoke provider state separately"});_save(path,s);return s
 if cmd=="onboard.resume":
  if s["status"] in TERMINAL:return {**s,"idempotent":True}
  s.update(status="running",handoff=None,updated_at=now);_advance(s,_fixture(),set(approve or []),credential_present);s["revision"]+=1;_save(path,s);return s
 raise ValueError("unknown onboarding command")
