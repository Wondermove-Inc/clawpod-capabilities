"""Durable, locked local state for previews, idempotency and opaque bound tokens."""
from __future__ import annotations
import fcntl, hashlib, hmac, json, os, tempfile, time
from contextlib import contextmanager
from pathlib import Path
from .security import canonical

TTL=600

def path():
 return Path(os.environ.get("GOOGLE_WORKSPACE_STATE_FILE",Path.home()/".local/state/clawpod/google-workspace.json"))
@contextmanager
def locked():
 p=path();p.parent.mkdir(parents=True,exist_ok=True); lock=p.with_suffix(p.suffix+".lock")
 with open(lock,"a+") as l:
  fcntl.flock(l,fcntl.LOCK_EX)
  try:d=json.loads(p.read_text())
  except (FileNotFoundError,json.JSONDecodeError):d={}
  d.setdefault("previews",{});d.setdefault("idempotency",{});d.setdefault("secret",os.urandom(32).hex())
  yield d
  fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=".state-")
  try:
   with os.fdopen(fd,"w") as f:json.dump(d,f,separators=(",",":"));f.flush();os.fsync(f.fileno())
   os.chmod(tmp,0o600);os.replace(tmp,p)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)

def fingerprint(command,account,payload):
 clean={k:v for k,v in payload.items() if k not in ("preview","dryRun","confirm","requestId")}
 return hashlib.sha256(canonical({"command":command,"account":account,"input":clean}).encode()).hexdigest()
def issue_preview(command,account,payload,target=None,etag=None):
 fp=fingerprint(command,account,payload);now=time.time()
 with locked() as d:
  token=hmac.new(bytes.fromhex(d["secret"]),f"{fp}:{now}:{os.urandom(8).hex()}".encode(),hashlib.sha256).hexdigest()
  d["previews"][token]={"fingerprint":fp,"command":command,"account":account,"target":target,"etag":etag,"issuedAt":now,"expiresAt":now+TTL,"used":False}
 return token

def consume_preview(token,command,account,payload,target=None,etag=None):
 with locked() as d:
  r=d["previews"].get(token)
  if not r:return False,"preview confirmation not found"
  if r["used"]:return False,"preview confirmation was already used"
  if time.time()>r["expiresAt"]:return False,"preview confirmation expired"
  if (r["command"],r["account"],r["fingerprint"])!=(command,account,fingerprint(command,account,payload)):return False,"preview confirmation does not match account, command, or input"
  if r.get("target")!=target or r.get("etag")!=etag:return False,"preview target or ETag is stale"
  r["used"]=True
 return True,None

def idempotency_lookup(key,command,account,payload):
 fp=fingerprint(command,account,payload)
 with locked() as d:
  r=d["idempotency"].get(f"{account}:{key}")
 return (r,fp)
def idempotency_store(key,command,account,payload,result):
 fp=fingerprint(command,account,payload)
 with locked() as d:d["idempotency"][f"{account}:{key}"]={"fingerprint":fp,"command":command,"result":result,"createdAt":time.time()}

def bind_token(raw,command,account,query):
 with locked() as d:
  doc={"raw":raw,"command":command,"account":account,"query":hashlib.sha256(canonical(query).encode()).hexdigest(),"issuedAt":time.time()}
  enc=json.dumps(doc,separators=(",",":"),sort_keys=True).encode().hex();sig=hmac.new(bytes.fromhex(d["secret"]),enc.encode(),hashlib.sha256).hexdigest()
 return enc+"."+sig
def unbind_token(token,command,account,query):
 try:enc,sig=token.split(".",1)
 except ValueError:raise ValueError("unbound or malformed continuation token")
 with locked() as d:expected=hmac.new(bytes.fromhex(d["secret"]),enc.encode(),hashlib.sha256).hexdigest()
 if not hmac.compare_digest(sig,expected):raise ValueError("invalid continuation token")
 doc=json.loads(bytes.fromhex(enc));qh=hashlib.sha256(canonical(query).encode()).hexdigest()
 if (doc["command"],doc["account"],doc["query"])!=(command,account,qh):raise ValueError("continuation token does not match command, account, or query")
 return doc["raw"]
