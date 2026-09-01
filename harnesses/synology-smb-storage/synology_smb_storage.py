#!/usr/bin/env python3
"""Guarded Synology SMB storage control harness with secret-redacted output."""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, uuid
from pathlib import Path

ROOT=Path("/workspace/shared")
BEGIN="<!-- BEGIN SYNOLOGY SMB STORAGE POLICY v0.1.0 -->"
END="<!-- END SYNOLOGY SMB STORAGE POLICY v0.1.0 -->"
PASSWORD_ENV="SYNOLOGY_SMB_PASSWORD"
SAFE_OPTS=("vers=3.1.1","nosuid","nodev","noexec","cache=strict")
SMBCLIENT_PROTOCOL=("--option=client min protocol=SMB3_11","--option=client max protocol=SMB3_11")
NAME=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
ACCOUNT=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,126}$")
SERVER=re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?|(?:\d{1,3}\.){3}\d{1,3})$")
POLICY='''Shared-storage-first durable artifact policy:\n- Store durable deliverables under /workspace/shared/common, /workspace/shared/<org-id>/common, or /workspace/shared/<org-id>/<agent-id>.\n- Use local workspace only for scratch, cache, builds, Git worktrees, and SQLite databases.\n- Do not place Git repositories or SQLite databases on SMB storage.\n'''

class Fault(Exception):
 def __init__(self,code,msg,details=None): self.code,self.msg,self.details=code,msg,details or {}

def emit(command,data=None,effects=None,error=None,ok=True):
 obj={"ok":ok,"schemaVersion":1,"command":command,"requestId":str(uuid.uuid4()),"data":data or {},"effects":effects or [],"error":error}
 print(json.dumps(obj,separators=(",",":"),sort_keys=True)); return 0 if ok else 1

def valid_name(v,label):
 if not NAME.fullmatch(v or ""): raise Fault("INVALID_INPUT",f"invalid {label}")
 return v

def valid_account(v):
 if not ACCOUNT.fullmatch(v or ""): raise Fault("INVALID_INPUT","invalid account")
 return v

def valid_server(v):
 if not SERVER.fullmatch(v or "") or "/" in v or "\\" in v: raise Fault("INVALID_INPUT","invalid server")
 return v

def password():
 p=os.environ.get(PASSWORD_ENV)
 if p is None and not sys.stdin.isatty(): p=sys.stdin.readline().rstrip("\r\n")
 if not p: raise Fault("AUTH_REQUIRED",f"password required via {PASSWORD_ENV} or harness stdin")
 return p

def restore_password():
 p=os.environ.get(PASSWORD_ENV)
 if not p: raise Fault("AUTH_REQUIRED",f"password required via {PASSWORD_ENV}")
 return p

def run(argv,*,credential=None,timeout=15):
 env=os.environ.copy(); env.pop(PASSWORD_ENV,None)
 if credential is not None: env["PASSWD"]=credential
 try:
  cp=subprocess.run(argv,stdin=subprocess.DEVNULL,text=True,capture_output=True,env=env,timeout=timeout,check=False)
  # Never return backend diagnostics: a remote endpoint may reflect credentials.
  return subprocess.CompletedProcess(cp.args,cp.returncode,"","")
 except subprocess.TimeoutExpired: raise Fault("BACKEND_TIMEOUT","backend timed out")
 except OSError as e: raise Fault("BACKEND_UNAVAILABLE",f"backend unavailable: {e.strerror}")

def smb(server,account,extra,credential):
 return run(["smbclient",*extra,*SMBCLIENT_PROTOCOL,"-U",valid_account(account)],credential=credential)

def discover(a):
 s,p=valid_server(a.server),password(); account=valid_account(a.account)
 # Machine-readable share names are captured internally; backend output is never surfaced.
 env=os.environ.copy(); env.pop(PASSWORD_ENV,None); env["PASSWD"]=p
 argv=["smbclient","-L",f"//{s}","-g",*SMBCLIENT_PROTOCOL,"-U",account]
 try: cp=subprocess.run(argv,stdin=subprocess.DEVNULL,text=True,capture_output=True,env=env,timeout=15,check=False)
 except subprocess.TimeoutExpired: raise Fault("BACKEND_TIMEOUT","share discovery timed out")
 except OSError as e: raise Fault("BACKEND_UNAVAILABLE",f"backend unavailable: {e.strerror}")
 if cp.returncode: raise Fault("AUTH_OR_BACKEND_FAILURE","share discovery failed",{"exitCode":cp.returncode})
 safe_stdout=cp.stdout.replace(p,"[REDACTED]")
 shares=sorted({x[1] for ln in safe_stdout.splitlines() if len(x:=ln.split("|"))>1 and x[0]=="Disk" and NAME.fullmatch(x[1])})
 return {"server":s,"shares":shares,"selectedShare":shares[0] if len(shares)==1 else None,"ambiguous":len(shares)!=1}

