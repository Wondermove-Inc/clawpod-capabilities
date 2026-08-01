import json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).parents[1]; CLI=ROOT/'notion.py'; FIX=Path(__file__).parent/'fixtures/onboard_happy.json'
def run(*a,env=None):
 p=subprocess.run([sys.executable,str(CLI),*map(str,a)],capture_output=True,text=True,env={**os.environ,**(env or {})},check=True);return json.loads(p.stdout)['data']
with tempfile.TemporaryDirectory() as d:
 state=Path(d)/'state.json'
 plan=run('onboard.plan','--workspace','Acme')
 start=run('onboard.start','--state-path',state,'--workspace','Acme','--adapter-fixture',FIX)
 mid=run('onboard.resume','--state-path',state,'--expected-revision',start['revision'],'--approve-handoffs','login_required','--adapter-fixture',FIX)
 capture=run('onboard.resume','--state-path',state,'--expected-revision',mid['revision'],'--approve-handoffs','permission_approval_required,root_approval_required','--adapter-fixture',FIX)
 assert not plan['external_effects_performed'];assert capture['handoff']['reason']=='secret_capture_required';assert 'ntn_' not in state.read_text()
 print(f"SMOKE OK: pure plan; secret_capture_required; revision={capture['revision']}")
