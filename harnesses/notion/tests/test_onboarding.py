import json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).parents[1]/"notion.py"; F=Path(__file__).parent/"fixtures"
def run(*args,env=None):
 p=subprocess.run([sys.executable,str(P),*map(str,args)],text=True,capture_output=True,env={**os.environ,**(env or {})});return p.returncode,json.loads(p.stdout)
def data(*args,**kw):return run(*args,**kw)[1]["data"]
def test_plan_is_pure_and_paths(tmp_path):
 s=tmp_path/'s';o=data('onboard.plan','--state-path',s,'--auth-mode','oauth');assert not s.exists() and not o['external_effects_performed'] and 'client configuration' in o['paths']['oauth']
def test_happy_handoffs_resume_idempotency_and_secret_free(tmp_path):
 s=tmp_path/'state';f=F/'onboard_happy.json';o=data('onboard.start','--state-path',s,'--workspace','Acme','--adapter-fixture',f);assert o['handoff']['reason']=='login_required';r=o['revision']
 o=data('onboard.resume','--state-path',s,'--expected-revision',r,'--approve-handoffs','login_required','--adapter-fixture',f);assert o['handoff']['reason']=='permission_approval_required';r=o['revision']
 o=data('onboard.resume','--state-path',s,'--expected-revision',r,'--approve-handoffs','permission_approval_required,root_approval_required','--adapter-fixture',f);assert o['handoff']['reason']=='secret_capture_required';assert 'token' not in s.read_text().lower()
 r=o['revision'];o=data('onboard.resume','--state-path',s,'--expected-revision',r,'--adapter-fixture',f,env={'NOTION_TOKEN':'ntn_fixture_should_never_persist'});assert o['status']=='verification_required' and 'fixture_should' not in s.read_text()
 o2=data('onboard.start','--state-path',s,'--workspace','Acme','--adapter-fixture',f);assert o2['idempotent'] and o2['session_id']==o['session_id']
def test_login_mfa_permission_and_captcha(tmp_path):
 for reason in ['mfa_required','permission_approval_required']:
  f=tmp_path/(reason+'.json');f.write_text(json.dumps({'steps':[reason]}));o=data('onboard.start','--state-path',tmp_path/(reason+'.state'),'--workspace','Acme','--adapter-fixture',f);assert o['handoff']['reason']==reason
 o=data('onboard.start','--state-path',tmp_path/'cap','--workspace','Acme','--adapter-fixture',F/'onboard_captcha.json');assert o['handoff']['reason']=='captcha_required'
def test_wrong_workspace_stale_cancel_timeout_and_status_pure(tmp_path):
 f=tmp_path/'wrong.json';f.write_text(json.dumps({'steps':[{'kind':'select_workspace','workspace':'Other'}]}));s=tmp_path/'s';o=data('onboard.start','--state-path',s,'--workspace','Acme','--adapter-fixture',f,'--now',100,'--session-timeout',30);assert o['status']=='failed' and o['handoff']['reason']=='wrong_workspace'
 f.write_text(json.dumps({'steps':['login_required']}));s=tmp_path/'s2';o=data('onboard.start','--state-path',s,'--workspace','Acme','--adapter-fixture',f,'--now',100,'--session-timeout',30);before=s.read_bytes();data('onboard.status','--state-path',s,'--now',101);assert s.read_bytes()==before
 rc,e=run('onboard.resume','--state-path',s,'--expected-revision',99,'--adapter-fixture',f,'--now',101);assert rc==2 and 'stale revision' in e['error']['message']
 o=data('onboard.cancel','--state-path',s,'--expected-revision',o['revision'],'--now',102);assert o['status']=='cancelled'
 s=tmp_path/'s3';o=data('onboard.start','--state-path',s,'--workspace','Acme','--adapter-fixture',f,'--now',100,'--session-timeout',30);o=data('onboard.status','--state-path',s,'--now',131);assert o['status']=='timed_out' and o['handoff']['reason']=='timeout'
def test_state_redaction_and_no_screen_audit(tmp_path):
 f=tmp_path/'f';f.write_text(json.dumps({'steps':[{'kind':'login_required','instructions':'Bearer shouldhide','screenshot':'secret_abcdefghi'}]}));s=tmp_path/'s';o=data('onboard.start','--state-path',s,'--workspace','Acme','--adapter-fixture',f);raw=s.read_text();assert 'shouldhide' not in raw and 'screenshot' not in raw
def test_contract_commands_and_safety():
 h=json.loads((P.parent/'harness.json').read_text());assert h['commands']['onboard.status']['safetyClasses']==['readOnly'];assert h['commands']['onboard.resume']['safetyClasses']==['externalSideEffect','secretUse','authReuse'];assert h['commands']['onboard.resume']['inputSchema']['required']==['expectedRevision']
