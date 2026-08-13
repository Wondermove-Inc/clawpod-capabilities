import hashlib, json, os, subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).parents[1]; CLI=ROOT/'claude_design.py'
def run(*args,env=None):
 p=subprocess.run([str(CLI),*args],text=True,capture_output=True,env=env); return p,json.loads(p.stdout)

def test_version():
 p,o=run('system.version'); assert p.returncode==0 and o['data']['version']=='0.2.0'
def test_stable_envelope():
 _,o=run('system.version'); assert {'ok','command','request_id','data','warnings','evidence','retry_safe'}<=o.keys()
def test_onboarding_plan_complete():
 _,o=run('onboarding.plan'); assert o['data']['state']=='installed_not_connected' and o['data']['official_mcp']['url']=='https://api.anthropic.com/v1/design/mcp' and 'CLI commands' in o['data']['never_delegate_to_user'] and o['data']['human_only']==['sign-in when no reusable authentication exists','MFA','provider consent','credential-use authorization']
def test_preflight_redacts_setup_token():
 env={**os.environ,'CLAUDE_CODE_OAUTH_TOKEN':'TOP_SECRET_SENTINEL'};p,o=run('onboarding.preflight',env=env)
 assert o['data']['setup_token_present'] and 'TOP_SECRET_SENTINEL' not in p.stdout
def test_onboarding_status_has_verified_state_contract():
 _,o=run('onboarding.status'); assert o['data']['connection_state'] in {'CONNECTED','NOT_CONNECTED'} and o['data']['official_mcp']['url']=='https://api.anthropic.com/v1/design/mcp' and o['data']['schema_discovered'] is False
def test_auth_contract():
 _,o=run('auth.contract'); assert o['data']['setup_token_command']=='claude setup-token' and o['data']['setup_token_persisted'] is False and o['data']['agent_owns_mcp_registration'] is True
def test_setup_token_plan_not_execute():
 _,o=run('auth.setup-token.plan'); assert o['data']['interactive'] and o['data']['command']==['claude','setup-token']
def test_login_is_human_verification():
 p,o=run('code.login.handoff'); assert p.returncode==2 and o['error']['code']=='HUMAN_VERIFICATION' and 'sign-in, MFA, or consent' in o['error']['message']
def test_mcp_uses_verified_endpoint():
 _,o=run('mcp.inspect'); assert o['data']['official_url']=='https://api.anthropic.com/v1/design/mcp' and o['data']['tool_schema_discovered'] is False
def test_mcp_validate_unavailable():
 p,o=run('mcp.validate'); assert p.returncode==2 and o['error']['code']=='BACKEND_UNAVAILABLE'
def test_mcp_install_requires_observed_transport():
 _,o=run('mcp.install-plan'); assert o['error']['code']=='INVALID_INPUT'
def test_mcp_install_plan_does_not_execute():
 _,o=run('mcp.install-plan','--mcp-url','https://observed.example/mcp'); assert o['data']['execute'] is False
def test_mcp_remove_requires_name():
 _,o=run('mcp.remove-plan'); assert o['error']['code']=='INVALID_INPUT'
def test_mcp_remove_plan():
 _,o=run('mcp.remove-plan','--mcp-name','observed-design'); assert o['data']['argv']==['claude','mcp','remove','observed-design']

@pytest.mark.parametrize('command',[ 'projects.list','projects.search','projects.present','design-systems.list','templates.list','admin.status','admin.permissions','admin.usage'])
def test_reads_require_human_reconciliation(command):
 p,o=run(command); assert p.returncode==2 and o['error']['code']=='HUMAN_VERIFICATION' and o['data']['reconciliation_source']
@pytest.mark.parametrize('command,flag',[('projects.get','--project-id'),('design-systems.get','--design-system-id'),('templates.get','--template-id')])
def test_get_requires_id(command,flag):
 _,o=run(command); assert o['error']['code']=='INVALID_INPUT'
 _,o=run(command,flag,'x'); assert o['error']['code']=='HUMAN_VERIFICATION'
@pytest.mark.parametrize('command,args',[('projects.create',['--prompt','x']),('design-systems.create',['--name','x']),('templates.create',['--name','x']),('projects.update',['--project-id','p']),('projects.iterate',['--project-id','p','--prompt','x']),('projects.edit',['--project-id','p','--patch','{}']),('design-systems.update',['--design-system-id','d']),('design-systems.remix',['--design-system-id','d']),('templates.update',['--template-id','t'])])
def test_typed_mutations_handoff(command,args):
 p,o=run(command,*args); assert p.returncode==2 and o['error']['code']=='HUMAN_VERIFICATION'
