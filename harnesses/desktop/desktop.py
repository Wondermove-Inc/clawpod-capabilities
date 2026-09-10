#!/usr/bin/env python3
from __future__ import annotations
import fcntl, contextlib, math, io, stat, tempfile
import argparse, datetime as dt, hashlib, json, os, pathlib, re, shutil, struct, subprocess, sys, time, uuid, zlib
VERSION='3.1.3'; SCHEMA='desktop.v3'; STOP=re.compile(r'captcha|recaptcha|hcaptcha|turnstile|verify you are human|human verification|bot detection',re.I)
OBS=set('capabilities environment.preflight session.list session.get app.list app.get window.list window.get screen.list screen.capture ui.observe ui.find ui.read ui.table ui.wait ui.verify image.locate dialog.inspect clipboard.inspect download.inspect task.get task.events task.artifacts'.split())
S1=set('app.launch app.focus window.activate window.move window.resize window.minimize window.maximize window.restore pointer.move pointer.scroll keyboard.key keyboard.shortcut'.split())
S4={'window.close','process.terminate','process.kill'}
MAP={'app.list':['apps','--json'],'screen.capture':['screenshot'],'ui.observe':['observe','--json'],'ui.find':['find'],'ui.read':['read'],'ui.table':['table','--json'],'ui.wait':['wait'],'ui.verify':['verify'],'image.locate':['locate-image'],'app.launch':['open'],'app.focus':['focus'],'app.close':['close'],'pointer.click':['click'],'pointer.double-click':['dblclick'],'pointer.right-click':['rclick'],'pointer.scroll':['scroll'],'keyboard.type':['type'],'keyboard.key':['key'],'keyboard.shortcut':['key'],'keyboard.select':['select'],'image.click':['click-image']}
PRECISION_CLICKS={'pointer.click','pointer.double-click','pointer.right-click','image.click'}
PRECISION_ACTIONS=PRECISION_CLICKS|{'pointer.drag-drop','keyboard.type'}
PORTAL_ACTIONS={'dialog.respond','file-dialog.open','file-dialog.save','file-dialog.choose-directory','file-dialog.cancel'}
DISPLAY_MUTATION=re.compile(r'\b(?:xrandr|xfconf-query|xrdb|gsettings)\b|(?:xft[./_-]?dpi|text-scaling-factor|scaling-factor|scale-monitor-framebuffer|--(?:mode|dpi|scale|fb|output|newmode|addmode|delmode|off|rotate|transform))|"(?:resolution|dpi)"\s*:',re.I)
SESSION_MUTATION=re.compile(r'\b(?:Xvfb|Xorg|startx|xinit|startxfce4|xfce4-session|openbox-session|gnome-session)\b',re.I)
SESSION_LIFECYCLE={'session.open','session.recover','session.close'}
def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def redact(v):
 if isinstance(v,dict): return {k:('[REDACTED]' if re.search(r'pass|secret|token|otp|authorization|clipboard',k,re.I) else redact(x)) for k,x in v.items()}
 if isinstance(v,list): return [redact(x) for x in v]
 return v
def sensitive_values(v):
 out=[]
 if isinstance(v,dict):
  for k,x in v.items():
   if re.search(r'pass|secret|token|otp|authorization|clipboard',k,re.I) and isinstance(x,(str,int,float)):
    if str(x): out.append(str(x))
   else: out.extend(sensitive_values(x))
 elif isinstance(v,list):
  for x in v: out.extend(sensitive_values(x))
 return out
def scrub(v,secrets):
 if isinstance(v,dict): return {k:scrub(x,secrets) for k,x in v.items()}
 if isinstance(v,list): return [scrub(x,secrets) for x in v]
 if isinstance(v,str):
  for secret in secrets:
   v=v.replace(secret,'[REDACTED]')
 return v
def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def safe_root(p):
 root=pathlib.Path(os.environ.get('DESKTOP_RUNS_ROOT','/tmp/desktop-runs')).resolve(); q=pathlib.Path(p or root/f'run-{uuid.uuid4().hex[:12]}')
 if q.exists() and q.is_symlink(): raise ValueError('run root symlink refused')
 q=q.resolve()
 if q!=root and root not in q.parents: raise ValueError('run root outside approved root')
 q.mkdir(parents=True,exist_ok=True); return q