def mount_source(a): return f"//{valid_server(a.server)}/{valid_name(a.share,'share')}"
def mount_record():
 try:
  for ln in Path("/proc/self/mountinfo").read_text().splitlines():
   parts=ln.split()
   if len(parts)>6 and parts[4]==str(ROOT) and "-" in parts:
    sep=parts.index("-")
    if len(parts)>sep+2: return {"line":ln,"fstype":parts[sep+1],"source":parts[sep+2]}
 except OSError: pass
 return None
def mounted():
 record=mount_record()
 return record if record and record["fstype"]=="cifs" else None

def preview(a): return {"source":mount_source(a),"target":str(ROOT),"fstype":"cifs","options":list(SAFE_OPTS),"passwordTransport":"PASSWD-environment-to-backend"}
def mount_apply(a):
 if mount_record(): raise Fault("MOUNT_CONFLICT","mount target is already a mountpoint")
 if ROOT.exists() and any(ROOT.iterdir()): raise Fault("MOUNT_CONFLICT","mount target is non-empty")
 created_root=not ROOT.exists(); ROOT.mkdir(parents=True,exist_ok=True)
 opts=",".join((*SAFE_OPTS,f"username={valid_account(a.account)}"))
 cp=run(["mount.cifs",mount_source(a),str(ROOT),"-o",opts],credential=password())
 if cp.returncode:
  if created_root:
   try: ROOT.rmdir()
   except OSError: pass
  raise Fault("MOUNT_FAILED","mount.cifs failed",{"exitCode":cp.returncode,"retrySafe":True})
 record=mounted()
 if not record or record["source"]!=mount_source(a):
  if mount_record(): run(["umount",str(ROOT)])
  if created_root:
   try: ROOT.rmdir()
   except OSError: pass
  raise Fault("MOUNT_VERIFY_FAILED","mount command succeeded but the expected CIFS source was not verified",{"retrySafe":False})
 return {"mounted":True,"target":str(ROOT),"options":list(SAFE_OPTS)}
def mount_restore(a):
 source=mount_source(a); account=valid_account(a.account); record=mount_record()
 if record:
  if record["fstype"]=="cifs" and record["source"]==source:
   return {"mounted":True,"changed":False,"source":source,"target":str(ROOT),"secretUsed":False,"externalSideEffect":False,"options":list(SAFE_OPTS)}
  raise Fault("MOUNT_CONFLICT","mount target is already mounted from a different source")
 if ROOT.exists() and any(ROOT.iterdir()): raise Fault("MOUNT_CONFLICT","mount target is non-empty")
 if not shutil.which("mount.cifs"): raise Fault("PREREQUISITE_MISSING","mount.cifs is unavailable")
 if os.geteuid()!=0 and not cap_sys_admin(): raise Fault("PREREQUISITE_MISSING","mount privilege is unavailable")
 credential=restore_password(); created_root=not ROOT.exists(); ROOT.mkdir(parents=True,exist_ok=True)
 opts=",".join((*SAFE_OPTS,f"username={account}"))
 cp=run(["mount.cifs",source,str(ROOT),"-o",opts],credential=credential)
 if cp.returncode:
  if created_root:
   try: ROOT.rmdir()
   except OSError: pass
  raise Fault("MOUNT_FAILED","mount.cifs failed",{"exitCode":cp.returncode,"retrySafe":True})
 verified=mount_record()
 if not verified or verified["fstype"]!="cifs" or verified["source"]!=source:
  # Do not perform a live rollback here: restoration is fail-closed and live
  # unmounting is outside this command's contract.
  raise Fault("MOUNT_VERIFY_FAILED","expected CIFS source and target were not verified",{"retrySafe":False})
 return {"mounted":True,"changed":True,"source":source,"target":str(ROOT),"secretUsed":True,"externalSideEffect":True,"options":list(SAFE_OPTS)}
def status(a):
 record=mounted(); return {"mounted":bool(record),"target":str(ROOT),"fstype":None if not record else record["fstype"],"source":None if not record else record["source"]}
def unmount(a):
 if not mounted(): return {"mounted":False,"changed":False}
 cp=run(["umount",str(ROOT)])
 if cp.returncode: raise Fault("UNMOUNT_FAILED","unmount failed",{"exitCode":cp.returncode})
 return {"mounted":False,"changed":True}

def layout_paths(a):
 org,agent=valid_name(a.org_id,"org-id"),valid_name(a.agent_id,"agent-id")
 return [ROOT/"common",ROOT/org/"common",ROOT/org/agent]
