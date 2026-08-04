#!/usr/bin/env python3
"""Fail-closed accountless Cloudflare Quick Tunnel controller (stdlib only)."""
import argparse,hashlib,ipaddress,json,os,re,signal,socket,stat,subprocess,sys,tempfile,time
from pathlib import Path
from urllib.parse import urlsplit
VERSION="0.1.0"; MAXLOG=16384
class Fail(Exception):
 def __init__(self,c,m):self.code,self.message=c,m
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(131072),b''):h.update(b)
 return h.hexdigest()
def binary(p):
 q=Path(p)
 if not q.is_absolute():raise Fail('UNSAFE_BINARY','cloudflared must be absolute')
 try:s=os.lstat(q)
 except OSError:raise Fail('UNSAFE_BINARY','cloudflared unavailable')
 if stat.S_ISLNK(s.st_mode) or not stat.S_ISREG(s.st_mode) or not os.access(q,os.X_OK):raise Fail('UNSAFE_BINARY','cloudflared must be a regular executable non-symlink')
 if s.st_mode&0o022:raise Fail('UNSAFE_BINARY','cloudflared must not be group/world writable')
 return {'path':str(q),'sha256':sha(q),'device':s.st_dev,'inode':s.st_ino}
def root(p,create=False):
 q=Path(p)
 if create:q.mkdir(parents=True,mode=0o700,exist_ok=True)
 try:s=os.lstat(q)
 except OSError:raise Fail('STATE_UNAVAILABLE','state root unavailable')
 if stat.S_ISLNK(s.st_mode) or not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o700:raise Fail('UNSAFE_STATE','state root must be owner-owned mode 0700')
 return q
def fileok(p):
 s=os.lstat(p)
 if stat.S_ISLNK(s.st_mode) or not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o600:raise Fail('UNSAFE_STATE','state files must be owner-owned mode 0600')
def validurl(u):
 try:x=urlsplit(u)
 except ValueError:return False
 return x.scheme=='https' and x.port is None and not x.username and not x.password and x.path in ('','/') and not x.query and not x.fragment and bool(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com',x.hostname or ''))
def target(host,port,connect=True):
 try:i=ipaddress.ip_address(host)
 except ValueError:raise Fail('UNSAFE_TARGET','host must be a loopback IP literal')
 if not i.is_loopback:raise Fail('UNSAFE_TARGET','target must be loopback-only')
 if not 1<=port<=65535:raise Fail('INVALID_PORT','port must be 1..65535')
 if connect:
  try:
   with socket.create_connection((host,port),.5):pass
  except OSError:raise Fail('TARGET_UNAVAILABLE','local target is unavailable')
 return 'http://'+(('['+host+']') if i.version==6 else host)+':'+str(port)
def surprises():
 if any(os.environ.get(x) for x in ('TUNNEL_TOKEN','TUNNEL_ORIGIN_CERT','CF_TUNNEL_TOKEN','CLOUDFLARED_CONFIG')):raise Fail('AUTH_STATE_PRESENT','credential/config environment is not allowed')
 d=Path.home()/'.cloudflared'
 if any((d/x).exists() for x in ('config.yml','config.yaml','cert.pem','credentials.json')):raise Fail('AUTH_STATE_PRESENT','Cloudflare config/auth state is present')
def pstart(pid):
 try:return Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]
 except (OSError,IndexError):return None
def owned(s):
 st=pstart(s['pid'])
 if st is None:return False
 if st!=s['pidStart']:raise Fail('FOREIGN_PID','PID identity changed')
 try:e=os.readlink('/proc/'+str(s['pid'])+'/exe')
 except OSError:raise Fail('FOREIGN_PID','process executable cannot be verified')
 if e.endswith(' (deleted)') or os.path.realpath(e)!=os.path.realpath(s['binary']['path']):raise Fail('FOREIGN_PID','process executable differs')
 if binary(s['binary']['path'])!=s['binary']:raise Fail('BINARY_CHANGED','cloudflared binary changed')
 return True
def load(r,optional=False):
 q=root(r)/'state.json'
 if not q.exists():
  if optional:return None
  raise Fail('NOT_RUNNING','no tunnel state')
 fileok(q)
 try:s=json.loads(q.read_text())
 except Exception:raise Fail('MALFORMED_STATE','invalid JSON state')
 keys={'schemaVersion','pid','pidStart','binary','url','target','createdAt','expiresAt'}
 if not isinstance(s,dict) or set(s)!=keys or s['schemaVersion']!=1 or not isinstance(s['pid'],int) or not isinstance(s['binary'],dict) or set(s['binary'])!={'path','sha256','device','inode'} or not validurl(s['url']):raise Fail('MALFORMED_STATE','invalid state shape')
 return s
def save(r,s):
 r=root(r,True);fd,n=tempfile.mkstemp(dir=r,prefix='.state-');os.fchmod(fd,0o600)
 try:
  with os.fdopen(fd,'w') as f:json.dump(s,f,separators=(',',':'));f.flush();os.fsync(f.fileno())
  os.replace(n,r/'state.json')
 finally:
  try:os.unlink(n)
  except FileNotFoundError:pass