def atomic_state(path, value):
 temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 with os.fdopen(os.open(str(temp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as stream:
  json.dump(value,stream); stream.flush(); os.fsync(stream.fileno())
 os.replace(temp,path)
 fd=os.open(str(path.parent),os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)

@contextlib.contextmanager
def journal_lock(root):
 # Stable journal is independent of disposable per-run evidence directories.
 journal=root/'.journal'; journal.mkdir(mode=0o700,exist_ok=True)
 if journal.is_symlink():raise ValueError('journal symlink refused')
 fd=os.open(str(journal/'lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
 try:
  fcntl.flock(fd,fcntl.LOCK_EX)
  yield journal
 finally:os.close(fd)

def error(code,msg,category='validation',retryable=False,details=None,remediation='Correct the request and retry.'):
 return {'code':code,'message':msg,'category':category,'retryable':retryable,'details':details or {},'remediation':remediation}
def emit(cmd,rid,status,result=None,err=None,warnings=None,approval=None,revision=0,started=None,attempt=1,max_attempts=1):
 end=time.time(); o={'schemaVersion':SCHEMA,'requestId':rid,'command':cmd,'status':status,'revision':revision,'result':result or {},'error':err,'warnings':warnings or [],'artifacts':[],'approval':approval,'timing':{'startedAt':dt.datetime.fromtimestamp(started or end,dt.timezone.utc).isoformat(),'endedAt':now(),'durationMs':int((end-(started or end))*1000)},'retry':{'attempt':attempt,'maxAttempts':max_attempts,'retryable':bool(err and err.get('retryable'))}}
 if len(json.dumps(o,ensure_ascii=False,separators=(',',':')))>1800:o['retry']['detailsRequired']=True
 o={k:o[k] for k in ('schemaVersion','status','retry','error','warnings','command','requestId','result','revision','artifacts','approval','timing') if k in o}
 print(json.dumps(o,ensure_ascii=False,separators=(',',':')))
def bundled_backend():
 # The backend engine ships inside this harness package (engine/desktop), so the
 # unit is self-contained: no dependency on an image-vendored system CLI. An
 # explicit DESKTOP_SYSTEM_CLI override still wins (tests stub the backend this way).
 p=pathlib.Path(__file__).resolve().parent/'engine'/'desktop'
 return str(p) if p.is_file() else None
def backend(): return os.environ.get('DESKTOP_SYSTEM_CLI') or bundled_backend() or shutil.which('desktop') or '/workspace/skills/desktop/desktop'
def valid_approval(path,request_digest,inline=None):
 if path and inline:raise ValueError('Use either approval file or inline approval, not both')
 if inline is not None:
  x=json.loads(inline)
 elif path:
  p=pathlib.Path(path)
  if p.is_symlink(): raise ValueError('approval symlink refused')
  x=json.loads(p.read_text())
 else:return None
 if not isinstance(x,dict) or x.get('requestDigest')!=request_digest:return None
 try:
  expires=dt.datetime.fromisoformat(x['expiresAt'].replace('Z','+00:00'))
  if expires.tzinfo is None:return None
 except (KeyError,AttributeError,TypeError,ValueError):return None
 return x if expires>dt.datetime.now(dt.timezone.utc) else None
def forbidden_request(inp):
 raw=json.dumps(inp,ensure_ascii=False,separators=(',',':'))
 if DISPLAY_MUTATION.search(raw):
  return error('DISPLAY_MUTATION_FORBIDDEN','Display resolution, DPI, scale, X resources, and X settings are immutable.','policy',False,{'contract':'immutable-display-metrics'},'Remove the display-setting command or argument; Desktop never changes display metrics.')
 if SESSION_MUTATION.search(raw):
  return error('DESKTOP_SESSION_MUTATION_FORBIDDEN','Starting or replacing desktop/X sessions is outside Desktop capability behavior.','policy',False,{'contract':'existing-session-only'},'Use an independently provisioned disposable display outside this capability for environment tests.')
 return None
def display_metrics(budget=None):
 tool=os.environ.get('DESKTOP_METRICS_CLI') if os.environ.get('DESKTOP_DISPOSABLE_DISPLAY')=='1' else None
 tool=tool or shutil.which('xdpyinfo')
 if not tool or not os.environ.get('DISPLAY'): return None
 try:p=subprocess.run([tool],capture_output=True,text=True,timeout=budget.seconds(5000) if budget else 5,env=os.environ)
 except (OSError,subprocess.TimeoutExpired):return None
 if p.returncode:return None
 dimensions=re.search(r'dimensions:\s*(\d+)x(\d+)',p.stdout,re.I); resolution=re.search(r'resolution:\s*(\d+)x(\d+)\s+dots per inch',p.stdout,re.I)
 if not dimensions or not resolution:return None
 return {'display':os.environ.get('DISPLAY'),'width':int(dimensions.group(1)),'height':int(dimensions.group(2)),'dpiX':int(resolution.group(1)),'dpiY':int(resolution.group(2))}
def backend_call(argv,timeout_ms,*,budget=None,before_dispatch=None):
 before=display_metrics(budget) if budget else display_metrics()
 if before is None:return None, 'display_state_unavailable'
 # The bundled engine may install without its executable bit (the registry
 # installer only chmods the harness entrypoint); run it via the interpreter so
 # exec-bit loss never breaks it. shebang is python3, so this is equivalent.
 if argv and argv[0]==bundled_backend() and not os.access(argv[0],os.X_OK):argv=[sys.executable]+list(argv)
 if before_dispatch:before_dispatch()
 try:p=subprocess.run(argv,capture_output=True,text=True,timeout=budget.seconds(timeout_ms) if budget else max(1,min(timeout_ms,120000))/1000,env={**os.environ,'DESKTOP_FAST_INPUT':'1'})
 except subprocess.TimeoutExpired:return None, 'timeout'
 # A non-bundled backend path (DESKTOP_SYSTEM_CLI / PATH / legacy) that is not
 # executable would otherwise raise an uncaught PermissionError; surface it as a
 # normal unavailable-backend result instead of a traceback.
 except (PermissionError,OSError) as e:return None, {'code':'backend_unavailable','detail':str(e)}
 after=display_metrics(budget) if budget else display_metrics()
 if after is None:return None, 'display_state_unavailable'
 if before!=after:return None, {'code':'desktop_state_changed','before':before,'after':after}
 return p, None
def verified_capture_bytes(path):
 # Read one bounded regular-file snapshot; hash and decode exactly these bytes.
 with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
  info=os.fstat(stream.fileno())
  if not stat.S_ISREG(info.st_mode) or info.st_size>16777216 or info.st_nlink!=1:raise ValueError('invalid capture file')
  data=stream.read(16777217)
  if len(data)!=info.st_size or len(data)>16777216:raise ValueError('capture size changed')
 if data[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('PNG signature')
 pos=8; ended=False; first=True; seen_idat=False; closed_idat=False; seen_plte=False
 while pos<len(data):
  if pos+12>len(data):raise ValueError('truncated PNG')
  size=struct.unpack('>I',data[pos:pos+4])[0]; kind=data[pos+4:pos+8]; end=pos+12+size
  if end>len(data):raise ValueError('truncated PNG chunk')
  if zlib.crc32(data[pos+4:end-4])&0xffffffff!=struct.unpack('>I',data[end-4:end])[0]:raise ValueError('PNG CRC')
  if not first and kind==b'IHDR':raise ValueError('duplicate IHDR')
  if kind==b'PLTE':
   if seen_plte or seen_idat or not size or size%3 or size>768:raise ValueError('invalid PLTE ordering')
   seen_plte=True
  if kind==b'IDAT':
   if closed_idat:raise ValueError('non-contiguous IDAT')
   seen_idat=True
  elif seen_idat:closed_idat=True
  if kind not in {b'IHDR',b'PLTE',b'IDAT',b'IEND'} and not (kind[0]&32):raise ValueError('unknown critical PNG chunk')
  if first:
   if kind!=b'IHDR' or size!=13:raise ValueError('PNG header')
   width,height=struct.unpack('>II',data[pos+8:pos+16])
   if not (0<width<=16384 and 0<height<=16384 and width*height<=25000000):raise ValueError('PNG dimensions')
   first=False
  if kind==b'IEND':
   if size or end!=len(data) or not seen_idat:raise ValueError('PNG ending')
   ended=True
  pos=end
 if not ended:raise ValueError('missing IEND')
 from PIL import Image
 with Image.open(io.BytesIO(data)) as image:
  if image.size!=(width,height):raise ValueError('PNG decoder dimension mismatch')
  image.verify()
 with Image.open(io.BytesIO(data)) as image:
  if image.size!=(width,height):raise ValueError('PNG decoder dimension mismatch')
  image.load()
 return data
def backend_result(p,argv):
 return {'exitCode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'backendArgv':[pathlib.Path(argv[0]).name]+argv[1:]}
def safe_pointer_argv(target,cmd,args=(),trajectory=None,text_mode='append'):
 # xdotool mousemove --sync can wait forever when the pointer is already at the
 # requested coordinate. Focus/readback provide the synchronization boundary.
 tool=shutil.which('xdotool') or 'xdotool'
 if cmd=='keyboard.type':
  x,y=(target['visualRegion'][0]+target['visualRegion'][2]//2,target['visualRegion'][1]+target['visualRegion'][3]//2) if target['kind']=='image' else (target['x'],target['y'])
  argv=[tool,'mousemove',str(x),str(y),'click','1']
  # Selection is made AFTER the only click, so typing cannot deselect it.
  if text_mode=='replace':argv+=['key','--clearmodifiers','ctrl+a']
  return argv+['type','--clearmodifiers','--delay','20','--',args[0]]
 if cmd in PRECISION_CLICKS:
  if target['kind']=='image':x,y=target['visualRegion'][0]+target['visualRegion'][2]//2,target['visualRegion'][1]+target['visualRegion'][3]//2
  else:x,y=target['x'],target['y']
  click=['click','--repeat','2','--delay','100','1'] if cmd=='pointer.double-click' else ['click','3' if cmd=='pointer.right-click' else '1']
  return [tool,'mousemove',str(x),str(y)]+click
 if cmd=='pointer.drag-drop' and trajectory:
  argv=[tool,'mousemove',str(trajectory['points'][0][0]),str(trajectory['points'][0][1]),'mousedown','1']
  for point in trajectory['points'][1:]:argv+=['mousemove',str(point[0]),str(point[1])]
  return argv+['mouseup','1']
 return None
def xwindow_geometry(window_id):
 tool=shutil.which('xdotool')
 if not tool:return None
 p=subprocess.run([tool,'getwindowgeometry','--shell',str(window_id)],capture_output=True,text=True)
 if p.returncode:return None
 values={}
 for line in p.stdout.splitlines():
  if '=' in line:
   k,v=line.split('=',1)
   if v.lstrip('-').isdigit():values[k]=int(v)
 return values if all(k in values for k in ('X','Y','WIDTH','HEIGHT')) else None
def verify_effect(post,target,before_geometry,trajectory=None,before_visual=None,after_visual=None):
 tool=shutil.which('xdotool'); window_id=str(target.get('windowId')); checks={}
 if not tool:return False,{'xdotool':False}
 active=subprocess.run([tool,'getactivewindow'],capture_output=True,text=True); checks['activeWindowId']=active.stdout.strip(); checks['activeWindowMatch']=active.returncode==0 and active.stdout.strip()==window_id
 after=xwindow_geometry(window_id); checks['beforeGeometry']=before_geometry; checks['afterGeometry']=after
 if post.get('searchFieldText'):
  # Pixel differences cannot establish which text is present. Never echo the
  # requested string as evidence of a successful literal-text readback.
  checks['literalTextVerified']=False
 if post.get('visualRegionChanged') is True:
  checks['visualRegionChanged']=bool(before_visual and after_visual and before_visual!=after_visual)
 if before_geometry and after:
  checks['sizeUnchanged']=(before_geometry['WIDTH'],before_geometry['HEIGHT'])==(after['WIDTH'],after['HEIGHT'])
  if post.get('windowBoundsUnchanged') is not None:checks['boundsUnchanged']=before_geometry==after
  if trajectory:
   dx=round(trajectory['points'][-1][0]-trajectory['points'][0][0]); dy=round(trajectory['points'][-1][1]-trajectory['points'][0][1]); checks['dragDeltaMatch']=(after['X']-before_geometry['X'],after['Y']-before_geometry['Y'])==(dx,dy)
 supported={'activeWindowMatch','windowBoundsUnchanged','visualRegionChanged'}
 required=[checks['activeWindowMatch'],bool(post),not (set(post)-supported)]
 if 'windowBoundsUnchanged' in post and post['windowBoundsUnchanged'] is not True:required.append(False)
 for key in ('literalTextVerified','visualRegionChanged','sizeUnchanged','boundsUnchanged','dragDeltaMatch'):
  if key in checks:required.append(checks[key])
 return all(required),checks
def parsed_stdout(p):
 try:
  value=json.loads(p.stdout)
  return value if isinstance(value,dict) else {}
 except (TypeError,json.JSONDecodeError): return {}
def precision_error(inp):
 target=inp.get('target'); post=inp.get('postcondition')
 if not isinstance(target,dict): return error('PRECISION_TARGET_REQUIRED','Precision actions require a typed target.','policy',False,{},'Provide a fresh accessibility target; use explicit image or coordinate fallback only when supported.')
 kind=target.get('kind')
 if kind not in {'accessibility','image','coordinate'}: return error('PRECISION_TARGET_REQUIRED','Target kind must be accessibility, image, or coordinate.','policy')
 required={'windowId','observedRevision','targetDigest'}
 if not required.issubset(target) or type(target.get('observedRevision')) is not int or not isinstance(target.get('targetDigest'),str) or not target['targetDigest'] or type(target.get('windowId')) not in (str,int) or str(target['windowId'])=='': return error('STALE_TARGET','Target lacks fresh window, revision, or digest identity.','conflict',False)
 if kind=='accessibility': return error('ACCESSIBILITY_DISPATCH_UNSUPPORTED','Backend cannot dispatch an exact verified node identity; accessibility precision mutations are disabled.','policy',False,{},'Do not substitute current focus or a name selector. Use a separately observed supported visual target only when fallback policy permits.')
 if kind in {'coordinate','image'}:
  region=target.get('visualRegion')
  if not isinstance(region,list) or len(region)!=4 or not all(type(v) is int for v in region) or min(region[:2])<0 or min(region[2:])<1:
   return error('INVALID_INPUT','visualRegion must be [x,y,width,height] with nonnegative origin and positive dimensions.')
 if kind=='coordinate' and (any(type(target.get(k)) not in (int,float) or not math.isfinite(target[k]) for k in ('x','y','scale')) or type(target.get('monitor')) is not int or target['scale']<=0):
  return error('INVALID_INPUT','Coordinate target requires numeric x/y, positive scale and integer monitor.')
 if kind=='image':
  if inp.get('visionFallbackSupported') is not True or not isinstance(target.get('templateHash'),str) or not target['templateHash'] or type(target.get('confidence')) not in (int,float) or not math.isfinite(target['confidence']) or not 0<=target['confidence']<=1 or not isinstance(target.get('screenshotDigest'),str) or not target['screenshotDigest'] or not target.get('visualRegion'):
   return error('VISION_FALLBACK_UNSUPPORTED','Image fallback was not explicitly supported with screenshot/template hashes and confidence.','policy',False)
 if kind=='coordinate':
  if not all(k in target for k in ('x','y','screenshotDigest','visualRegion','monitor','scale')) or not isinstance(target.get('screenshotDigest'),str) or not target['screenshotDigest']:
   return error('COORDINATE_APPROVAL_REQUIRED','Coordinate fallback requires digest-bound screen, monitor, scale, and point identity.','policy',False)
 if not isinstance(post,dict) or not post:
  return error('POSTCONDITION_REQUIRED','Click-like actions require an explicit postcondition.','policy',False,{},'Describe a read-only state that confirms the action exactly once.')
 if kind!='accessibility':
  supported={'activeWindowMatch','windowBoundsUnchanged','visualRegionChanged'}
  if set(post)-supported or any(v is not True for v in post.values()):
   return error('POSTCONDITION_UNSUPPORTED','Visual targets support only explicit focus, unchanged bounds, or changed-region checks; these do not prove literal text or navigation.','policy',False,{},'Use accessibility readback for semantic assertions, or request a supported structural check and independently verify the visible result.')
 return None
class FocusGuardError(Exception):
 def __init__(self,code):self.code=code

class GuardBudget:
 # A single monotonic budget for this path, not a hard realtime guarantee.
 def __init__(self,timeout_ms,started):self.deadline=started+min(timeout_ms,120000)/1000
 def seconds(self,cap_ms=120000):
  remaining=min(self.deadline-time.monotonic(),cap_ms/1000)
  if remaining<=0:raise FocusGuardError('TIMEOUT')
  return remaining
 def metrics(self):
  value=display_metrics(self)
  self.seconds()
  if value is None:raise FocusGuardError('DISPLAY_STATE_UNAVAILABLE')
  if value.get('display')!=':99':raise FocusGuardError('FOCUS_GUARD_DISPLAY_UNSUPPORTED')
  return value
 def xread(self,*args):
  tool=shutil.which('xdotool')
  if not tool:raise FocusGuardError('FOCUS_NOT_VERIFIED')
  try:p=subprocess.run([tool,*map(str,args)],capture_output=True,text=True,timeout=self.seconds(),env=os.environ)
  except subprocess.TimeoutExpired:raise FocusGuardError('TIMEOUT')
  except OSError:raise FocusGuardError('FOCUS_NOT_VERIFIED')
  self.seconds()
  if p.returncode:raise FocusGuardError('FOCUS_NOT_VERIFIED')
  return p.stdout.strip()
 def identity(self,window_id,expected=None):
  display=self.metrics()
  pid=self.xread('getwindowpid',window_id)
  active=self.xread('getactivewindow')
  if not pid.isdecimal() or int(pid)<=0:raise FocusGuardError('PID_UNAVAILABLE')
  if window_number(active)!=window_number(window_id):raise FocusGuardError('FOCUS_NOT_VERIFIED')
  value={'windowId':str(window_id),'pid':int(pid),'display':display}
  if expected and value!=expected:raise FocusGuardError('FOCUS_IDENTITY_CHANGED')
  return value
 def geometry(self,window_id):
  fields=dict(line.split('=',1) for line in self.xread('getwindowgeometry','--shell',window_id).splitlines() if '=' in line)
  try:return {k:int(fields[k]) for k in ('X','Y','WIDTH','HEIGHT')}
  except (KeyError,ValueError):raise FocusGuardError('FOCUS_NOT_VERIFIED')

def window_number(value):
 if type(value) not in (str,int):return None
 text=str(value)
 if not re.fullmatch(r'(?:[0-9]+|0[xX][0-9a-fA-F]+)',text):return None
 number=int(text,16 if text.lower().startswith('0x') else 10)
 return number if number>0 else None

def focus_guard_error(cmd,inp):
 if inp.get('postCapture') is True and 'focusGuard' not in inp:
  return error('FOCUS_GUARD_REQUIRED','Return postCapture requires a fresh prepared focusGuard.','policy')
 if 'focusGuard' not in inp:return None
 if cmd!='keyboard.key' or inp.get('args')!=['Return']:
  return error('FOCUS_GUARD_UNSUPPORTED','focusGuard supports only a single Return.','policy')
 guard=inp['focusGuard']; target=inp.get('target'); observation=guard.get('observation') if isinstance(guard,dict) else None
 if not isinstance(guard,dict) or set(guard)!={'windowId','pid','observation'} or window_number(guard.get('windowId')) is None or type(guard.get('pid')) is not int or guard['pid']<=0 or not isinstance(observation,dict) or set(observation)!={'revision','digest','display'}:
  return error('INVALID_FOCUS_GUARD','Supply the complete guard returned by targeted ui.observe.','policy')
 shape=precision_error(inp)
 if shape:return shape
 display=observation['display']
 if type(observation['revision']) is not int or not isinstance(observation['digest'],str) or not isinstance(display,dict) or set(display)!={'display','width','height','dpiX','dpiY'} or not isinstance(display['display'],str) or not display['display'] or any(type(display[k]) is not int or display[k]<=0 for k in ('width','height','dpiX','dpiY')):
  return error('INVALID_FOCUS_GUARD','Guard observation and display identity are incomplete.','policy')
 if str(guard['windowId'])!=str(target['windowId']) or observation['revision']!=target['observedRevision'] or observation['digest']!=target['targetDigest']:
  return error('STALE_TARGET','Guard and target identities conflict.','conflict')
 if inp['postcondition']!={'activeWindowMatch':True,'windowBoundsUnchanged':True}:
  return error('POSTCONDITION_UNSUPPORTED','Guarded Return requires activeWindowMatch and windowBoundsUnchanged only.','policy')
 return None

def guard_observe(budget,run,target,expected=None):
 # No focus repair, no retry, no background readiness loop.
 identity=budget.identity(target['windowId'],expected)
 private=pathlib.Path(tempfile.mkdtemp(prefix='guard-',dir=run))
 old_umask=os.umask(0o077)
 try:observed,failed=backend_call([backend()]+MAP['ui.observe']+['--screenshot',str(private/'observe.png')],120000,budget=budget)
 finally:os.umask(old_umask)
 if failed or observed is None or observed.returncode:raise FocusGuardError('TIMEOUT' if failed=='timeout' else 'FOCUS_OBSERVATION_FAILED')
 observation=parsed_stdout(observed)
 if observation.get('accessibilityMatch'):raise FocusGuardError('ACCESSIBILITY_TARGET_AVAILABLE')
 actual=target_identity(observation,target)
 if not actual or not actual.get('focused') or window_number(actual['windowId'])!=window_number(target['windowId']):raise FocusGuardError('FOCUS_NOT_VERIFIED')
 budget.identity(target['windowId'],identity)
 return observation,identity

def png_region_digest(path,region):
 # Decode once in native code when Pillow is available. Preserve the exact
 # legacy channel order and hash prefix; never reuse a prior screenshot digest.
 try:
  from PIL import Image
 except ImportError:
  return png_region_digest_python(path,region)
 with Image.open(path) as image:
  channels={'L':1,'RGB':3,'LA':2,'RGBA':4}.get(image.mode)
  if image.format!='PNG' or not channels:
   return png_region_digest_python(path,region)
  if not isinstance(region,(list,tuple)) or len(region)!=4:
   raise ValueError('invalid visual region')
  x,y,w,h=region
  if not all(type(v) is int for v in region) or x<0 or y<0 or w<1 or h<1 or x+w>image.width or y+h>image.height:
   raise ValueError('visual region outside screenshot')
  crop=image.crop((x,y,x+w,y+h)).tobytes()
  return hashlib.sha256(struct.pack('>III',w,h,channels)+crop).hexdigest()
def png_region_digest_python(path,region):
 data=path.read_bytes(); pos=8; width=height=bit_depth=color_type=interlace=None; compressed=b''
 while pos<len(data):
  length=struct.unpack('>I',data[pos:pos+4])[0]; kind=data[pos+4:pos+8]; chunk=data[pos+8:pos+8+length]; pos+=12+length
  if kind==b'IHDR':width,height,bit_depth,color_type,_,_,interlace=struct.unpack('>IIBBBBB',chunk)
  elif kind==b'IDAT':compressed+=chunk
  elif kind==b'IEND':break
 channels={0:1,2:3,4:2,6:4}.get(color_type)
 if bit_depth!=8 or interlace!=0 or not channels:raise ValueError('unsupported screenshot PNG format')
 raw=zlib.decompress(compressed); stride=width*channels; rows=[]; prior=bytearray(stride); i=0
 for _ in range(height):
  filt=raw[i]; i+=1; scan=bytearray(raw[i:i+stride]); i+=stride
  for j in range(stride):
   left=scan[j-channels] if j>=channels else 0; up=prior[j]; upper_left=prior[j-channels] if j>=channels else 0
   if filt==1:scan[j]=(scan[j]+left)&255
   elif filt==2:scan[j]=(scan[j]+up)&255
   elif filt==3:scan[j]=(scan[j]+((left+up)//2))&255
   elif filt==4:
    p=left+up-upper_left; pa=abs(p-left); pb=abs(p-up); pc=abs(p-upper_left); scan[j]=(scan[j]+(left if pa<=pb and pa<=pc else up if pb<=pc else upper_left))&255
   elif filt!=0:raise ValueError('unsupported screenshot PNG filter')
  rows.append(bytes(scan)); prior=scan
 x,y,w,h=region
 if not all(isinstance(v,int) for v in region) or x<0 or y<0 or w<1 or h<1 or x+w>width or y+h>height:raise ValueError('visual region outside screenshot')
 crop=b''.join(row[x*channels:(x+w)*channels] for row in rows[y:y+h])
 return hashlib.sha256(struct.pack('>III',w,h,channels)+crop).hexdigest()
def target_identity(observation,target):
 if all(k in observation for k in ('revision','targetDigest','windowId')):
  return {'windowId':str(observation['windowId']),'observedRevision':observation['revision'],'targetDigest':observation['targetDigest'],'nodeId':target.get('nodeId'),'name':target.get('name'),'app':None,'bbox':None,'focused':bool(observation.get('focused',False))}
 active=observation.get('active_window') or {}; window_id=str(active.get('window_id') or '')
 if target.get('kind') in {'coordinate','image'}:
  screenshot_value=observation.get('screenshot') or ''
  screenshot=pathlib.Path(screenshot_value.get('path','') if isinstance(screenshot_value,dict) else screenshot_value)
  if not screenshot.is_file():return None
  region=target.get('visualRegion')
  if not isinstance(region,list) or len(region)!=4:return None
  try:screenshot_digest=png_region_digest(screenshot,region)
  except (OSError,ValueError,zlib.error):return None
  stable={'windowId':window_id,'screenshotDigest':screenshot_digest,'visualRegion':region,'screen':observation.get('screen')}
  if target.get('kind')=='coordinate':stable.update({'point':[target.get('x'),target.get('y')],'monitor':target.get('monitor'),'scale':target.get('scale')})
  else:stable.update({'templateHash':target.get('templateHash'),'confidence':target.get('confidence')})
  target_digest=digest(stable)
  return {'windowId':window_id,'observedRevision':int(target_digest[:8],16),'targetDigest':target_digest,'screenshotDigest':screenshot_digest,'nodeId':None,'name':None,'app':None,'bbox':None,'focused':bool(window_id and not active.get('error'))}
 nodes=observation.get('nodes') or []
 node=None
 if target.get('nodeId') is not None:
  matches=[n for n in nodes if str(n.get('id'))==str(target['nodeId'])]
  node=matches[0] if len(matches)==1 else None
 elif target.get('name'):
  matches=[n for n in nodes if n.get('name')==target['name']]
  node=matches[0] if len(matches)==1 else None
 if not node:return None
 stable_node={k:node.get(k) for k in ('id','path','app','role','name','bbox','actions')}
 target_digest=digest({'windowId':window_id,'target':stable_node})
 return {'windowId':window_id,'observedRevision':int(target_digest[:8],16),'targetDigest':target_digest,'nodeId':str(node['id']),'name':node.get('name'),'app':node.get('app'),'bbox':node.get('bbox'),'focused':node.get('focused') is True}
def observation_index(observation):
 active=observation.get('active_window') or {}; out=[]
 for node in observation.get('nodes') or []:
  if node.get('id') is not None and node.get('bbox'):
   identity=target_identity(observation,{'nodeId':node['id']})
   if identity:out.append(identity)
 return {'activeWindow':active,'targets':out}
def observation_matches(observation,target):
 identity=target_identity(observation,target)
 return bool(identity and identity['observedRevision']==target.get('observedRevision') and
         identity['targetDigest']==target.get('targetDigest') and
         identity['windowId']==str(target.get('windowId')))
def validate_drag(inp):
 drag=inp.get('drag')
 if not isinstance(drag,dict): return None,error('DRAG_TRAJECTORY_REQUIRED','Drag requires a bounded linear trajectory.','policy')
 start,end=drag.get('start'),drag.get('end'); steps=drag.get('steps'); duration=drag.get('durationMs')
 if not (isinstance(start,list) and isinstance(end,list) and len(start)==len(end)==2 and all(isinstance(x,(int,float)) for x in start+end)):
  return None,error('DRAG_TRAJECTORY_REQUIRED','Drag start and end must be numeric points.','policy')
 if not isinstance(steps,int) or not 2<=steps<=64 or not isinstance(duration,int) or not 100<=duration<=2000:
  return None,error('DRAG_TRAJECTORY_REQUIRED','Drag must use 2..64 steps over 100..2000ms.','policy')
 points=[[round(start[j]+(end[j]-start[j])*i/steps,3) for j in (0,1)] for i in range(steps+1)]
 return {'kind':'linear','steps':steps,'durationMs':duration,'points':points},None
def main():
 # Hold a cross-process lock through check/dispatch/checkpoint. Kernel releases it
 # on crash; the durable in-flight marker then forbids any automatic replay.
 try:
  root=safe_root(os.environ.get('DESKTOP_RUNS_ROOT','/tmp/desktop-runs'))
  with journal_lock(root) as journal:
   return run_main(journal)
 except FocusGuardError as exc:
  emit(sys.argv[1] if len(sys.argv)>1 else '', 'focus-guard-error','blocked',err=error(exc.code,'Guard validation or budget failed. Preserve any unknown checkpoint; do not replay an uncertain Return.','conflict',False,{},'Re-observe the outcome without input. Never bypass an unknown checkpoint with a new key or scope.'))
  return 25
 except (OSError,ValueError,KeyError,TypeError):
  emit(sys.argv[1] if len(sys.argv)>1 else '', 'checkpoint-error','blocked',err=error('CHECKPOINT_UNAVAILABLE','Local checkpoint or evidence could not be safely read or written; do not replay an uncertain action.','storage',False,{},'Preserve the journal and inspect the outcome before recovery.'))
  return 31
def run_main(journal):
 ap=argparse.ArgumentParser(); ap.add_argument('command',nargs='?'); ap.add_argument('--input'); ap.add_argument('--request-id'); ap.add_argument('--timeout-ms',type=int,default=30000); ap.add_argument('--idempotency-key'); ap.add_argument('--expected-revision',type=int); ap.add_argument('--approval-file'); ap.add_argument('--approval'); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--run-root'); ap.add_argument('--version',action='store_true'); a=ap.parse_args()
 if a.version: print(VERSION); return 0
 cmd=a.command or ''; rid=a.request_id or 'req_'+uuid.uuid4().hex; started=time.time(); guard_started=time.monotonic()
 try:
  inp=json.loads(a.input or '{}')
  if not isinstance(inp,dict): raise ValueError()
 except Exception: emit(cmd,rid,'failed',err=error('INVALID_INPUT','--input must be a JSON object.')); return 10
 secrets=sensitive_values(inp)
 identity_input={k:v for k,v in inp.items() if k!='outputMode'}
 scope=str(pathlib.Path(a.run_root).resolve()) if a.run_root else 'default'
 request={'command':cmd,'input':redact(identity_input),'idempotencyKey':a.idempotency_key,'expectedRevision':a.expected_revision,'scope':scope}; request_digest=digest({**request,'input':identity_input})
 policy_error=forbidden_request(inp)
 if policy_error:
  emit(cmd,rid,'blocked',err=policy_error,started=started); return 31
 if STOP.search(json.dumps(inp)):
  emit(cmd,rid,'blocked',err=error('HUMAN_VERIFICATION','Automation stopped before protected interaction.','policy',False,{},'Complete verification manually, then resume after re-observation.'),started=started); return 32
 contracts=json.loads((pathlib.Path(__file__).parent/'command_contracts.json').read_text())['commands']
 if cmd=='capabilities': emit(cmd,rid,'succeeded',{'version':VERSION,'backend':backend(),'backendAvailable':pathlib.Path(backend()).is_file(),'commands':contracts},started=started); return 0
 if cmd=='environment.preflight':
  checks={'backend':pathlib.Path(backend()).is_file(),'display':bool(os.environ.get('DISPLAY')),'dbus':bool(os.environ.get('DBUS_SESSION_BUS_ADDRESS')),'atspi':bool(shutil.which('pgrep') and subprocess.run(['pgrep','-f','at-spi'],capture_output=True).returncode==0)}; warnings=[] if checks['dbus'] else ['D-Bus session address absent; portal actions unavailable. Start within a desktop session or export its bus address.']; ok=checks['backend'] and checks['atspi']; emit(cmd,rid,'succeeded' if ok else 'blocked',checks,None if ok else error('AT_SPI_UNAVAILABLE','AT-SPI registry or backend unavailable.','backend',True,checks,'Start at-spi2-registryd in the target desktop session; do not use coordinate fallback.'),warnings,started=started); return 0 if ok else 24
 if cmd not in contracts: emit(cmd,rid,'failed',err=error('INVALID_INPUT','Unknown command.')); return 10
 if cmd in SESSION_LIFECYCLE:
  emit(cmd,rid,'blocked',err=error('SESSION_LIFECYCLE_FORBIDDEN','Desktop attaches to an existing session but never creates, replaces, recovers, or closes the desktop/X session.','policy',False,{'contract':'existing-session-only','command':cmd},'Use session.list/session.get and environment.preflight for observation; provision or recover disposable sessions outside Desktop.'),started=started); return 31
 mutation=cmd not in OBS
 if 'args' in inp and (not isinstance(inp['args'],list) or not all(isinstance(x,str) and '\x00' not in x for x in inp['args'])):
  emit(cmd,rid,'failed',err=error('INVALID_INPUT','args must be an array of strings.'),started=started); return 10
 if cmd=='keyboard.type':
  args=inp.get('args'); text_mode=inp.get('textMode','append')
  if not isinstance(args,list) or len(args)!=1 or not isinstance(args[0],str) or '\x00' in args[0] or text_mode not in {'append','replace'}:
   emit(cmd,rid,'failed',err=error('INVALID_INPUT','keyboard.type requires exactly one text string and textMode append or replace.'),started=started); return 10
  if text_mode=='replace' and (not isinstance(inp.get('target'),dict) or inp['target'].get('kind') not in {'coordinate','image'}):
   emit(cmd,rid,'blocked',err=error('UNSUPPORTED_TEXT_MODE','Atomic replace currently requires an explicitly bound image or coordinate input-field target.','policy'),started=started); return 31
 if cmd in {'keyboard.key','keyboard.shortcut'}:
  args=inp.get('args')
  if not isinstance(args,list) or len(args)!=1 or not isinstance(args[0],str) or not re.fullmatch(r'[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*',args[0]):
   emit(cmd,rid,'failed',err=error('INVALID_INPUT','Supply exactly one key or chord per command; key arrays are not sequences.'),started=started); return 10
 if 'postCapture' in inp and (cmd!='keyboard.key' or inp.get('args')!=['Return'] or type(inp['postCapture']) is not bool):
  emit(cmd,rid,'failed',err=error('INVALID_INPUT','postCapture is a boolean supported only for keyboard.key args [Return].'),started=started); return 10
 guard_error=focus_guard_error(cmd,inp)
 if guard_error:emit(cmd,rid,'blocked',err=guard_error,started=started); return 31
 preparing='prepareFocusGuard' in inp
 if preparing and (cmd!='ui.observe' or inp['prepareFocusGuard'] is not True or not isinstance(inp.get('target'),dict) or window_number(inp['target'].get('windowId')) is None or inp.get('args') not in (None,[])):
  emit(cmd,rid,'failed',err=error('INVALID_FOCUS_GUARD','prepareFocusGuard requires targeted ui.observe with an exact window ID and no args.'),started=started); return 10
 guarded='focusGuard' in inp
 # Bundled observation and human_input bind to :99. Never validate a different
 # display then dispatch there; aliases are not proven equivalent. Do not rewrite env.
 if (guarded or preparing) and (os.environ.get('DISPLAY')!=':99' or (guarded and inp['focusGuard']['observation']['display']['display']!=':99')):
  emit(cmd,rid,'blocked',err=error('FOCUS_GUARD_DISPLAY_UNSUPPORTED','Guard preparation and guarded Return require exact DISPLAY=:99 and a :99 guard snapshot.','policy',False,{},'Use only an independently provisioned existing :99 session; do not change DISPLAY or bypass the guard.'),started=started); return 25
 guard_budget=GuardBudget(a.timeout_ms,guard_started) if guarded or preparing else None
 if mutation and not a.idempotency_key: emit(cmd,rid,'failed',err=error('INVALID_INPUT','Mutation requires --idempotency-key.')); return 10
 if cmd in PORTAL_ACTIONS and not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
  details={'dbusSessionAddress':False,'command':cmd,'display':os.environ.get('DISPLAY') or None}
  emit(cmd,rid,'blocked',err=error('DBUS_SESSION_UNAVAILABLE','A desktop D-Bus session is required for portal-backed interaction.','backend',True,details,'Run inside the target graphical login session and export DBUS_SESSION_BUS_ADDRESS; then re-observe the dialog. Coordinates are not a safe substitute.'),warnings=['No backend or artifact was invoked or created.'],started=started); return 22
 if cmd in PRECISION_ACTIONS:
  policy_error=precision_error(inp)
  if not policy_error and cmd=='pointer.drag-drop':_,policy_error=validate_drag(inp)
  if not policy_error and cmd in PRECISION_CLICKS and inp.get('args') not in (None,[]):policy_error=error('INVALID_INPUT','Precision clicks accept no independent selector arguments.')
  if policy_error:emit(cmd,rid,'blocked',err=policy_error,started=started); return 31
 if inp.get('outputMode','compact') not in {'compact','full'}:
  emit(cmd,rid,'failed',err=error('INVALID_INPUT','outputMode must be compact or full.')); return 10
 try:receipt=valid_approval(a.approval_file,request_digest,a.approval)
 except (ValueError,OSError):
  emit(cmd,rid,'failed',err=error('INVALID_APPROVAL','Approval must be one valid digest-bound JSON receipt, inline or file.'),started=started); return 10
 needs_approval=mutation and cmd not in S1
 if needs_approval and not (a.dry_run or receipt): emit(cmd,rid,'blocked',{'preview':request,'requestDigest':request_digest},error('APPROVAL_REQUIRED','Fresh digest-bound approval required.','policy'),approval={'requestDigest':request_digest,'safetyClass':'S4' if cmd in S4 else 'S2'},started=started); return 30
 run=safe_root(a.run_root); state=journal/(digest(scope)+'.json')
 if state.is_symlink():raise ValueError('journal state symlink refused')
 legacy=run/'state.json'
 if legacy.is_symlink():raise ValueError('legacy state symlink refused')
 st=json.loads(state.read_text()) if state.exists() else (json.loads(legacy.read_text()) if legacy.exists() else {'revision':0,'idempotency':{}})
 if not isinstance(st,dict) or type(st.get('revision')) is not int or not isinstance(st.get('idempotency'),dict):raise ValueError('invalid checkpoint')
 if any(not isinstance(v,dict) or v.get('status') not in {'succeeded','outcome_unknown'} or not isinstance(v.get('digest'),str) or not isinstance(v.get('result'),dict) for v in st['idempotency'].values()):raise ValueError('invalid checkpoint record')
 if a.expected_revision is not None and a.expected_revision!=st['revision']: emit(cmd,rid,'failed',err=error('REVISION_CONFLICT','Expected revision does not match.','conflict'),revision=st['revision'],started=started); return 41
 if mutation and a.idempotency_key in st['idempotency']:
  old=st['idempotency'][a.idempotency_key]
  if old['digest']!=request_digest: emit(cmd,rid,'failed',err=error('IDEMPOTENCY_CONFLICT','Key reused with different request.','conflict'),revision=st['revision'],started=started); return 41
  if old.get('status')=='outcome_unknown':
   emit(cmd,rid,'blocked',old.get('result') or {},error('OUTCOME_UNKNOWN','The prior action may have executed; automatic replay is forbidden.','conflict',False,{},'Inspect the current UI and resolve the checkpoint with a new idempotency key only after confirming the outcome.'),revision=st['revision'],started=started); return 40
  emit(cmd,rid,'succeeded',old['result'],revision=st['revision'],started=started); return 0
 if a.dry_run: emit(cmd,rid,'succeeded',{'preview':request,'requestDigest':request_digest,'wouldExecute':True,'shapeValidated':cmd in (PRECISION_ACTIONS|{'keyboard.key','keyboard.shortcut'}),'liveTargetValidated':False},approval={'required':needs_approval,'safetyClass':'S4' if cmd in S4 else 'S2'},revision=st['revision'],started=started); return 0
 if cmd.startswith(('task.','session.')): result={'state':'prepared' if cmd=='task.plan' else 'completed','checkpointToken':'cp_'+request_digest[:24],'input':redact(inp)}
 else:
  if not pathlib.Path(backend()).is_file(): emit(cmd,rid,'blocked',err=error('BACKEND_UNAVAILABLE','Installed system desktop CLI unavailable.','backend',True),started=started); return 22
  if cmd in PRECISION_ACTIONS:
   policy_error=precision_error(inp)
   if policy_error: emit(cmd,rid,'blocked',err=policy_error,revision=st['revision'],started=started); return 31
   trajectory=None
   if cmd=='pointer.drag-drop':
    trajectory,policy_error=validate_drag(inp)
    if policy_error: emit(cmd,rid,'blocked',err=policy_error,revision=st['revision'],started=started); return 31
   target=inp['target']; observation={}; precision_screenshot=run/'precision-observe.png'; observe_argv=[backend()]+MAP['ui.observe']+['--screenshot',str(precision_screenshot)]
   for observation_attempt in range(2):
    observed,timeout=backend_call(observe_argv,a.timeout_ms)
    if timeout=='display_state_unavailable': emit(cmd,rid,'blocked',err=error('DISPLAY_STATE_UNAVAILABLE','Display geometry and DPI could not be snapshotted before dispatch.','backend',False),revision=st['revision'],started=started); return 25
    if isinstance(timeout,dict): emit(cmd,rid,'blocked',err=error('DESKTOP_STATE_CHANGED','Display geometry or DPI changed during the operation.','conflict',False,timeout),revision=st['revision'],started=started); return 25
    if timeout: emit(cmd,rid,'failed',err=error('TIMEOUT','Re-observation deadline exceeded before any input.','backend',True,{'phase':'observe','attempt':observation_attempt+1}),revision=st['revision'],started=started,attempt=observation_attempt+1,max_attempts=2); return 21
    if observed.returncode:
     result=backend_result(observed,observe_argv); code='AT_SPI_UNAVAILABLE' if observed.returncode==4 else 'TARGET_NOT_FOUND'; emit(cmd,rid,'failed',scrub(redact(result),secrets),error(code,'Accessibility observation failed before action.','backend',code=='AT_SPI_UNAVAILABLE',{'phase':'observe'}),revision=st['revision'],started=started); return 24 if observed.returncode==4 else 20
    observation=parsed_stdout(observed)
    if target['kind']!='accessibility' and observation.get('accessibilityMatch'):
     emit(cmd,rid,'blocked',err=error('ACCESSIBILITY_TARGET_AVAILABLE','Accessible target found; visual/coordinate fallback is forbidden.','policy'),revision=st['revision'],started=started); return 31
    if observation_matches(observation,target): break
   else:
    emit(cmd,rid,'failed',err=error('STALE_TARGET','Target identity changed after bounded re-observation.','conflict',False,{'observedRevision':observation.get('revision'),'observedTargetDigest':observation.get('targetDigest')},'Acquire a new target and fresh digest-bound approval.'),revision=st['revision'],started=started); return 20
   identity=target_identity(observation,target)
   if not identity or not identity.get('focused',False):
    focus_argv=[backend()]+MAP['app.focus']+[str(target['windowId'])]
    focused,timeout=backend_call(focus_argv,a.timeout_ms)
    if timeout=='display_state_unavailable': emit(cmd,rid,'blocked',err=error('DISPLAY_STATE_UNAVAILABLE','Display geometry and DPI could not be snapshotted before dispatch.','backend',False),revision=st['revision'],started=started); return 25
    if isinstance(timeout,dict): emit(cmd,rid,'blocked',err=error('DESKTOP_STATE_CHANGED','Display geometry or DPI changed during the operation.','conflict',False,timeout),revision=st['revision'],started=started); return 25
    if timeout or focused.returncode: emit(cmd,rid,'failed',err=error('FOCUS_NOT_VERIFIED','Target window could not be focused before action.','backend',False),revision=st['revision'],started=started); return 20
    verified,timeout=backend_call(observe_argv,a.timeout_ms); verified_observation=parsed_stdout(verified) if verified else {}
    verified_identity=target_identity(verified_observation,target)
    if timeout=='display_state_unavailable': emit(cmd,rid,'blocked',err=error('DISPLAY_STATE_UNAVAILABLE','Display geometry and DPI could not be snapshotted before dispatch.','backend',False),revision=st['revision'],started=started); return 25
    if isinstance(timeout,dict): emit(cmd,rid,'blocked',err=error('DESKTOP_STATE_CHANGED','Display geometry or DPI changed during the operation.','conflict',False,timeout),revision=st['revision'],started=started); return 25
    if timeout or verified.returncode or not observation_matches(verified_observation,target) or not verified_identity or not verified_identity.get('focused',False):
     emit(cmd,rid,'failed',err=error('FOCUS_NOT_VERIFIED','Focus or target identity changed before action.','conflict',False),revision=st['revision'],started=started); return 20
   before_geometry=xwindow_geometry(target['windowId'])
   if target['kind']!='accessibility' and (cmd in PRECISION_CLICKS or cmd in {'keyboard.type','pointer.drag-drop'}):
    argv=safe_pointer_argv(target,cmd,inp.get('args',[]),trajectory,inp.get('textMode','append'))
   else:
    argv=[backend()]+MAP.get(cmd,[cmd.replace('.','-')])+[str(x) for x in inp.get('args',[])]
    if trajectory:argv+=['--trajectory-json',json.dumps(trajectory,separators=(',',':'))]
   st['idempotency'][a.idempotency_key]={'digest':request_digest,'status':'outcome_unknown','result':{'checkpointToken':'cp_'+request_digest[:24]}}
   atomic_state(state,st)
   p,timeout=backend_call(argv,a.timeout_ms)
   if timeout=='display_state_unavailable': emit(cmd,rid,'blocked',err=error('DISPLAY_STATE_UNAVAILABLE','Display geometry and DPI could not be snapshotted before dispatch.','backend',False),revision=st['revision'],started=started); return 25
   if isinstance(timeout,dict): emit(cmd,rid,'blocked',err=error('DESKTOP_STATE_CHANGED','Display geometry or DPI changed during the operation.','conflict',False,timeout),revision=st['revision'],started=started); return 25
   if timeout:
    emit(cmd,rid,'partial',st['idempotency'][a.idempotency_key]['result'],error('OUTCOME_UNKNOWN','Action deadline expired after dispatch; it will not be replayed.','backend',False,{'phase':'action'}),revision=st['revision'],started=started); return 40
   result={'exitCode':p.returncode,'stderr':p.stderr}
   if p.returncode:result['stdout']=p.stdout
   if not p.returncode:
    if target['kind']=='accessibility':
     verify_argv=[backend()]+MAP['ui.verify']+[json.dumps(inp['postcondition'],separators=(',',':'))]; verified,verify_timeout=backend_call(verify_argv,a.timeout_ms)
     if verify_timeout=='display_state_unavailable': emit(cmd,rid,'blocked',err=error('DISPLAY_STATE_UNAVAILABLE','Display geometry and DPI could not be snapshotted during verification.','backend',False),revision=st['revision'],started=started); return 25
     if isinstance(verify_timeout,dict): emit(cmd,rid,'blocked',err=error('DESKTOP_STATE_CHANGED','Display geometry or DPI changed during verification.','conflict',False,verify_timeout),revision=st['revision'],started=started); return 25
     confirmed=not verify_timeout and not verified.returncode; verification={'backendVerify':confirmed}
    else:
     before_visual=after_visual=None
     if inp['postcondition'].get('visualRegionChanged') is True and target.get('visualRegion'):
      post_screenshot=run/'precision-postcondition.png'; captured,capture_timeout=backend_call([backend()]+MAP['screen.capture']+[str(post_screenshot)],a.timeout_ms)
      if capture_timeout=='display_state_unavailable': emit(cmd,rid,'blocked',err=error('DISPLAY_STATE_UNAVAILABLE','Display geometry and DPI could not be snapshotted during visual QA.','backend',False),revision=st['revision'],started=started); return 25
      if isinstance(capture_timeout,dict): emit(cmd,rid,'blocked',err=error('DESKTOP_STATE_CHANGED','Display geometry or DPI changed during visual QA.','conflict',False,capture_timeout),revision=st['revision'],started=started); return 25
      if not capture_timeout and captured.returncode==0:
       try:
        before_visual=png_region_digest(precision_screenshot,target['visualRegion']); after_visual=png_region_digest(post_screenshot,target['visualRegion'])
        result['afterScreenshot']={'path':str(post_screenshot),'sha256':hashlib.sha256(post_screenshot.read_bytes()).hexdigest(),'bytes':post_screenshot.stat().st_size}
       except (OSError,ValueError,zlib.error):pass
     confirmed,verification=verify_effect(inp['postcondition'],target,before_geometry,trajectory,before_visual,after_visual)
    result['verification']=verification
    if not confirmed:
     result['checkpointToken']='cp_'+request_digest[:24]
     emit(cmd,rid,'partial',scrub(redact(result),secrets),error('OUTCOME_UNKNOWN','Action returned but its postcondition was not confirmed; replay is forbidden.','backend',False,{'phase':'postcondition'}),revision=st['revision'],started=started); return 40
    result['postconditionConfirmed']=True
    if trajectory: result['trajectory']=trajectory
  else:
   args=[str(x) for x in inp.get('args',[])]
   if cmd=='screen.capture' and not args:args=[str(run/'screenshot.png')]
   if cmd=='ui.observe' and 'target' in inp:
    if args or not isinstance(inp['target'],dict):
     emit(cmd,rid,'failed',err=error('INVALID_INPUT','Target observation requires a target object and no positional arguments.'),started=started); return 10
    args=['--screenshot',str(run/'target-observe.png')]
   if cmd=='window.move' and len(args)==3:argv=[shutil.which('xdotool') or 'xdotool','windowmove',args[0],args[1],args[2]]
   else:argv=[backend()]+MAP.get(cmd,[cmd.replace('.','-')])+args
   if inp.get('postCapture') is True:
    capture_baseline=guard_budget.metrics() if guard_budget else display_metrics()
    if capture_baseline is None:
     emit(cmd,rid,'blocked',err=error('DISPLAY_STATE_UNAVAILABLE','Cannot bind action and capture to a display.','backend',False),started=started); return 25
    if capture_baseline.get('display')!=':99':
     emit(cmd,rid,'blocked',err=error('CAPTURE_DISPLAY_UNSUPPORTED','Bundled capture provenance is currently verified only for existing display :99.','policy',False),started=started); return 25
   if mutation:
    st['idempotency'][a.idempotency_key]={'digest':request_digest,'status':'outcome_unknown','result':{'checkpointToken':'cp_'+request_digest[:24]}}
    atomic_state(state,st)
   if guarded:
    target=inp['target']; guard=inp['focusGuard']
    expected={'windowId':str(guard['windowId']),'pid':guard['pid'],'display':guard['observation']['display']}
    observation,_=guard_observe(guard_budget,run,target,expected)
    if not observation_matches(observation,{**target,'windowId':target_identity(observation,target)['windowId']}):raise FocusGuardError('STALE_TARGET')
    before_bounds=guard_budget.geometry(target['windowId'])
    p,timeout=backend_call(argv,a.timeout_ms,budget=guard_budget,before_dispatch=lambda:guard_budget.identity(target['windowId'],expected))
   elif preparing:
    observation,prepared_identity=guard_observe(guard_budget,run,inp['target'])
    p=subprocess.CompletedProcess(argv,0,json.dumps(observation),''); timeout=None
   else:p,timeout=backend_call(argv,a.timeout_ms)
   if timeout=='display_state_unavailable': emit(cmd,rid,'blocked',err=error('DISPLAY_STATE_UNAVAILABLE','Display geometry and DPI could not be snapshotted before dispatch.','backend',False),started=started); return 25
   if isinstance(timeout,dict): emit(cmd,rid,'blocked',err=error('DESKTOP_STATE_CHANGED','Display geometry or DPI changed during the operation.','conflict',False,timeout),started=started); return 25
   if timeout:
    emit(cmd,rid,'partial' if mutation else 'failed',err=error('OUTCOME_UNKNOWN' if mutation else 'TIMEOUT','Backend deadline exceeded before a confirmed side effect.','backend',not mutation,{'phase':'observation' if not mutation else 'mutation'}),started=started); return 40 if mutation else 21
   result=backend_result(p,argv)
   if guarded and not p.returncode:
    if guard_budget.geometry(target['windowId'])!=before_bounds:raise FocusGuardError('POSTCONDITION_NOT_CONFIRMED')
    guard_budget.identity(target['windowId'],expected)
    result['verification']={'activeWindowMatch':True,'windowBoundsUnchanged':True,'semanticOutcomeVerified':False}
    result['postconditionConfirmed']=True
   if cmd=='window.list' and not p.returncode and inp.get('outputMode')!='full':
    windows=parsed_stdout(p).get('windows')
    if isinstance(windows,list):
     sanitized=scrub(redact(parsed_stdout(p)),secrets)
     safe_result={**scrub(redact(result),secrets),'stdout':json.dumps(sanitized,ensure_ascii=False)}
     data=json.dumps(safe_result,ensure_ascii=False).encode()
     details=run/('windows-'+uuid.uuid4().hex[:12]+'.json')
     with os.fdopen(os.open(str(details),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as stream:stream.write(data)
     result={'windows':windows,'activeWindowKnown':False,'exitCode':p.returncode,'stderr':p.stderr,'details':{'path':str(details),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'omitted':['stdout','backendArgv'],'truncated':False}}
   if cmd=='ui.observe' and not p.returncode:
    observation=parsed_stdout(p)
    if 'target' not in inp or inp.get('outputMode')=='full':result['observation']=observation_index(observation)
    if 'target' in inp:
     target=dict(inp['target'])
     if target.get('kind') not in {'accessibility','coordinate','image'}:
      emit(cmd,rid,'failed',err=error('INVALID_INPUT','Unsupported target kind.'),started=started); return 10
     if target.get('kind')=='accessibility' and target.get('name') and target.get('nodeId') is None:
      matches=[n for n in observation.get('nodes',[]) if n.get('name')==target['name']]
      if len(matches)!=1:
       emit(cmd,rid,'failed',scrub(redact(result),secrets),err=error('TARGET_AMBIGUOUS','Target name must match exactly one node; use a nodeId.'),started=started); return 20
     identity=target_identity(observation,target)
     if not identity or not identity.get('windowId'):
      emit(cmd,rid,'failed',scrub(redact(result),secrets),err=error('TARGET_NOT_FOUND','Cannot bind this target to the current observation.'),started=started); return 20
     if target.get('windowId') is not None and (window_number(target['windowId'])!=window_number(identity['windowId']) if preparing else str(target['windowId'])!=identity['windowId']):
      emit(cmd,rid,'failed',scrub(redact(result),secrets),err=error('STALE_TARGET','Requested window is not the observed active window.'),started=started); return 20
     target.update({k:identity[k] for k in ('windowId','observedRevision','targetDigest') if not (preparing and k=='windowId')})
     if identity.get('screenshotDigest'):target['screenshotDigest']=identity['screenshotDigest']
     if target.get('kind')=='accessibility':target['nodeId']=identity['nodeId']
     if inp.get('outputMode')!='full':
      details=run/('observation-'+uuid.uuid4().hex[:12]+'.json'); sanitized=scrub(redact(observation),secrets)
      data=json.dumps({'stdout':json.dumps(sanitized,ensure_ascii=False),'observation':sanitized},ensure_ascii=False).encode()
      with os.fdopen(os.open(str(details),os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600),'wb') as stream:stream.write(data)
      result={'target':target,'exitCode':p.returncode,'stderr':p.stderr,'details':{'path':str(details),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'omitted':['stdout','observationIndex'],'truncated':False}}
     else:result={'target':target,**result}
     result['targetPreparationOnly']=True
     if preparing:
      prepared_guard={'windowId':target['windowId'],'pid':prepared_identity['pid'],'observation':{'revision':target['observedRevision'],'digest':target['targetDigest'],'display':prepared_identity['display']}}
      check=focus_guard_error('keyboard.key',{'args':['Return'],'target':target,'focusGuard':prepared_guard,'postcondition':{'activeWindowMatch':True,'windowBoundsUnchanged':True},'visionFallbackSupported':inp.get('visionFallbackSupported')})
      if check:emit(cmd,rid,'blocked',err=check,started=started); return 31
      guard_budget.identity(target['windowId'],prepared_identity)
      result['focusGuard']=prepared_guard
  if p.returncode: code='AT_SPI_UNAVAILABLE' if p.returncode==4 else 'TARGET_NOT_FOUND'; emit(cmd,rid,'failed',scrub(redact(result),secrets),error(code,'System desktop CLI failed.','backend',code=='AT_SPI_UNAVAILABLE'),started=started); return 24 if p.returncode==4 else 20
  if cmd=='app.launch' and re.search(r'window not detected|window (?:was )?not found',p.stdout+'\n'+p.stderr,re.I):
   emit(cmd,rid,'failed',scrub(redact(result),secrets),error('POSTCONDITION_NOT_CONFIRMED','The process launch returned but no application window was observed.','backend',False,{'phase':'launch-observation'},'Inspect the launch command or file association; do not treat process creation as a visible GUI success.'),started=started); return 20
 if inp.get('postCapture') is True:
  # Already-dispatched key is never repeated for a capture failure.
  result['postCapture']={'status':'failed','actionDispatchConfirmed':True,'semanticOutcomeVerified':False}
  observed_display=guard_budget.metrics() if guard_budget else display_metrics()
  if observed_display is None or observed_display!=capture_baseline:
   code='DISPLAY_STATE_UNAVAILABLE' if observed_display is None else 'DESKTOP_STATE_CHANGED'
   emit(cmd,rid,'blocked',result,error(code,'Display could not be verified across action and capture.','conflict',False),started=started); return 25
  remaining_ms=guard_budget.seconds()*1000 if guard_budget else a.timeout_ms-int((time.time()-started)*1000)
  capture_error='timeout'; captured=None
  try:
   if remaining_ms>0:
    private=pathlib.Path(tempfile.mkdtemp(prefix='capture-',dir=run))
    shot=private/'after-return.png'
    old_umask=os.umask(0o077)
    try:captured,capture_error=backend_call([backend(),'screenshot',str(shot)],min(remaining_ms,2000),**({'budget':guard_budget} if guard_budget else {}))
    finally:os.umask(old_umask)
   observed_display=guard_budget.metrics() if guard_budget else display_metrics()
   if capture_error=='display_state_unavailable' or observed_display is None or observed_display!=capture_baseline or (isinstance(capture_error,dict) and capture_error.get('code')!='backend_unavailable'):
    code='DISPLAY_STATE_UNAVAILABLE' if capture_error=='display_state_unavailable' or observed_display is None else 'DESKTOP_STATE_CHANGED'
    emit(cmd,rid,'blocked',result,error(code,'Display verification failed after key dispatch; do not replay.','conflict',False),started=started); return 25
   if not capture_error and captured.returncode==0:
    data=verified_capture_bytes(shot)
    if (guard_budget.seconds() if guard_budget else a.timeout_ms-(time.time()-started)*1000)>0:
     result['afterScreenshot']={'path':str(shot),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'display':capture_baseline}
     result['postCapture']['status']='captured'
   if result['postCapture']['status']=='failed':
    result['postCapture']['reason']='CAPTURE_TIMEOUT' if capture_error=='timeout' or (time.time()-started)*1000>=a.timeout_ms else 'CAPTURE_BACKEND_UNAVAILABLE' if isinstance(capture_error,dict) else 'CAPTURE_UNAVAILABLE'
  except (OSError,ValueError,struct.error,zlib.error,ImportError):result['postCapture']['reason']='CAPTURE_UNAVAILABLE'
 result=scrub(redact(result),secrets)
 if mutation: st['revision']+=1; st['idempotency'][a.idempotency_key]={'digest':request_digest,'status':'succeeded','result':result}; atomic_state(state,st)
 ev=run/'events.jsonl'; seq=sum(1 for _ in ev.open())+1 if ev.exists() else 1; ev.open('a').write(json.dumps({'sequence':seq,'at':now(),'command':cmd,'requestDigest':request_digest,'status':'succeeded'})+'\n')
 emit(cmd,rid,'succeeded',result,revision=st['revision'],started=started); return 0
if __name__=='__main__': raise SystemExit(main())
