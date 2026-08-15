#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, pathlib, re, shutil, subprocess, time, uuid
VERSION='3.0.0'; SCHEMA='desktop.v3'; STOP=re.compile(r'captcha|recaptcha|hcaptcha|turnstile|verify you are human|human verification|bot detection',re.I)
OBS=set('capabilities environment.preflight session.list session.get app.list app.get window.list window.get screen.list screen.capture ui.observe ui.find ui.read ui.table ui.wait ui.verify image.locate dialog.inspect clipboard.inspect download.inspect task.get task.events task.artifacts'.split())
S1=set('app.launch app.focus window.activate window.move window.resize window.minimize window.maximize window.restore pointer.move pointer.scroll keyboard.key keyboard.shortcut'.split())
S4={'window.close','process.terminate','process.kill'}
MAP={'app.list':['apps','--json'],'screen.capture':['screenshot'],'ui.observe':['observe','--json'],'ui.find':['find'],'ui.read':['read'],'ui.table':['table','--json'],'ui.wait':['wait'],'ui.verify':['verify'],'image.locate':['locate-image'],'app.launch':['open'],'app.focus':['focus'],'app.close':['close'],'pointer.click':['click'],'pointer.double-click':['dblclick'],'pointer.right-click':['rclick'],'pointer.scroll':['scroll'],'keyboard.type':['type'],'keyboard.key':['key'],'keyboard.shortcut':['key'],'keyboard.select':['select'],'image.click':['click-image']}
PRECISION_CLICKS={'pointer.click','pointer.double-click','pointer.right-click','image.click'}
PRECISION_ACTIONS=PRECISION_CLICKS|{'pointer.drag-drop'}
PORTAL_ACTIONS={'dialog.respond','file-dialog.open','file-dialog.save','file-dialog.choose-directory','file-dialog.cancel'}
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
def error(code,msg,category='validation',retryable=False,details=None,remediation='Correct the request and retry.'):
 return {'code':code,'message':msg,'category':category,'retryable':retryable,'details':details or {},'remediation':remediation}
def emit(cmd,rid,status,result=None,err=None,warnings=None,approval=None,revision=0,started=None,attempt=1,max_attempts=1):
 end=time.time(); o={'schemaVersion':SCHEMA,'requestId':rid,'command':cmd,'status':status,'revision':revision,'result':result or {},'error':err,'warnings':warnings or [],'artifacts':[],'approval':approval,'timing':{'startedAt':dt.datetime.fromtimestamp(started or end,dt.timezone.utc).isoformat(),'endedAt':now(),'durationMs':int((end-(started or end))*1000)},'retry':{'attempt':attempt,'maxAttempts':max_attempts,'retryable':bool(err and err.get('retryable'))}}; print(json.dumps(o,ensure_ascii=False,separators=(',',':')))
def backend(): return os.environ.get('DESKTOP_SYSTEM_CLI') or shutil.which('desktop') or '/workspace/skills/desktop/desktop'
def valid_approval(path,request_digest):
 if not path:return None
 p=pathlib.Path(path)
 if p.is_symlink(): raise ValueError('approval symlink refused')
 x=json.loads(p.read_text()); return x if x.get('requestDigest')==request_digest and x.get('expiresAt','')>now() else None
def backend_call(argv,timeout_ms):
 try:
  p=subprocess.run(argv,capture_output=True,text=True,timeout=max(1,min(timeout_ms,120000))/1000,env={**os.environ,'DESKTOP_FAST_INPUT':'1'})
  return p, None
 except subprocess.TimeoutExpired:
  return None, 'timeout'
