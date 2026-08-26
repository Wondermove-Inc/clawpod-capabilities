"""Detached, pod-local Google OAuth lifecycle.

Gateway-facing functions are short control-plane calls. The worker performs the
human-paced browser/callback flow without nested control-plane calls.
"""
from __future__ import annotations
import hashlib,hmac,json,os,secrets,signal,subprocess,sys,time
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from .bindings import BindingError,binding_root,ensure_root,list_bindings,normalize_alias,register_staged_binding
from .oauth_desktop import desktop_login,LoginError
from .state import consume_preview

HANDLE_RE=__import__('re').compile(r"^[A-Za-z0-9_-]{43}$")
ACTIVE={"starting","pending_browser","pending_callback","exchanging","validating"}
TERMINAL={"finalized","failed","cancelled","expired"}

def _now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def _jobs(root=None):
 root=ensure_root(root or binding_root()); p=root/'.oauth-jobs';p.mkdir(mode=0o700,exist_ok=True);os.chmod(p,0o700)
 (p/'staging').mkdir(mode=0o700,exist_ok=True);return p

def _atomic(path,doc,mode=0o600):
 data=(json.dumps(doc,sort_keys=True,separators=(',',':'))+'\n').encode();tmp=path.with_name('.'+path.name+'.'+secrets.token_hex(6)+'.part')
 fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
 with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)

def _key(jobs):
 p=jobs/'.key'
 try:return p.read_bytes()
 except FileNotFoundError:
  key=secrets.token_bytes(32);fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as f:f.write(key);f.flush();os.fsync(f.fileno())
  return key