@pytest.mark.parametrize('command,idflag',[('projects.delete','--project-id'),('design-systems.delete','--design-system-id'),('templates.delete','--template-id')])
def test_delete_exact_approval(command,idflag):
 _,o=run(command,idflag,'x'); assert o['error']['code']=='APPROVAL_REQUIRED'
 _,o=run(command,idflag,'x','--exact-name','Exact','--approve'); assert o['error']['code']=='HUMAN_VERIFICATION'
@pytest.mark.parametrize('stem,args',[('projects.share',['--project-id','p','--access','workspace']),('projects.comment',['--project-id','p','--text','hi']),('projects.handoff',['--project-id','p','--destination','Claude Code']),('design-systems.publish',['--design-system-id','d']),('design-systems.set-default',['--design-system-id','d']),('destinations.handoff',['--project-id','p','--destination','Canva']),('code.sync',['--repository-path','/tmp/repo','--direction','to-design']),('admin.enable',['--organization','o']),('admin.role-update',['--member','m','--role','Claude Design Admin'])])
def test_preview_apply_exact_digest(stem,args):
 _,pre=run(stem+'.preview',*args); d=pre['data']['effect_digest']; assert len(d)==64 and pre['data']['execute'] is False
 _,bad=run(stem+'.apply',*args,'--effect-digest','bad','--approve'); assert bad['error']['code']=='APPROVAL_REQUIRED'
 p,good=run(stem+'.apply',*args,'--effect-digest',d,'--approve'); assert p.returncode==2 and good['error']['code']=='HUMAN_VERIFICATION'
def test_digest_changes_with_effect():
 _,a=run('projects.share.preview','--project-id','p','--access','workspace');_,b=run('projects.share.preview','--project-id','p','--access','public');assert a['data']['effect_digest']!=b['data']['effect_digest']
def test_export_validates_args(tmp_path):
 _,o=run('projects.export','--project-id','p','--format','docx','--output-path',str(tmp_path/'x')); assert o['error']['code']=='INVALID_INPUT'
def test_export_handoff(tmp_path):
 _,o=run('projects.export','--project-id','p','--format','pdf','--output-path',str(tmp_path/'x.pdf')); assert o['error']['code']=='HUMAN_VERIFICATION'
def test_export_verify_missing(tmp_path):
 _,o=run('projects.export.verify','--output-path',str(tmp_path/'none.pdf')); assert o['error']['code']=='NOT_FOUND'
def test_export_verify_hash_mime_bytes(tmp_path):
 f=tmp_path/'x.pdf';f.write_bytes(b'%PDF-1.4\n');_,o=run('projects.export.verify','--output-path',str(f),'--format','pdf')
 assert o['data']['bytes']==9 and o['data']['mime']=='application/pdf' and o['data']['sha256']==hashlib.sha256(f.read_bytes()).hexdigest()
def test_destinations_catalog():
 _,o=run('destinations.list'); assert {'Canva','Vercel','Claude Code'}<=set(o['data']['destinations'])
def test_unknown_unsupported():
 _,o=run('invented'); assert o['error']['code']=='UNSUPPORTED'
def test_unsafe_identifier_rejected():
 _,o=run('projects.update','--project-id','../../etc/passwd'); assert o['error']['code']=='INVALID_INPUT'
def test_manifest_contract():
 m=json.loads((ROOT/'harness.json').read_text()); assert m['name']=='claude-design' and m['title']=='Claude Design' and m['version']=='0.2.0'
 assert all(x not in (ROOT/'harness.json').read_text() for x in ['minimum','maximum','minLength','enum'])
def test_contracts_match_manifest():
 m=json.loads((ROOT/'harness.json').read_text());c=json.loads((ROOT/'command_contracts.json').read_text());assert c['commands']==list(m['commands'])
def test_no_secret_literals_in_distributables():
 text='\n'.join(p.read_text(errors='ignore') for p in ROOT.rglob('*') if p.is_file() and 'tests' not in p.parts)
 assert 'TOP_SECRET_SENTINEL' not in text