def layout(a,ensure=False,created=None):
 ps=layout_paths(a); changed=[] if created is None else created
 if ensure:
  if not mounted(): raise Fault("NOT_MOUNTED","shared storage is not mounted")
  org=ps[1].parent
  for p in (ps[0],org,ps[1],ps[2]):
   if not p.exists(): p.mkdir(); changed.append(str(p))
 return {"paths":[{"path":str(p),"exists":p.is_dir() and not p.is_symlink()} for p in ps],"changed":changed}

def policy_validate(text):
 begins=[m.start() for m in re.finditer(re.escape("<!-- BEGIN SYNOLOGY SMB STORAGE POLICY"),text)]
 ends=[m.start() for m in re.finditer(re.escape("<!-- END SYNOLOGY SMB STORAGE POLICY"),text)]
 if len(begins)!=len(ends) or len(begins)>1 or (begins and begins[0]>ends[0]): raise Fault("MALFORMED_POLICY_MARKERS","WORKFLOW markers are malformed")
 return bool(begins),begins,ends

def atomic_bytes(path,data):
 fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=".atomic-"); os.close(fd)
 try: Path(tmp).write_bytes(data); os.replace(tmp,path)
 finally:
  if os.path.exists(tmp): os.unlink(tmp)
def workflow(a,rollback=False):
 path=Path(a.workflow); old=path.read_bytes(); text=old.decode("utf-8"); exists,b,e=policy_validate(text)
 if rollback:
  backup=path.with_suffix(path.suffix+".synology-smb-storage.bak")
  if not backup.exists(): raise Fault("NO_ROLLBACK","rollback backup not found")
  replacement=backup.read_bytes()
 else:
  block=f"{BEGIN}\n{POLICY}{END}"
  if exists: replacement=(text[:b[0]]+block+text[text.find("-->",e[0])+3:]).encode()
  else: replacement=(text+("" if text.endswith("\n") else "\n")+block+"\n").encode()
  atomic_bytes(path.with_suffix(path.suffix+".synology-smb-storage.bak"),old)
 atomic_bytes(path,replacement)
 return {"workflow":str(path),"changed":replacement!=old,"rollback":rollback,"agentsChanged":False}

def rollback_onboard(a,workflow_before,backup_before,created,mounted_here):
 evidence={"attempted":True,"workflowRestored":False,"backupRestored":False,"unmountedNewMount":False,"removedDirectories":[],"failures":[]}
 path=Path(a.workflow)
 try:
  if path.exists() and path.read_bytes()!=workflow_before: atomic_bytes(path,workflow_before); evidence["workflowRestored"]=True
 except Exception as e: evidence["failures"].append({"step":"workflow","type":type(e).__name__})
 try:
  backup=path.with_suffix(path.suffix+".synology-smb-storage.bak")
  if backup_before is None:
   if backup.exists(): backup.unlink()
  else: atomic_bytes(backup,backup_before)
  evidence["backupRestored"]=True
 except Exception as e: evidence["failures"].append({"step":"workflowBackup","type":type(e).__name__})
 for raw in reversed(created):
  try:
   p=Path(raw)
   if p.is_dir() and not p.is_symlink() and not any(p.iterdir()): p.rmdir(); evidence["removedDirectories"].append(raw)
  except Exception as e: evidence["failures"].append({"step":"directory","path":raw,"type":type(e).__name__})
 if mounted_here:
  try: evidence["unmountedNewMount"]=bool(unmount(a)["changed"])
  except Exception as e: evidence["failures"].append({"step":"unmount","type":type(e).__name__})
 evidence["complete"]=not evidence["failures"]
 return evidence

def onboard(a):
 info=discover(a); share=a.share or info["selectedShare"]
 if not share: raise Fault("AMBIGUOUS_SHARE","multiple or no shares discovered; specify --share",{"shares":info["shares"]})
 if mounted(): raise Fault("MOUNT_CONFLICT","pre-existing mount will not be changed")
 workflow_path=Path(a.workflow); workflow_before=workflow_path.read_bytes(); policy_validate(workflow_before.decode("utf-8"))
 backup_path=workflow_path.with_suffix(workflow_path.suffix+".synology-smb-storage.bak"); backup_before=backup_path.read_bytes() if backup_path.exists() else None
 a.share=share; created=[]; mounted_here=False
 try:
  mount_result=mount_apply(a); mounted_here=True
  layout_result=layout(a,True,created)
  policy_result=workflow(a)
  return {"discovery":info,"mount":mount_result,"layout":layout_result,"policy":policy_result,"connected":True,"rollback":{"attempted":False}}
 except Exception as e:
  rb=rollback_onboard(a,workflow_before,backup_before,created,mounted_here)
  if isinstance(e,Fault): code,msg=e.code,e.msg
  elif isinstance(e,PermissionError): code,msg="PERMISSION_DENIED","permission denied"
  else: code,msg="ONBOARD_FAILED","onboarding failed"
  raise Fault(code,msg,{"partialSideEffects":mounted_here or bool(created),"rollback":rb})

