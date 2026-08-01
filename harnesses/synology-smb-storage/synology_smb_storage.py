#!/usr/bin/env python3
"""Typed, bounded Synology SMB storage harness. Password is accepted only via stdin/env."""
import argparse, base64, json, os, re, shutil, subprocess, sys, tempfile, uuid
from pathlib import Path

ROOT=Path("/workspace/shared")
BEGIN="<!-- BEGIN SYNOLOGY SMB STORAGE POLICY v0.1.0 -->"
END="<!-- END SYNOLOGY SMB STORAGE POLICY v0.1.0 -->"
PASSWORD_ENV="SYNOLOGY_SMB_PASSWORD"
SAFE_OPTS=("vers=3.0","nosuid","nodev","noexec","cache=strict")
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

def relpath(v):
 p=Path(v or ".")
 if p.is_absolute() or ".." in p.parts or any(x in ("",) for x in p.parts): raise Fault("PATH_TRAVERSAL","path must be relative and remain under mount root")
 return p

def password():
 p=os.environ.get(PASSWORD_ENV)
 if p is None and not sys.stdin.isatty(): p=sys.stdin.readline().rstrip("\r\n")
 if not p: raise Fault("AUTH_REQUIRED",f"password required via {PASSWORD_ENV} or stdin")
 return p

def run(argv,*,secret=None,timeout=15):
 env=os.environ.copy(); inp=None
 if secret is not None:
  env["PASSWD"]=secret; inp=secret+"\n"
 try: return subprocess.run(argv,input=inp,text=True,capture_output=True,env=env,timeout=timeout,check=False)
 except subprocess.TimeoutExpired: raise Fault("BACKEND_TIMEOUT","backend timed out")
 except OSError as e: raise Fault("BACKEND_UNAVAILABLE",f"backend unavailable: {e.strerror}")

def smb(server,account,extra,secret): return run(["smbclient",*extra,"-m","SMB3","-U",valid_account(account),"--password-stdin"],secret=secret)
def discover(a):
 s,p=valid_server(a.server),password(); account=valid_account(a.account); cp=smb(s,account,["-L",f"//{s}","-g"],p)
 if cp.returncode: raise Fault("AUTH_OR_BACKEND_FAILURE","share discovery failed",{"exitCode":cp.returncode})
 shares=sorted({ln.split("|")[1] for ln in cp.stdout.splitlines() if ln.startswith("Disk|") and len(ln.split("|"))>1 and NAME.fullmatch(ln.split("|")[1])})
 selected=shares[0] if len(shares)==1 else None
 return {"server":s,"shares":shares,"selectedShare":selected,"ambiguous":len(shares)!=1}

def mount_source(a): return f"//{valid_server(a.server)}/{valid_name(a.share,'share')}"
def mounted():
 try:
  for ln in Path("/proc/self/mountinfo").read_text().splitlines():
   parts=ln.split();
   if str(ROOT) in parts and " - cifs " in ln: return ln
 except OSError: pass
 return None

def preview(a): return {"source":mount_source(a),"target":str(ROOT),"fstype":"cifs","options":list(SAFE_OPTS),"passwordTransport":"environment-or-stdin"}
def mount_apply(a):
 if mounted(): raise Fault("MOUNT_CONFLICT","mount target already contains a CIFS mount")
 if ROOT.exists() and any(ROOT.iterdir()): raise Fault("MOUNT_CONFLICT","mount target is non-empty")
 ROOT.mkdir(parents=True,exist_ok=True); p=password()
 opts=",".join((*SAFE_OPTS,f"username={valid_account(a.account)}"))
 cp=run(["mount.cifs",mount_source(a),str(ROOT),"-o",opts],secret=p)
 if cp.returncode: raise Fault("MOUNT_FAILED","mount.cifs failed",{"exitCode":cp.returncode,"retrySafe":True})
 return {"mounted":True,"target":str(ROOT),"options":list(SAFE_OPTS)}
