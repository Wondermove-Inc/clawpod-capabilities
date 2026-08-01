import json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).parents[1];CLI=ROOT/'notion.py';FIX=Path(__file__).parent/'fixtures/onboard_happy.json'
def run(*a,env=None):return json.loads(subprocess.run([sys.executable,str(CLI),*map(str,a)],capture_output=True,text=True,env={**os.environ,**(env or {})},check=True).stdout)['data']
with tempfile.TemporaryDirectory() as d:
 root=Path(d)/'private';root.mkdir(mode=0o700);base=['--state-root',root,'--session','smoke'];env={'NOTION_ONBOARD_TEST_MODE':'1','NOTION_ONBOARD_TEST_FIXTURE':str(FIX)}
 plan=run('onboard.plan','--workspace','Acme');desktop=run('onboard.desktop.task','--workspace','Acme');start=run('onboard.start',*base,'--workspace','Acme',env=env);mid=run('onboard.resume',*base,'--expected-revision',start['revision'],'--approve-handoffs','login_required',env=env);capture=run('onboard.resume',*base,'--expected-revision',mid['revision'],'--approve-handoffs','permission_approval_required,root_approval_required',env=env)
 assert not plan['external_effects_performed'] and desktop['pure'];assert capture['handoff']['reason']=='secret_capture_required';assert 'ntn_' not in (root/'smoke'/'state.json').read_text();print(f"SMOKE OK: confined state; pure desktop plan; secret_capture_required; revision={capture['revision']}")
