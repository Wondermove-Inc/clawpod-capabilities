#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, pathlib, re, shutil, subprocess, time, uuid
VERSION='3.0.0'; SCHEMA='desktop.v3'; STOP=re.compile(r'captcha|recaptcha|hcaptcha|turnstile|verify you are human|human verification|bot detection',re.I)
OBS=set('capabilities environment.preflight session.list session.get app.list app.get window.list window.get screen.list screen.capture ui.observe ui.find ui.read ui.table ui.wait ui.verify image.locate dialog.inspect clipboard.inspect download.inspect task.get task.events task.artifacts'.split())
S1=set('app.launch app.focus window.activate window.move window.resize window.minimize window.maximize window.restore pointer.move pointer.scroll keyboard.key keyboard.shortcut'.split())
S4={'window.close','process.terminate','process.kill'}
MAP={'app.list':['apps','--json'],'screen.capture':['screenshot'],'ui.observe':['observe','--json'],'ui.find':['find'],'ui.read':['read'],'ui.table':['table','--json'],'ui.wait':['wait'],'ui.verify':['verify'],'image.locate':['locate-image'],'app.launch':['open'],'app.focus':['focus'],'app.close':['close'],'pointer.click':['click'],'pointer.double-click':['dblclick'],'pointer.right-click':['rclick'],'pointer.scroll':['scroll'],'keyboard.type':['type'],'keyboard.key':['key'],'keyboard.shortcut':['key'],'keyboard.select':['select'],'image.click':['click-image']}
def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def redact(v):
 if isinstance(v,dict): return {k:('[REDACTED]' if re.search(r'pass|secret|token|otp|authorization|clipboard',k,re.I) else redact(x)) for k,x in v.items()}
 if isinstance(v,list): return [redact(x) for x in v]
 return v
def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def safe_root(p):
 root=pathlib.Path(os.environ.get('DESKTOP_RUNS_ROOT','/workspace/desktop-runs')).resolve(); q=pathlib.Path(p or root/f'run-{uuid.uuid4().hex[:12]}')
 if q.exists() and q.is_symlink(): raise ValueError('run root symlink refused')
 q=q.resolve()
 if q!=root and root not in q.parents: raise ValueError('run root outside approved root')
 q.mkdir(parents=True,exist_ok=True); return q
def error(code,msg,category='validation',retryable=False,details=None,remediation='Correct the request and retry.'):
 return {'code':code,'message':msg,'category':category,'retryable':retryable,'details':details or {},'remediation':remediation}
def emit(cmd,rid,status,result=None,err=None,warnings=None,approval=None,revision=0,started=None,attempt=1,max_attempts=1):
 end=time.time(); o={'schemaVersion':SCHEMA,'requestId':rid,'command':cmd,'status':status,'revision':revision,'result':result or {},'error':err,'warnings':warnings or [],'artifacts':[],'approval':approval,'timing':{'startedAt':dt.datetime.fromtimestamp(started or end,dt.timezone.utc).isoformat(),'endedAt':now(),'durationMs':int((end-(started or end))*1000)},'retry':{'attempt':attempt,'maxAttempts':max_attempts,'retryable':bool(err and err.get('retryable'))}}; print(json.dumps(o,ensure_ascii=False,separators=(',',':')))
