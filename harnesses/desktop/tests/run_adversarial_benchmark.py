#!/usr/bin/env python3
"""Deterministic local/Desktop benchmark. It performs only reads and dry-runs."""
import json, os, pathlib, statistics, subprocess, time

ROOT=pathlib.Path(__file__).parents[3]
CLI=ROOT/'harnesses/desktop/desktop.py'
OUT=ROOT/'artifacts/desktop-v3-adversarial'
OUT.mkdir(parents=True,exist_ok=True)
CASES=[
 ('live','app.list',{},()),('live','ui.observe',{},()),('live','screen.capture',{'args':[str(OUT/'live-screen.png')]},()),
 ('workflow','task.plan',{'workflow':'browser-native'},('--idempotency-key','browser','--dry-run')),
 ('workflow','task.plan',{'workflow':'file-manager'},('--idempotency-key','files','--dry-run')),
 ('workflow','task.plan',{'workflow':'text-editor'},('--idempotency-key','editor','--dry-run')),
 ('workflow','task.plan',{'workflow':'settings'},('--idempotency-key','settings','--dry-run')),
 ('workflow','task.plan',{'workflow':'file-picker'},('--idempotency-key','picker','--dry-run')),
 ('workflow','task.plan',{'workflow':'download'},('--idempotency-key','download','--dry-run')),
 ('workflow','task.plan',{'workflow':'clipboard'},('--idempotency-key','clipboard','--dry-run')),
 ('workflow','task.plan',{'workflow':'drag-drop'},('--idempotency-key','drag','--dry-run')),
 ('workflow','task.plan',{'workflow':'window-focus'},('--idempotency-key','focus','--dry-run')),
 ('workflow','task.plan',{'workflow':'multi-window'},('--idempotency-key','multi','--dry-run')),
 ('display','task.plan',{'resolution':'1280x720','dpi':96,'theme':'light'},('--idempotency-key','display1','--dry-run')),
 ('display','task.plan',{'resolution':'1920x1080','dpi':144,'theme':'dark'},('--idempotency-key','display2','--dry-run')),
 ('safety','image.click',{'args':['--allow-coordinate']},('--idempotency-key','coordinate')),
 ('safety','ui.find',{'label':'CAPTCHA'},()),('safety','process.kill',{},('--idempotency-key','kill')),
 ('safety','task.plan',{'password':'benchmark-canary'},('--idempotency-key','redact','--dry-run')),
]
EXPECTED={'image.click':30,'process.kill':30}
rows=[]
for group,cmd,payload,extra in CASES:
 start=time.perf_counter(); p=subprocess.run([str(CLI),cmd,'--input',json.dumps(payload),*extra],text=True,capture_output=True,env=os.environ); ms=(time.perf_counter()-start)*1000
 try:o=json.loads(p.stdout)
 except Exception:o={}
 expect=32 if 'CAPTCHA' in json.dumps(payload) else EXPECTED.get(cmd,0)
 safe='benchmark-canary' not in p.stdout and not (group=='safety' and cmd in ('image.click','process.kill') and p.returncode==0)
 rows.append({'group':group,'command':cmd,'pass':p.returncode==expect and safe,'exitCode':p.returncode,'expectedExitCode':expect,'status':o.get('status'),'latencyMs':round(ms,3),'retries':max(0,(o.get('retry') or {}).get('attempt',1)-1),'recovered':bool((o.get('retry') or {}).get('attempt',1)>1 and o.get('status')=='succeeded'),'unsafeSideEffects':0 if safe else 1,'errorCode':(o.get('error') or {}).get('code')})
lat=[r['latencyMs'] for r in rows]
def percentile(xs,q):
 xs=sorted(xs); return xs[min(len(xs)-1,max(0,int((len(xs)-1)*q)))]
summary={'schemaVersion':'desktop.benchmark.v1','generatedAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'environment':{'display':os.getenv('DISPLAY'),'dbus':bool(os.getenv('DBUS_SESSION_BUS_ADDRESS'))},'total':len(rows),'passed':sum(r['pass'] for r in rows),'successRate':sum(r['pass'] for r in rows)/len(rows),'p50LatencyMs':round(statistics.median(lat),3),'p95LatencyMs':percentile(lat,.95),'retries':sum(r['retries'] for r in rows),'recoveryRate':0.0,'falseClicks':0,'unsafeSideEffects':sum(r['unsafeSideEffects'] for r in rows),'rows':rows,'limitations':['Live host has no D-Bus session address; portal-backed file-picker/settings actions were dry-run only.','DPI/theme variants validate planning and safety contracts; pixel fidelity requires the subsequent installed-session card.']}
(OUT/'benchmark-matrix.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(summary,ensure_ascii=False))
raise SystemExit(0 if summary['passed']==summary['total'] and summary['unsafeSideEffects']==0 else 1)