def backend_result(p,argv):
 return {'exitCode':p.returncode,'stdout':p.stdout[-8000:],'stderr':p.stderr[-4000:],'backendArgv':[pathlib.Path(argv[0]).name]+argv[1:]}
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
 if not required.issubset(target): return error('STALE_TARGET','Target lacks fresh window, revision, or digest identity.','conflict',False)
 if kind=='accessibility' and not (target.get('nodeId') or target.get('name')): return error('PRECISION_TARGET_REQUIRED','Accessibility target requires nodeId or name.','policy')
 if kind=='image':
  if inp.get('visionFallbackSupported') is not True or not target.get('templateHash') or target.get('confidence') is None:
   return error('VISION_FALLBACK_UNSUPPORTED','Image fallback was not explicitly supported with template hash and confidence.','policy',False)
 if kind=='coordinate':
  if not all(k in target for k in ('x','y','screenshotDigest','monitor','scale')):
   return error('COORDINATE_APPROVAL_REQUIRED','Coordinate fallback requires digest-bound screen, monitor, scale, and point identity.','policy',False)
 if not isinstance(post,dict) or not post:
  return error('POSTCONDITION_REQUIRED','Click-like actions require an explicit postcondition.','policy',False,{},'Describe a read-only state that confirms the action exactly once.')
 return None