def backend(): return os.environ.get('DESKTOP_SYSTEM_CLI','/workspace/skills/desktop/desktop')
def valid_approval(path,request_digest):
 if not path:return None
 p=pathlib.Path(path)
 if p.is_symlink(): raise ValueError('approval symlink refused')
 x=json.loads(p.read_text()); return x if x.get('requestDigest')==request_digest and x.get('expiresAt','')>now() else None
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('command',nargs='?'); ap.add_argument('--input'); ap.add_argument('--request-id'); ap.add_argument('--timeout-ms',type=int,default=30000); ap.add_argument('--idempotency-key'); ap.add_argument('--expected-revision',type=int); ap.add_argument('--approval-file'); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--run-root'); ap.add_argument('--version',action='store_true'); a=ap.parse_args()
 if a.version: print(VERSION); return 0
 cmd=a.command or ''; rid=a.request_id or 'req_'+uuid.uuid4().hex; started=time.time()
 try:
  inp=json.loads(a.input or '{}')
  if not isinstance(inp,dict): raise ValueError()
 except Exception: emit(cmd,rid,'failed',err=error('INVALID_INPUT','--input must be a JSON object.')); return 10
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
 receipt=valid_approval(a.approval_file,request_digest)
 needs_approval=mutation and cmd not in S1
 if needs_approval and not (a.dry_run or receipt): emit(cmd,rid,'blocked',{'preview':request,'requestDigest':request_digest},error('APPROVAL_REQUIRED','Fresh digest-bound approval required.','policy'),approval={'requestDigest':request_digest,'safetyClass':'S4' if cmd in S4 else 'S2'},started=started); return 30
 run=safe_root(a.run_root); state=run/'state.json'; st=json.loads(state.read_text()) if state.exists() else {'revision':0,'idempotency':{}}
 if a.expected_revision is not None and a.expected_revision!=st['revision']: emit(cmd,rid,'failed',err=error('REVISION_CONFLICT','Expected revision does not match.','conflict'),revision=st['revision'],started=started); return 41
 if mutation and a.idempotency_key in st['idempotency']:
  old=st['idempotency'][a.idempotency_key]
  if old['digest']!=request_digest: emit(cmd,rid,'failed',err=error('IDEMPOTENCY_CONFLICT','Key reused with different request.','conflict'),revision=st['revision'],started=started); return 41
  emit(cmd,rid,'succeeded',old['result'],revision=st['revision'],started=started); return 0
 if a.dry_run: emit(cmd,rid,'succeeded',{'preview':request,'requestDigest':request_digest,'wouldExecute':True},approval={'required':needs_approval,'safetyClass':'S4' if cmd in S4 else 'S2'},revision=st['revision'],started=started); return 0
 if cmd.startswith(('task.','session.')) or cmd in {'dialog.inspect','clipboard.inspect','download.inspect','window.list','window.get','app.get','screen.list'}: result={'state':'prepared' if cmd=='task.plan' else 'completed','checkpointToken':'cp_'+request_digest[:24],'input':redact(inp)}
 else:
  if not pathlib.Path(backend()).is_file(): emit(cmd,rid,'blocked',err=error('BACKEND_UNAVAILABLE','Installed system desktop CLI unavailable.','backend',True),started=started); return 22
  argv=[backend()]+MAP.get(cmd,[cmd.replace('.','-')])+[str(x) for x in inp.get('args',[])]
  try: p=subprocess.run(argv,capture_output=True,text=True,timeout=max(1,min(a.timeout_ms,120000))/1000,env={**os.environ,'DESKTOP_FAST_INPUT':'1'}); result={'exitCode':p.returncode,'stdout':p.stdout[-8000:],'stderr':p.stderr[-4000:],'backendArgv':[pathlib.Path(argv[0]).name]+argv[1:]}
  except subprocess.TimeoutExpired: emit(cmd,rid,'failed',err=error('TIMEOUT','Backend deadline exceeded.','backend',True),started=started); return 21
  if p.returncode: code='AT_SPI_UNAVAILABLE' if p.returncode==4 else 'TARGET_NOT_FOUND'; emit(cmd,rid,'failed',redact(result),error(code,'System desktop CLI failed.','backend',code=='AT_SPI_UNAVAILABLE'),started=started); return 24 if p.returncode==4 else 20
 result=redact(result)
 if mutation: st['revision']+=1; st['idempotency'][a.idempotency_key]={'digest':request_digest,'result':result}; state.write_text(json.dumps(st,indent=2))
 ev=run/'events.jsonl'; seq=sum(1 for _ in ev.open())+1 if ev.exists() else 1; ev.open('a').write(json.dumps({'sequence':seq,'at':now(),'command':cmd,'requestDigest':request_digest,'status':'succeeded'})+'\n')
 emit(cmd,rid,'succeeded',result,revision=st['revision'],started=started); return 0
if __name__=='__main__': raise SystemExit(main())