def cap_sys_admin():
 try:
  for line in Path("/proc/self/status").read_text().splitlines():
   if line.startswith("CapEff:"): return bool(int(line.split()[1],16)&(1<<21))
 except (OSError,ValueError,IndexError): pass
 return False
def preflight():
 record=mount_record(); exists=ROOT.exists(); nonempty=exists and any(ROOT.iterdir())
 return {"tools":{"smbclient":bool(shutil.which("smbclient")),"mountCifs":bool(shutil.which("mount.cifs")),"umount":bool(shutil.which("umount"))},"privilege":{"effectiveUid":os.geteuid(),"capSysAdmin":cap_sys_admin(),"mountLikelyPermitted":os.geteuid()==0 or cap_sys_admin()},"mountRoot":{"path":str(ROOT),"exists":exists,"nonEmpty":nonempty,"cifsMounted":bool(record and record["fstype"]=="cifs"),"conflict":bool(record and record["fstype"]!="cifs") or (nonempty and not bool(record))},"protocol":{"dialect":"SMB3.1.1","mountOption":"vers=3.1.1","smbclientMin":"SMB3_11","smbclientMax":"SMB3_11"}}

class JsonParser(argparse.ArgumentParser):
 def error(self,message): emit("invalid",error={"code":"INVALID_INPUT","message":message,"details":{}},ok=False); raise SystemExit(2)
def parser():
 p=JsonParser(); sp=p.add_subparsers(dest="cmd",required=True,parser_class=JsonParser)
 sp.add_parser("system.preflight"); sp.add_parser("auth.contract")
 q=sp.add_parser("auth.onboard"); q.add_argument("--server",required=True); q.add_argument("--account",required=True); q.add_argument("--workflow",required=True); q.add_argument("--org-id",required=True); q.add_argument("--agent-id",required=True); q.add_argument("--share")
 for c in ("shares.discover","mount.preview","mount.apply"):
  q=sp.add_parser(c); q.add_argument("--server",required=True); q.add_argument("--account",required=True); q.add_argument("--share",required=c!="shares.discover")
 q=sp.add_parser("mount.restore"); q.add_argument("--server",required=True); q.add_argument("--account",required=True); q.add_argument("--share",required=True)
 sp.add_parser("mount.status"); sp.add_parser("mount.unmount")
 for c in ("layout.inspect","layout.ensure"):
  q=sp.add_parser(c); q.add_argument("--org-id",required=True); q.add_argument("--agent-id",required=True)
 for c in ("workflow.install","workflow.rollback"): q=sp.add_parser(c); q.add_argument("--workflow",required=True)
 return p

def main():
 a=parser().parse_args(); c=a.cmd
 try:
  if c=="system.preflight": d=preflight()
  elif c=="auth.contract": d={"requiredInputs":["NAS address","account","password"],"harnessInput":["stdin",PASSWORD_ENV],"backendPasswordTransport":"PASSWD environment only","passwordPersisted":False,"postInstallState":"installed-not-connected","approvalRequired":True}
  elif c=="shares.discover": d=discover(a)
  elif c=="mount.preview": d=preview(a)
  elif c=="mount.apply": d=mount_apply(a)
  elif c=="mount.restore": d=mount_restore(a)
  elif c=="mount.status": d=status(a)
  elif c=="mount.unmount": d=unmount(a)
  elif c=="layout.inspect": d=layout(a)
  elif c=="layout.ensure": d=layout(a,True)
  elif c=="workflow.install": d=workflow(a)
  elif c=="workflow.rollback": d=workflow(a,True)
  elif c=="auth.onboard": d=onboard(a)
  effects=[{"type":"mount","target":str(ROOT)}] if c=="mount.restore" and d["changed"] else []
  return emit(c,d,effects)
 except Fault as e: return emit(c,error={"code":e.code,"message":e.msg,"details":e.details},ok=False)
 except PermissionError: return emit(c,error={"code":"PERMISSION_DENIED","message":"permission denied","details":{}},ok=False)
 except OSError as e: return emit(c,error={"code":"IO_FAILURE","message":e.strerror or "I/O failure","details":{"retrySafe":False}},ok=False)

if __name__=="__main__": raise SystemExit(main())