def status(a): return {"mounted":bool(mounted()),"target":str(ROOT),"source":None if not mounted() else mounted().split(" - cifs ",1)[1].split()[0]}
def unmount(a):
 if not mounted(): return {"mounted":False,"changed":False}
 cp=run(["umount",str(ROOT)])
 if cp.returncode: raise Fault("UNMOUNT_FAILED","unmount failed",{"exitCode":cp.returncode})
 return {"mounted":False,"changed":True}
def layout_paths(a):
 org,agent=valid_name(a.org_id,"org-id"),valid_name(a.agent_id,"agent-id")
 return [ROOT/"common",ROOT/org/"common",ROOT/org/agent]
def layout(a,ensure=False):
 ps=layout_paths(a); changed=[]
 if ensure:
  if not mounted(): raise Fault("NOT_MOUNTED","shared storage is not mounted")
  for p in ps:
   if not p.exists(): p.mkdir(parents=True); changed.append(str(p))
 return {"paths":[{"path":str(p),"exists":p.is_dir()} for p in ps],"changed":changed}
def safe_target(v):
 p=(ROOT/relpath(v)).resolve(); rr=ROOT.resolve()
 if p!=rr and rr not in p.parents: raise Fault("PATH_TRAVERSAL","path escapes mount root")
 return p

def fileop(a,op):
 if not mounted(): raise Fault("NOT_MOUNTED","shared storage is not mounted")
 target=safe_target(a.path)
 if op=="list":
  if not target.is_dir(): raise Fault("NOT_FOUND","directory not found")
  return {"path":a.path,"entries":[{"name":x.name,"type":"directory" if x.is_dir() else "file","size":None if x.is_dir() else x.stat().st_size} for x in sorted(target.iterdir())]}
 if op=="get":
  if not target.is_file(): raise Fault("NOT_FOUND","file not found")
  raw=target.read_bytes(); return {"path":a.path,"bytes":len(raw),"contentBase64":base64.b64encode(raw).decode("ascii")} 
 src=Path(a.source)
 if not src.is_file(): raise Fault("NOT_FOUND","source file not found")
 target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists() and not a.overwrite: raise Fault("ALREADY_EXISTS","destination exists")
 fd,tmp=tempfile.mkstemp(dir=target.parent,prefix=".smb-put-"); os.close(fd)
 try: shutil.copyfile(src,tmp); os.replace(tmp,target)
 finally:
  if os.path.exists(tmp): os.unlink(tmp)
 return {"path":a.path,"bytes":target.stat().st_size}
def policy_validate(text):
 begins=[m.start() for m in re.finditer(re.escape("<!-- BEGIN SYNOLOGY SMB STORAGE POLICY"),text)]
 ends=[m.start() for m in re.finditer(re.escape("<!-- END SYNOLOGY SMB STORAGE POLICY"),text)]
 if len(begins)!=len(ends) or len(begins)>1 or (begins and begins[0]>ends[0]): raise Fault("MALFORMED_POLICY_MARKERS","WORKFLOW markers are malformed")
 return bool(begins),begins,ends

def workflow(a,rollback=False):
 path=Path(a.workflow); old=path.read_bytes(); text=old.decode("utf-8"); exists,b,e=policy_validate(text)
 if rollback:
  backup=path.with_suffix(path.suffix+".synology-smb-storage.bak")
  if not backup.exists(): raise Fault("NO_ROLLBACK","rollback backup not found")
  replacement=backup.read_bytes()
 else:
  block=f"{BEGIN}\n{POLICY}{END}"
  if exists:
   endline=text.find("-->",e[0])+3; new=text[:b[0]]+block+text[endline:]
  else: new=text+("" if text.endswith("\n") else "\n")+block+"\n"
  replacement=new.encode()
  path.with_suffix(path.suffix+".synology-smb-storage.bak").write_bytes(old)
 fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=".workflow-"); os.close(fd)
 try: Path(tmp).write_bytes(replacement); os.replace(tmp,path)
 finally:
  if os.path.exists(tmp): os.unlink(tmp)
 return {"workflow":str(path),"changed":replacement!=old,"rollback":rollback,"agentsChanged":False}