def slog(p):
 try:fileok(p);x=p.read_bytes()[-MAXLOG:].decode('utf8','replace')
 except FileNotFoundError:return ''
 x=re.sub(r'(?i)(token|secret|password|authorization)(\s*[=:]\s*)\S+',r'\1\2[REDACTED]',x)
 return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]','?',x)[-4096:]
def ok(c,d,e=[]):return {'ok':True,'schemaVersion':1,'command':c,'data':d,'effects':e}
def stopowned(s):
 if not owned(s):return False
 os.kill(s['pid'],signal.SIGTERM);end=time.time()+3
 while time.time()<end:
  if pstart(s['pid']) is None:return True
  time.sleep(.05)
 if owned(s):os.kill(s['pid'],signal.SIGKILL)
 return True
def run(a):
 if a.command=='preflight':root(a.state_root,True);surprises();return ok('preflight',{'ready':True,'binary':binary(a.cloudflared),'target':target(a.host,a.port,not a.skip_connect)})
 if a.command=='status':
  if not Path(a.state_root).exists():return ok('status',{'state':'absent','version':VERSION})
  s=load(a.state_root,True)
  if not s:return ok('status',{'state':'stopped','version':VERSION})
  live=owned(s);return ok('status',{'state':'running' if live else 'stale','expired':time.time()>=s['expiresAt'],'url':s['url'] if live else None,'expiresAt':s['expiresAt'],'version':VERSION})
 if a.command=='inspect':
  s=load(a.state_root);live=owned(s);return ok('inspect',{'state':'running' if live else 'stale','url':s['url'] if live else None,'target':s['target'],'createdAt':s['createdAt'],'expiresAt':s['expiresAt'],'expired':time.time()>=s['expiresAt'],'logs':slog(Path(a.state_root)/'cloudflared.log')})
 if a.command=='stop':
  if not Path(a.state_root).exists():return ok('stop',{'state':'stopped','changed':False})
  s=load(a.state_root,True)
  if not s:return ok('stop',{'state':'stopped','changed':False})
  if not owned(s):raise Fail('STALE_PID','persisted tunnel process is no longer running')
  changed=stopowned(s);Path(a.state_root,'state.json').unlink();return ok('stop',{'state':'stopped','changed':changed},['owned tunnel terminated'])
 if a.command=='_reap':
  try:s=load(a.state_root);time.sleep(max(0,s['expiresAt']-time.time()));s=load(a.state_root);stopowned(s);Path(a.state_root,'state.json').unlink(missing_ok=True)
  except Fail:pass
  return ok('_reap',{})
 # start
 r=root(a.state_root,True);old=load(r,True)
 if old and owned(old):raise Fail('ALREADY_RUNNING','an owned tunnel is running')
 b=binary(a.cloudflared);surprises();u=target(a.host,a.port)
 if not 30<=a.ttl<=86400:raise Fail('INVALID_TTL','ttl must be 30..86400')
 if not 1<=a.discovery_timeout<=30:raise Fail('INVALID_TIMEOUT','discovery timeout must be 1..30')
 lp=r/'cloudflared.log';fd=os.open(lp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
 try:p=subprocess.Popen([b['path'],'tunnel','--no-autoupdate','--config','/dev/null','--url',u],stdin=subprocess.DEVNULL,stdout=fd,stderr=fd,start_new_session=True,close_fds=True,env={'PATH':'/usr/bin:/bin','HOME':str(r),'LANG':'C.UTF-8'})
 finally:os.close(fd)
 ps=pstart(p.pid)
 if ps is None:raise Fail('EARLY_DEATH','cloudflared exited before identity capture')
 end=time.time()+a.discovery_timeout;url=None
 while time.time()<end:
  if p.poll() is not None:raise Fail('EARLY_DEATH','cloudflared exited before URL discovery')
  for x in re.findall(r'https://[^\s]+',slog(lp)):
   if validurl(x):url=x;break
  if url:break
  time.sleep(.1)
 if not url:os.kill(p.pid,signal.SIGTERM);raise Fail('DISCOVERY_TIMEOUT','valid Quick Tunnel URL not discovered')
 now=time.time();s={'schemaVersion':1,'pid':p.pid,'pidStart':ps,'binary':b,'url':url,'target':u,'createdAt':now,'expiresAt':now+a.ttl};save(r,s)
 subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'_reap','--state-root',str(r)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)
 return ok('start',{'state':'running','url':url,'expiresAt':s['expiresAt']},['external tunnel created','TTL reaper started'])
def parser():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True)
 for n in ('status','inspect','stop','_reap'):q=s.add_parser(n);q.add_argument('--state-root',required=True)
 for n in ('preflight','start'):
  q=s.add_parser(n);q.add_argument('--state-root',required=True);q.add_argument('--cloudflared',required=True);q.add_argument('--host',default='127.0.0.1');q.add_argument('--port',required=True,type=int)
  if n=='preflight':q.add_argument('--skip-connect',action='store_true')
  else:q.add_argument('--ttl',type=int,default=3600);q.add_argument('--discovery-timeout',type=float,default=10)
 return p
def main():
 a=parser().parse_args()
 try:r=run(a);code=0
 except Fail as e:r={'ok':False,'schemaVersion':1,'command':a.command,'error':{'code':e.code,'message':e.message},'effects':[]};code=2
 print(json.dumps(r,separators=(',',':')));return code
if __name__=='__main__':raise SystemExit(main())