def _mac(doc,key):
 bare={k:v for k,v in doc.items() if k!='mac'}
 return hmac.new(key,json.dumps(bare,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
def _save(jobs,doc):doc=dict(doc);doc['mac']=_mac(doc,_key(jobs));_atomic(jobs/(doc['handle']+'.status.json'),doc)
def _load(jobs,handle):
 if not isinstance(handle,str) or not HANDLE_RE.fullmatch(handle):raise BindingError('JOB_NOT_FOUND','OAuth job is unavailable')
 try:doc=json.loads((jobs/(handle+'.status.json')).read_text())
 except Exception:raise BindingError('JOB_NOT_FOUND','OAuth job is unavailable') from None
 mac=doc.pop('mac',None)
 if not isinstance(mac,str) or not hmac.compare_digest(mac,_mac(doc,_key(jobs))):raise BindingError('JOB_STALE','OAuth job is unavailable')
 doc['mac']=mac;return doc
@contextmanager
def _lock(jobs,handle):
 import fcntl
 p=jobs/(handle+'.lock');fd=os.open(p,os.O_RDWR|os.O_CREAT,0o600);fcntl.flock(fd,fcntl.LOCK_EX)
 try:yield
 finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
def _public(d):
 out={k:d[k] for k in ('handle','status','createdAt','updatedAt','expiresAt','account') if k in d}
 if d.get('status') in ('ready_to_finalize','finalized'):out['result']=d.get('result',{})
 if d.get('status') in ('failed','cancelled','expired'):out['error']=d.get('error',{})
 if d.get('status') in ACTIVE:out['pollAfterMs']=1000
 for k in ('bound','revision','alreadyFinalized'):
  if k in d:out[k]=d[k]
 return out
def _cleanup(jobs,d,staged=True):
 (jobs/(d['handle']+'.config.json')).unlink(missing_ok=True);(jobs/(d['handle']+'.cancel')).unlink(missing_ok=True)
 if staged:(jobs/'staging'/(d['handle']+'.json')).unlink(missing_ok=True)
def _process_start(pid):
 try:return Path(f'/proc/{pid}/stat').read_text().split()[21]
 except Exception:return None

def _reconcile(jobs,d):
 if d['status'] in ACTIVE and time.time()>=d['deadline']:
  d.update(status='expired',updatedAt=_now(),revision=d['revision']+1,error={'code':'AUTHORIZATION_TIMEOUT','message':'Authorization timed out','retryable':False});_cleanup(jobs,d);_save(jobs,d)
 elif d['status'] in ACTIVE and d.get('pid'):
  try:os.kill(d['pid'],0)
  except OSError:
   d.update(status='failed',updatedAt=_now(),revision=d['revision']+1,error={'code':'WORKER_DIED','message':'Authorization worker stopped','retryable':False});_cleanup(jobs,d);_save(jobs,d)
 return d

def start(payload):
 jobs=_jobs();alias=normalize_alias(payload['account']);body=payload['body'];request_id=payload.get('requestId');timeout=payload.get('timeoutMs',600000)
 digest=hashlib.sha256(json.dumps({'account':alias,'transferRoot':payload['transferRoot'],'body':body,'timeoutMs':timeout,'overwrite':bool(payload.get('overwrite')),'confirm':payload.get('confirm')},sort_keys=True,separators=(',',':')).encode()).hexdigest()
 if request_id:
  for p in list(jobs.glob('*.status.json'))[:100]:
   try:d=_load(jobs,p.name[:-12])
   except BindingError:continue
   if d.get('requestId')==request_id:
    if d.get('requestDigest')!=digest:raise BindingError('IDEMPOTENCY_CONFLICT','requestId was already used with different input')
    return _public(_reconcile(jobs,d))
 items,rev=list_bindings(root=binding_root());existing=next((x for x in items if x['alias']==alias),None)
 if existing and not payload.get('overwrite'):raise BindingError('BINDING_CONFLICT','binding alias already exists')
 if existing and not payload.get('confirm'):raise BindingError('APPROVAL_REQUIRED','replacing a binding requires preview confirmation')
 if existing:
  target={'operation':'login','alias':alias,'replacesBinding':True,'revision':rev}
  ok,reason=consume_preview(payload['confirm'],'auth.login',alias,payload,target,None)
  if not ok:raise BindingError('APPROVAL_REQUIRED',reason)
 handle=secrets.token_urlsafe(32);created=_now();deadline=time.time()+timeout/1000
 d={'schemaVersion':1,'handle':handle,'status':'starting','createdAt':created,'updatedAt':created,'expiresAt':datetime.fromtimestamp(deadline,timezone.utc).isoformat().replace('+00:00','Z'),'deadline':deadline,'account':alias,'revision':0,'bindingRevision':rev,'overwrite':bool(payload.get('overwrite')),'requestId':request_id,'requestDigest':digest}
 config={'handle':handle,'transferRoot':payload['transferRoot'],'clientPath':body['clientPath'],'profiles':body['profiles'],'managedBrowserDevtoolsUrl':body.get('managedBrowserDevtoolsUrl'),'smokeTests':body.get('smokeTests',[]),'timeout':timeout/1000,'account':alias}
 _save(jobs,d);_atomic(jobs/(handle+'.config.json'),config)
 proc=subprocess.Popen([sys.executable,'-m','google_workspace_core.oauth_jobs','--worker',handle],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True,start_new_session=True,cwd=str(Path(__file__).resolve().parents[1]),env={'PATH':os.environ.get('PATH',''),'PYTHONPATH':str(Path(__file__).resolve().parents[1])})
 with _lock(jobs,handle):d=_load(jobs,handle);d.update(status='pending_browser',pid=proc.pid,processStart=_process_start(proc.pid),updatedAt=_now(),revision=1);_save(jobs,d)
 return _public(d)
def status(handle):
 jobs=_jobs()
 with _lock(jobs,handle):return _public(_reconcile(jobs,_load(jobs,handle)))
def finalize(handle):
 jobs=_jobs();root=binding_root()
 with _lock(jobs,handle):
  d=_reconcile(jobs,_load(jobs,handle))
  if d['status']=='finalized':d['alreadyFinalized']=True;return _public(d)
  if d['status']!='ready_to_finalize':raise BindingError('JOB_CONFLICT','OAuth job is not ready to finalize')
  staged=jobs/'staging'/(handle+'.json')
  if hashlib.sha256(staged.read_bytes()).hexdigest()!=d.get('stagedDigest'):raise BindingError('JOB_STALE','staged credential failed integrity validation')
  doc=register_staged_binding(d['account'],staged,overwrite=d['overwrite'],root=root,expected_revision=d['bindingRevision'])
  d.update(status='finalized',updatedAt=_now(),revision=d['revision']+1,bound=True,alreadyFinalized=False);d['revision']=doc['revision'];_cleanup(jobs,d);_save(jobs,d);return _public(d)
def cancel(handle):
 jobs=_jobs()
 with _lock(jobs,handle):
  d=_reconcile(jobs,_load(jobs,handle))
  if d['status']=='finalized':raise BindingError('JOB_CONFLICT','finalized OAuth job cannot be cancelled')
  if d['status']=='cancelled':return _public(d)
  (jobs/(handle+'.cancel')).touch(mode=0o600,exist_ok=True)
  pid=d.get('pid')
  if pid and d.get('processStart') and hmac.compare_digest(str(d['processStart']),str(_process_start(pid))):
   try:os.killpg(pid,signal.SIGTERM)
   except OSError:pass
  d.update(status='cancelled',updatedAt=_now(),revision=d['revision']+1,error={'code':'CANCELLED','message':'Authorization cancelled','retryable':False});_cleanup(jobs,d);_save(jobs,d);return _public(d)
def recover(handle=None,max_jobs=20):
 jobs=_jobs();docs=[]
 paths=[jobs/(handle+'.status.json')] if handle else sorted(jobs.glob('*.status.json'))[:max_jobs]
 for p in paths:
  h=handle or p.name[:-12]
  try:
   with _lock(jobs,h):docs.append(_public(_reconcile(jobs,_load(jobs,h))))
  except BindingError:
   if handle:raise
 return {'items':docs,'scanned':len(paths),'active':sum(x.get('status') in ACTIVE for x in docs),'terminal':sum(x.get('status') in TERMINAL for x in docs)}
def worker(handle):
 jobs=_jobs()
 try:
  cfg=json.loads((jobs/(handle+'.config.json')).read_text())
  with _lock(jobs,handle):d=_load(jobs,handle);d.update(status='pending_callback',updatedAt=_now(),revision=d['revision']+1);_save(jobs,d)
  staged=jobs/'staging'/(handle+'.json')
  result=desktop_login(transfer_root=cfg['transferRoot'],client_path=cfg['clientPath'],output_path=staged.name,output_root=staged.parent,alias=cfg['account'],profiles=cfg['profiles'],timeout=cfg['timeout'],overwrite=False,managed_browser_devtools_url=cfg.get('managedBrowserDevtoolsUrl'),smoke_tests=cfg.get('smokeTests',[]))
  if any(not x.get('ok') for x in result.get('smokeTests',{}).values()):raise LoginError('requested post-login smoke test failed')
  with _lock(jobs,handle):
   d=_load(jobs,handle)
   if d['status'] in TERMINAL:_cleanup(jobs,d);return
   safe={'email':result['email'],'subjectHash':result['subject_hash'],'scopes':result['scopes'],'smokeTests':result['smokeTests']}
   d.update(status='ready_to_finalize',updatedAt=_now(),revision=d['revision']+1,result=safe,stagedDigest=hashlib.sha256(staged.read_bytes()).hexdigest());d.pop('pid',None);_cleanup(jobs,d,staged=False);_save(jobs,d)
 except Exception:
  try:
   with _lock(jobs,handle):
    d=_load(jobs,handle)
    if d['status'] not in TERMINAL:d.update(status='failed',updatedAt=_now(),revision=d['revision']+1,error={'code':'AUTH_REQUIRED','message':'Authorization failed safely','retryable':False});_cleanup(jobs,d);_save(jobs,d)
  except Exception:pass
if __name__=='__main__' and len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2])