class JsonParser(argparse.ArgumentParser):
 def error(self,message):
  emit("invalid",error={"code":"INVALID_INPUT","message":message,"details":{}},ok=False)
  raise SystemExit(2)

def parser():
 p=JsonParser(); sp=p.add_subparsers(dest="cmd",required=True,parser_class=JsonParser)
 sp.add_parser("system.preflight"); sp.add_parser("auth.contract")
 q=sp.add_parser("auth.onboard"); q.add_argument("--server",required=True); q.add_argument("--account",required=True); q.add_argument("--workflow",required=True); q.add_argument("--org-id",required=True); q.add_argument("--agent-id",required=True); q.add_argument("--share")
 for c in ("shares.discover","mount.preview","mount.apply"):
  q=sp.add_parser(c); q.add_argument("--server",required=True); q.add_argument("--account",required=True); q.add_argument("--share",required=c!="shares.discover")
 sp.add_parser("mount.status"); sp.add_parser("mount.unmount")
 for c in ("layout.inspect","layout.ensure"):
  q=sp.add_parser(c); q.add_argument("--org-id",required=True); q.add_argument("--agent-id",required=True)
 q=sp.add_parser("file.list"); q.add_argument("--path",default=".")
 q=sp.add_parser("file.get"); q.add_argument("--path",required=True)
 q=sp.add_parser("file.put"); q.add_argument("--path",required=True); q.add_argument("--source",required=True); q.add_argument("--overwrite",action="store_true")
 for c in ("workflow.install","workflow.rollback"):
  q=sp.add_parser(c); q.add_argument("--workflow",required=True)
 return p

def main():
 a=parser().parse_args(); c=a.cmd
 try:
  if c=="system.preflight": d={"smbclient":bool(shutil.which("smbclient")),"mountCifs":bool(shutil.which("mount.cifs")),"mountRoot":str(ROOT),"smbProtocol":"SMB3"}
  elif c=="auth.contract": d={"requiredInputs":["NAS address","account","password"],"passwordTransport":["stdin",PASSWORD_ENV],"passwordPersisted":False,"postInstallState":"installed-not-connected","approvalRequired":True}
  elif c=="shares.discover": d=discover(a)
  elif c=="mount.preview": d=preview(a)
  elif c=="mount.apply": d=mount_apply(a)
  elif c=="mount.status": d=status(a)
  elif c=="mount.unmount": d=unmount(a)
  elif c=="layout.inspect": d=layout(a)
  elif c=="layout.ensure": d=layout(a,True)
  elif c=="file.list": d=fileop(a,"list")
  elif c=="file.get": d=fileop(a,"get")
  elif c=="file.put": d=fileop(a,"put")
  elif c=="workflow.install": d=workflow(a)
  elif c=="workflow.rollback": d=workflow(a,True)
  elif c=="auth.onboard":
   info=discover(a); share=a.share or info["selectedShare"]
   if not share: raise Fault("AMBIGUOUS_SHARE","multiple or no shares discovered; specify --share",{"shares":info["shares"]})
   a.share=share; d={"discovery":info,"mount":mount_apply(a),"layout":layout(a,True),"policy":workflow(a),"connected":True}
  return emit(c,d)
 except Fault as e: return emit(c,error={"code":e.code,"message":e.msg,"details":e.details},ok=False)
 except PermissionError: return emit(c,error={"code":"PERMISSION_DENIED","message":"permission denied","details":{}},ok=False)
 except OSError as e: return emit(c,error={"code":"IO_FAILURE","message":e.strerror or "I/O failure","details":{"retrySafe":False}},ok=False)

if __name__=="__main__": raise SystemExit(main())
