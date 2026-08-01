import json,os,stat,subprocess,sys
from pathlib import Path
P=Path(__file__).parents[1]/'notion.py';F=Path(__file__).parent/'fixtures'
def private(tmp):p=tmp/'root';p.mkdir(mode=0o700,parents=True);return p
def run(*args,env=None):
 p=subprocess.run([sys.executable,str(P),*map(str,args)],text=True,capture_output=True,env={**os.environ,**(env or {})});return p.returncode,json.loads(p.stdout)
def data(*a,**kw):return run(*a,**kw)[1]['data']
def tenv(f):return {'NOTION_ONBOARD_TEST_MODE':'1','NOTION_ONBOARD_TEST_FIXTURE':str(f)}
def base(root):return ['--state-root',root,'--session','case']
def test_plan_and_desktop_plan_are_pure(tmp_path):
 root=private(tmp_path);before=list(root.iterdir());p=data('onboard.plan','--workspace','Acme');d=data('onboard.desktop.task','--workspace','Acme','--roots',json.dumps([{'type':'page','id':'123456781234123412341234567890ab'}]));assert list(root.iterdir())==before and not p['external_effects_performed'] and d['pure'] and not d['live_selectors_validated'];assert not d['rules']['capture_screenshots'] and 'ui_drift' in d['rules']['stop_on'] and any(x.get('reason')=='permission_approval_required' for x in d['steps'])
def test_private_path_happy_handoffs_and_secret_free(tmp_path):
 root=private(tmp_path);a=base(root);e=tenv(F/'onboard_happy.json');o=data('onboard.start',*a,'--workspace','Acme',env=e);assert o['handoff']['reason']=='login_required';o=data('onboard.resume',*a,'--expected-revision',o['revision'],'--approve-handoffs','login_required',env=e);o=data('onboard.resume',*a,'--expected-revision',o['revision'],'--approve-handoffs','permission_approval_required,root_approval_required',env=e);assert o['handoff']['reason']=='secret_capture_required';state=root/'case'/'state.json';assert stat.S_IMODE(state.stat().st_mode)==0o600 and 'token' not in state.read_text().lower();o=data('onboard.resume',*a,'--expected-revision',o['revision'],env={**e,'NOTION_TOKEN':'ntn_fixture_should_never_persist'});assert o['status']=='verification_required' and 'fixture_should' not in state.read_text()
def test_path_traversal_missing_root_public_root_and_symlinks(tmp_path):
 missing=tmp_path/'missing';rc,o=run('onboard.start','--state-root',missing,'--session','x','--workspace','Acme');assert rc==2 and 'already exist' in o['error']['message']
 root=private(tmp_path);rc,o=run('onboard.start','--state-root',root,'--session','../escape','--workspace','Acme');assert rc==2 and 'bounded relative' in o['error']['message']
 public=tmp_path/'public';public.mkdir(mode=0o755);rc,o=run('onboard.start','--state-root',public,'--session','x','--workspace','Acme');assert rc==2 and 'private' in o['error']['message']
 target=private(tmp_path/'target');link=tmp_path/'link';link.symlink_to(target,True);rc,o=run('onboard.start','--state-root',link,'--session','x','--workspace','Acme');assert rc==2 and 'symlink' in o['error']['message']
 (root/'bad').symlink_to(target,True);rc,o=run('onboard.start','--state-root',root,'--session','bad','--workspace','Acme');assert rc==2 and 'real child' in o['error']['message']
 session=root/'filelink';session.mkdir(mode=0o700);victim=tmp_path/'victim';victim.write_text('{}');(session/'state.json').symlink_to(victim);rc,o=run('onboard.start','--state-root',root,'--session','filelink','--workspace','Acme');assert rc==2 and 'non-symlink' in o['error']['message']
def test_fixture_injection_rejected_without_test_mode(tmp_path):
 root=private(tmp_path);rc,o=run('onboard.start',*base(root),'--workspace','Acme',env={'NOTION_ONBOARD_TEST_FIXTURE':str(F/'onboard_happy.json')});assert rc==2 and 'disabled' in o['error']['message']
def test_mfa_permission_captcha_and_no_capture(tmp_path):
 for reason in ['mfa_required','permission_approval_required']:
  f=tmp_path/(reason+'.json');f.write_text(json.dumps({'steps':[reason]}));root=private(tmp_path/reason);o=data('onboard.start',*base(root),'--workspace','Acme',env=tenv(f));assert o['handoff']['reason']==reason
 root=private(tmp_path/'cap');o=data('onboard.start',*base(root),'--workspace','Acme',env=tenv(F/'onboard_captcha.json'));assert o['handoff']['reason']=='captcha_required'
 f=tmp_path/'screen.json';f.write_text(json.dumps({'steps':[{'kind':'login_required','instructions':'Bearer shouldhide','screenshot':'secret_abcdefghi','dom':'private'}]}));root=private(tmp_path/'screen');o=data('onboard.start',*base(root),'--workspace','Acme',env=tenv(f));raw=(root/'case'/'state.json').read_text();assert 'shouldhide' not in raw and 'screenshot' not in raw and 'dom' not in raw
def test_revision_cancel_timeout_status_pure_and_idempotent(tmp_path):
 root=private(tmp_path);a=base(root);e=tenv(F/'onboard_happy.json');o=data('onboard.start',*a,'--workspace','Acme','--now',100,'--session-timeout',30,env=e);again=data('onboard.start',*a,'--workspace','Acme',env=e);assert again['idempotent'] and again['session_id']==o['session_id'];state=root/'case'/'state.json';before=state.read_bytes();status=data('onboard.status',*a,'--now',131);assert status['status']=='timed_out' and state.read_bytes()==before;rc,err=run('onboard.resume',*a,'--expected-revision',99,env=e);assert rc==2 and 'stale revision' in err['error']['message'];o=data('onboard.cancel',*a,'--expected-revision',o['revision'],'--now',102);assert o['status']=='cancelled'
def test_wrong_workspace_and_contract_has_no_fixture_or_arbitrary_path(tmp_path):
 f=tmp_path/'wrong.json';f.write_text(json.dumps({'steps':[{'kind':'select_workspace','workspace':'Other'}]}));root=private(tmp_path);o=data('onboard.start',*base(root),'--workspace','Acme',env=tenv(f));assert o['handoff']['reason']=='wrong_workspace'
 h=json.loads((P.parent/'harness.json').read_text());blob=json.dumps({k:v for k,v in h['commands'].items() if k.startswith('onboard.')});assert 'adapterFixture' not in blob and 'statePath' not in blob;assert h['commands']['onboard.start']['inputSchema']['required']==['stateRoot','session','workspace'];assert h['commands']['onboard.desktop.task']['safetyClasses']==['readOnly']