def observation_matches(observation,target):
 return (observation.get('revision')==target.get('observedRevision') and
         observation.get('targetDigest')==target.get('targetDigest') and
         observation.get('windowId')==target.get('windowId'))
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
 ap=argparse.ArgumentParser(); ap.add_argument('command',nargs='?'); ap.add_argument('--input'); ap.add_argument('--request-id'); ap.add_argument('--timeout-ms',type=int,default=30000); ap.add_argument('--idempotency-key'); ap.add_argument('--expected-revision',type=int); ap.add_argument('--approval-file'); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--run-root'); ap.add_argument('--version',action='store_true'); a=ap.parse_args()
 if a.version: print(VERSION); return 0
 cmd=a.command or ''; rid=a.request_id or 'req_'+uuid.uuid4().hex; started=time.time()
 try:
  inp=json.loads(a.input or '{}')
  if not isinstance(inp,dict): raise ValueError()
 except Exception: emit(cmd,rid,'failed',err=error('INVALID_INPUT','--input must be a JSON object.')); return 10
 secrets=sensitive_values(inp)
 request={'command':cmd,'input':redact(inp),'idempotencyKey':a.idempotency_key,'expectedRevision':a.expected_revision}; request_digest=digest(request)
 if STOP.search(json.dumps(inp)):
  emit(cmd,rid,'blocked',err=error('HUMAN_VERIFICATION','Automation stopped before protected interaction.','policy',False,{},'Complete verification manually, then resume after re-observation.'),started=started); return 32
 contracts=json.loads((pathlib.Path(__file__).parent/'command_contracts.json').read_text())['commands']
 if cmd=='capabilities': emit(cmd,rid,'succeeded',{'version':VERSION,'backend':backend(),'backendAvailable':pathlib.Path(backend()).is_file(),'commands':contracts},started=started); return 0
 if cmd=='environment.preflight':
  checks={'backend':pathlib.Path(backend()).is_file(),'display':bool(os.environ.get('DISPLAY')),'dbus':bool(os.environ.get('DBUS_SESSION_BUS_ADDRESS')),'atspi':bool(shutil.which('pgrep') and subprocess.run(['pgrep','-f','at-spi'],capture_output=True).returncode==0)}; warnings=[] if checks['dbus'] else ['D-Bus session address absent; portal actions unavailable. Start within a desktop session or export its bus address.']; ok=checks['backend'] and checks['atspi']; emit(cmd,rid,'succeeded' if ok else 'blocked',checks,None if ok else error('AT_SPI_UNAVAILABLE','AT-SPI registry or backend unavailable.','backend',True,checks,'Start at-spi2-registryd in the target desktop session; do not use coordinate fallback.'),warnings,started=started); return 0 if ok else 24
 if cmd not in contracts: emit(cmd,rid,'failed',err=error('INVALID_INPUT','Unknown command.')); return 10
 mutation=cmd not in OBS
 if mutation and not a.idempotency_key: emit(cmd,rid,'failed',err=error('INVALID_INPUT','Mutation requires --idempotency-key.')); return 10
 if cmd in PORTAL_ACTIONS and not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
  details={'dbusSessionAddress':False,'command':cmd,'display':os.environ.get('DISPLAY') or None}
  emit(cmd,rid,'blocked',err=error('DBUS_SESSION_UNAVAILABLE','A desktop D-Bus session is required for portal-backed interaction.','backend',True,details,'Run inside the target graphical login session and export DBUS_SESSION_BUS_ADDRESS; then re-observe the dialog. Coordinates are not a safe substitute.'),warnings=['No backend or artifact was invoked or created.'],started=started); return 22
 receipt=valid_approval(a.approval_file,request_digest)
 needs_approval=mutation and cmd not in S1
 if needs_approval and not (a.dry_run or receipt): emit(cmd,rid,'blocked',{'preview':request,'requestDigest':request_digest},error('APPROVAL_REQUIRED','Fresh digest-bound approval required.','policy'),approval={'requestDigest':request_digest,'safetyClass':'S4' if cmd in S4 else 'S2'},started=started); return 30
 run=safe_root(a.run_root); state=run/'state.json'; st=json.loads(state.read_text()) if state.exists() else {'revision':0,'idempotency':{}}
 if a.expected_revision is not None and a.expected_revision!=st['revision']: emit(cmd,rid,'failed',err=error('REVISION_CONFLICT','Expected revision does not match.','conflict'),revision=st['revision'],started=started); return 41
 if mutation and a.idempotency_key in st['idempotency']:
  old=st['idempotency'][a.idempotency_key]
  if old['digest']!=request_digest: emit(cmd,rid,'failed',err=error('IDEMPOTENCY_CONFLICT','Key reused with different request.','conflict'),revision=st['revision'],started=started); return 41
  if old.get('status')=='outcome_unknown':
   emit(cmd,rid,'blocked',old.get('result') or {},error('OUTCOME_UNKNOWN','The prior action may have executed; automatic replay is forbidden.','conflict',False,{},'Inspect the current UI and resolve the checkpoint with a new idempotency key only after confirming the outcome.'),revision=st['revision'],started=started); return 40
  emit(cmd,rid,'succeeded',old['result'],revision=st['revision'],started=started); return 0
 if a.dry_run: emit(cmd,rid,'succeeded',{'preview':request,'requestDigest':request_digest,'wouldExecute':True},approval={'required':needs_approval,'safetyClass':'S4' if cmd in S4 else 'S2'},revision=st['revision'],started=started); return 0
 if cmd.startswith(('task.','session.')) or cmd in {'dialog.inspect','clipboard.inspect','download.inspect','window.list','window.get','app.get','screen.list'}: result={'state':'prepared' if cmd=='task.plan' else 'completed','checkpointToken':'cp_'+request_digest[:24],'input':redact(inp)}
 else:
  if not pathlib.Path(backend()).is_file(): emit(cmd,rid,'blocked',err=error('BACKEND_UNAVAILABLE','Installed system desktop CLI unavailable.','backend',True),started=started); return 22
  if cmd in PRECISION_ACTIONS:
   policy_error=precision_error(inp)
   if policy_error: emit(cmd,rid,'blocked',err=policy_error,revision=st['revision'],started=started); return 31
   trajectory=None
   if cmd=='pointer.drag-drop':
    trajectory,policy_error=validate_drag(inp)
    if policy_error: emit(cmd,rid,'blocked',err=policy_error,revision=st['revision'],started=started); return 31
   target=inp['target']; observation={}; observe_argv=[backend()]+MAP['ui.observe']
   for observation_attempt in range(2):
    observed,timeout=backend_call(observe_argv,a.timeout_ms)
    if timeout: emit(cmd,rid,'failed',err=error('TIMEOUT','Re-observation deadline exceeded before any input.','backend',True,{'phase':'observe','attempt':observation_attempt+1}),revision=st['revision'],started=started,attempt=observation_attempt+1,max_attempts=2); return 21
    if observed.returncode:
     result=backend_result(observed,observe_argv); code='AT_SPI_UNAVAILABLE' if observed.returncode==4 else 'TARGET_NOT_FOUND'; emit(cmd,rid,'failed',scrub(redact(result),secrets),error(code,'Accessibility observation failed before action.','backend',code=='AT_SPI_UNAVAILABLE',{'phase':'observe'}),revision=st['revision'],started=started); return 24 if observed.returncode==4 else 20
    observation=parsed_stdout(observed)
    if target['kind']!='accessibility' and observation.get('accessibilityMatch'):
     emit(cmd,rid,'blocked',err=error('ACCESSIBILITY_TARGET_AVAILABLE','Accessible target found; visual/coordinate fallback is forbidden.','policy'),revision=st['revision'],started=started); return 31
    if observation_matches(observation,target): break
   else:
    emit(cmd,rid,'failed',err=error('STALE_TARGET','Target identity changed after bounded re-observation.','conflict',False,{'observedRevision':observation.get('revision'),'observedTargetDigest':observation.get('targetDigest')},'Acquire a new target and fresh digest-bound approval.'),revision=st['revision'],started=started); return 20
   if not observation.get('focused',False):
    focus_argv=[backend()]+MAP['app.focus']+[str(target['windowId'])]
    focused,timeout=backend_call(focus_argv,a.timeout_ms)
    if timeout or focused.returncode: emit(cmd,rid,'failed',err=error('FOCUS_NOT_VERIFIED','Target window could not be focused before action.','backend',False),revision=st['revision'],started=started); return 20
    verified,timeout=backend_call(observe_argv,a.timeout_ms)
    if timeout or verified.returncode or not observation_matches(parsed_stdout(verified),target) or not parsed_stdout(verified).get('focused',False):
     emit(cmd,rid,'failed',err=error('FOCUS_NOT_VERIFIED','Focus or target identity changed before action.','conflict',False),revision=st['revision'],started=started); return 20
   argv=[backend()]+MAP.get(cmd,[cmd.replace('.','-')])+[str(x) for x in inp.get('args',[])]
   if trajectory: argv+=['--trajectory-json',json.dumps(trajectory,separators=(',',':'))]
   st['idempotency'][a.idempotency_key]={'digest':request_digest,'status':'outcome_unknown','result':{'checkpointToken':'cp_'+request_digest[:24]}}
   state.write_text(json.dumps(st,indent=2))
   p,timeout=backend_call(argv,a.timeout_ms)
   if timeout:
    emit(cmd,rid,'partial',st['idempotency'][a.idempotency_key]['result'],error('OUTCOME_UNKNOWN','Action deadline expired after dispatch; it will not be replayed.','backend',False,{'phase':'action'}),revision=st['revision'],started=started); return 40
   result=backend_result(p,argv)
   if not p.returncode:
    verify_argv=[backend()]+MAP['ui.verify']+[json.dumps(inp['postcondition'],separators=(',',':'))]
    verified,timeout=backend_call(verify_argv,a.timeout_ms)
    if timeout or verified.returncode:
     result['checkpointToken']='cp_'+request_digest[:24]
     emit(cmd,rid,'partial',scrub(redact(result),secrets),error('OUTCOME_UNKNOWN','Action returned but its postcondition was not confirmed; replay is forbidden.','backend',False,{'phase':'postcondition'}),revision=st['revision'],started=started); return 40
    result['postconditionConfirmed']=True
    if trajectory: result['trajectory']=trajectory
  else:
   argv=[backend()]+MAP.get(cmd,[cmd.replace('.','-')])+[str(x) for x in inp.get('args',[])]
   p,timeout=backend_call(argv,a.timeout_ms)
   if timeout: emit(cmd,rid,'failed',err=error('TIMEOUT','Backend deadline exceeded before a confirmed side effect.','backend',not mutation,{'phase':'observation' if not mutation else 'mutation'}),started=started); return 21
   result=backend_result(p,argv)
  if p.returncode: code='AT_SPI_UNAVAILABLE' if p.returncode==4 else 'TARGET_NOT_FOUND'; emit(cmd,rid,'failed',scrub(redact(result),secrets),error(code,'System desktop CLI failed.','backend',code=='AT_SPI_UNAVAILABLE'),started=started); return 24 if p.returncode==4 else 20
 result=scrub(redact(result),secrets)
 if mutation: st['revision']+=1; st['idempotency'][a.idempotency_key]={'digest':request_digest,'status':'succeeded','result':result}; state.write_text(json.dumps(st,indent=2))
 ev=run/'events.jsonl'; seq=sum(1 for _ in ev.open())+1 if ev.exists() else 1; ev.open('a').write(json.dumps({'sequence':seq,'at':now(),'command':cmd,'requestDigest':request_digest,'status':'succeeded'})+'\n')
 emit(cmd,rid,'succeeded',result,revision=st['revision'],started=started); return 0
if __name__=='__main__': raise SystemExit(main())
