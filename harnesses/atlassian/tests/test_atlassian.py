import io,json,os,stat,subprocess,sys,time
from pathlib import Path
from urllib.error import HTTPError
import pytest
sys.path.insert(0,str(Path(__file__).parents[1])); import atlassian as a; import oauth3lo as o

def sites(tmp_path,auth=None):
 p=tmp_path/'sites.json'; p.write_text(json.dumps({'sites':{'one':{'jiraBaseUrl':'https://api.atlassian.com/ex/jira/cloud-one','confluenceBaseUrl':'https://api.atlassian.com/ex/confluence/cloud-one','auth':auth or {'type':'oauth','tokenRef':'env:TEST_TOKEN'}},'two':{'jiraBaseUrl':'https://api.atlassian.com/ex/jira/cloud-two','confluenceBaseUrl':'https://api.atlassian.com/ex/confluence/cloud-two','auth':{'type':'oauth','tokenRef':'env:OTHER_TOKEN'}}}})); p.chmod(0o600); return p
class Response:
 def __init__(self,data): self.data=json.dumps(data).encode()
 def __enter__(self): return self
 def __exit__(self,*x): pass
 def read(self): return self.data

def ns(**kw):
 base=dict(command='jira.issues.get',site='one',sites_file=None,params=None,body=None,dry_run=False,confirm=None,idempotency_key=None,input_path=None,transfer_root=None,client_path=None,output_path=None,sites_output_path=None,site_alias=None,resource_url=None,managed_browser_devtools_url=None,smoke_tests=None,overwrite=False,max_upload_bytes=1024,timeout_ms=100,retries=0,all_pages=False,max_pages=10,max_items=1000,issueIdOrKey='A-1',commentId=None,projectIdOrKey=None,pageId=None,spaceId=None); base.update(kw); return type('N',(),base)()
def test_auth_reference_and_redaction(tmp_path,monkeypatch):
 monkeypatch.setenv('TEST_TOKEN','supersecret'); s=a.get_site('one',sites(tmp_path)); assert a.authorization(s).startswith('Bearer '); assert 'supersecret' not in json.dumps(a.redact({'Authorization':a.authorization(s)}))
def test_auth_file_permissions(tmp_path):
 token=tmp_path/'token'; token.write_text('x'); token.chmod(0o644)
 with pytest.raises(a.Failure) as e:a.secret('file:'+str(token))
 assert e.value.code=='auth_permissions'
def test_path_safety(tmp_path):
 root=tmp_path/'root'; root.mkdir(); good=root/'x'; good.write_text('x'); assert a.safe_path(good,root)==good.resolve()
 with pytest.raises(a.Failure): a.safe_path(tmp_path/'escape',root)
def test_one_time_request_bound_confirm(tmp_path,monkeypatch):
 monkeypatch.setenv('ATLASSIAN_STATE_DIR',str(tmp_path/'state')); d=a.preview('x','one','/p',{},None); a.consume(d,'x','one','/p',{},None)
 with pytest.raises(a.Failure): a.consume(d,'x','one','/p',{},None)
def test_mutation_preview_without_auth(tmp_path):
 n=ns(command='jira.issues.create',issueIdOrKey=None,sites_file=str(sites(tmp_path)),body='{"fields":{}}',dry_run=True); out=a.execute(n); assert out['dryRun'] and out['confirm']
def test_tenant_isolation(tmp_path,monkeypatch):
 monkeypatch.setenv('TEST_TOKEN','one-token'); monkeypatch.setenv('OTHER_TOKEN','two-token'); p=sites(tmp_path); assert a.get_site('one',p)['jiraBaseUrl']!=a.get_site('two',p)['jiraBaseUrl']
def test_multipart_contains_bytes(tmp_path):
 p=tmp_path/'x.bin'; p.write_bytes(b'ACTUAL-BYTES'); body,ctype=a.multipart(p); assert b'ACTUAL-BYTES' in body and 'multipart/form-data' in ctype

def test_bounds():
 n=ns(timeout_ms=1)
 with pytest.raises(a.Failure): a.bounds(n)

def test_site_config_permissions(tmp_path):
 p=sites(tmp_path); p.chmod(0o644)
 with pytest.raises(a.Failure): a.load_sites(p)

def test_provider_body_not_leaked():
 def op(req,timeout): raise HTTPError(req.full_url,400,'bad',{},io.BytesIO(b'secret content'))
 with pytest.raises(a.Failure) as e:a.request('GET','https://x',{},None,1,0,op)
 assert 'secret' not in e.value.message

def test_idempotency_conflict(tmp_path,monkeypatch):
 monkeypatch.setenv('ATLASSIAN_STATE_DIR',str(tmp_path/'state')); n=ns(idempotency_key='k'); a.idem(n,'one',{'x':1})
 with pytest.raises(a.Failure): a.idem(n,'two')

def test_symlink_component_rejected(tmp_path):
 root=tmp_path/'root'; real=tmp_path/'real'; real.mkdir(); (real/'x').write_text('x'); root.symlink_to(real,target_is_directory=True)
 with pytest.raises(a.Failure): a.safe_path(root/'x',root)

def test_batch_partial_and_systemic_stop(tmp_path,monkeypatch):
 p=sites(tmp_path); monkeypatch.delenv('TEST_TOKEN',raising=False); monkeypatch.setenv('ATLASSIAN_STATE_DIR',str(tmp_path/'state'))
 batch=json.dumps([{'command':'jira.issues.get','site':'one','sites_file':str(p),'issue_id_or_key':'A-1'},{'command':'jira.issues.get','site':'two','sites_file':str(p),'issue_id_or_key':'A-2'}]); n=ns(batch=batch)
 out=a.run_batch(n); assert len(out['items'])==1 and out['stopped'] and out['items'][0]['error']['code']=='auth_missing'

def test_rate_limit_retry():
 calls=[]
 def op(req,timeout):
  calls.append(1)
  if len(calls)==1: raise HTTPError(req.full_url,429,'rate',{'Retry-After':'0'},io.BytesIO(b'limited'))
  return Response({'ok':1})
 assert a.request('GET','https://x',{},None,1,1,op,lambda _:None)=={'ok':1}
def test_timeout_ambiguous_mutation():
 def op(*x,**y): raise TimeoutError()
 with pytest.raises(a.Failure) as e:a.request('POST','https://x',{},None,1,0,op)
 assert e.value.ambiguous and e.value.code=='timeout'
def test_partial_failure_is_stable():
 e=a.Failure('conflict','partial',False,False); assert e.code=='conflict'
def test_cli_subprocess_lists_sites(tmp_path):
 p=sites(tmp_path); cli=Path(__file__).parents[1]/'atlassian.py'; cli.chmod(0o755); r=subprocess.run([str(cli),'auth.sites.list','--sites-file',str(p)],text=True,capture_output=True); data=json.loads(r.stdout); assert r.returncode==0 and data['data']['sites']==['one','two']
def test_pagination_start_at():
 pages=[{'issues':[{'id':'1'}],'startAt':0,'maxResults':1,'total':2},{'issues':[{'id':'2'}],'startAt':1,'maxResults':1,'total':2}]
 def op(req,timeout): return Response(pages.pop(0))
 n=ns(all_pages=True,max_pages=2,max_items=2,sites_file='unused'); out=a.paginate({},'https://x?startAt=0',{},n,op); assert len(out['items'])==2 and out['pages']==2

def test_manifest_argmap_and_required_identifiers():
 manifest=json.loads((Path(__file__).parents[1]/'harness.json').read_text()); cmd=manifest['commands']['jira.issues.comments.update']; args={x['arg'] for x in cmd['argMap']}
 assert {'sitesFile','issueIdOrKey','commentId','batch','allPages','maxUploadBytes'}<=args
 assert cmd['inputSchema']['additionalProperties'] is False and {'site','issueIdOrKey','commentId'}<=set(cmd['inputSchema']['required'])

def test_oauth_service_urls_are_separate(tmp_path):
 s=a.get_site('one',sites(tmp_path)); assert '/ex/jira/' in s['jiraBaseUrl'] and '/ex/confluence/' in s['confluenceBaseUrl']

def test_basic_origin_defaults_both_services(tmp_path):
 p=tmp_path/'basic.json'; p.write_text(json.dumps({'sites':{'b':{'baseUrl':'https://basic.atlassian.net','auth':{'type':'basic','email':'x@y','tokenRef':'env:X'}}}})); p.chmod(0o600); s=a.get_site('b',p); assert s['jiraBaseUrl']==s['confluenceBaseUrl']

def test_confirmation_concurrency(tmp_path,monkeypatch):
 import threading
 monkeypatch.setenv('ATLASSIAN_STATE_DIR',str(tmp_path/'state')); token=a.preview('x','one','/p',{},None); results=[]
 def use():
  try:a.consume(token,'x','one','/p',{},None); results.append('ok')
  except a.Failure:results.append('rejected')
 ts=[threading.Thread(target=use) for _ in range(2)]; [t.start() for t in ts]; [t.join() for t in ts]; assert sorted(results)==['ok','rejected']

def test_main_effect_and_page_envelopes(tmp_path,monkeypatch,capsys):
 monkeypatch.setenv('ATLASSIAN_STATE_DIR',str(tmp_path/'state')); p=sites(tmp_path); a.main(['jira.issues.create','--site','one','--sites-file',str(p),'--body','{}','--dry-run']); out=json.loads(capsys.readouterr().out); assert out['effects'][0]['status']=='planned' and out['provenance']['service']=='jira' and 'page' in out

def test_batch_shape_validation():
 n=ns(batch='{}')
 with pytest.raises(a.Failure) as e:a.run_batch(n)
 assert e.value.code=='batch_invalid'

def test_oauth_client_requires_fixed_loopback_and_core_scopes(tmp_path):
 p=tmp_path/'client.json'; p.write_text(json.dumps({'oauth2':{'client_id':'id','client_secret':'secret','redirect_uri':'https://remote.example/cb','scopes':['offline_access','read:me']}})); p.chmod(0o600)
 with pytest.raises(o.OAuthFailure) as e:o._client(p)
 assert e.value.code=='oauth_redirect_invalid'


def test_oauth_login_writes_private_bundle_and_site_alias(tmp_path,monkeypatch):
 root=tmp_path/'private'; root.mkdir(mode=0o700); client=root/'client.json'; scopes=['offline_access','read:me','read:jira-work','read:confluence-content.all']
 client.write_text(json.dumps({'oauth2':{'client_id':'id','client_secret':'secret','redirect_uri':'http://127.0.0.1:8765/oauth/atlassian/callback','scopes':scopes}})); client.chmod(0o600)
 done=__import__('threading').Event(); done.set(); monkeypatch.setattr(o,'_receiver',lambda *args,**kwargs:({'code':'one-time-code'},done))
 def opener(req,timeout):
  url=req.full_url
  if url==o.TOKEN_URL:return Response({'access_token':'access','refresh_token':'refresh','expires_in':3600,'scope':' '.join(scopes)})
  if url==o.RESOURCES_URL:return Response([{'id':'cloud','name':'Work','url':'https://work.atlassian.net','scopes':scopes}])
  if url==o.ME_URL:return Response({'account_id':'acct'})
  if '/rest/api/3/myself' in url:return Response({'accountId':'acct'})
  if '/wiki/api/v2/spaces' in url:return Response({'results':[]})
  raise AssertionError(url)
 out=o.login(transfer_root=root,client_path='client.json',output_path='credential.json',sites_output_path='sites.json',site_alias='work',resource_url='https://work.atlassian.net',managed_browser_devtools_url='http://127.0.0.1:18800',opener=opener,open_devtools=lambda *x:True)
 encoded=json.dumps(out); assert out['desktopLocal'] and out['siteAlias']=='work' and '"access_token"' not in encoded and '"refresh_token"' not in encoded and 'one-time-code' not in encoded
 for name in ('credential.json','sites.json'): assert stat.S_IMODE((root/name).stat().st_mode)==0o600
 site=json.loads((root/'sites.json').read_text())['sites']['work']; assert site['jiraBaseUrl'].endswith('/cloud') and site['auth']['type']=='oauth'
 assert a.secret(site['auth']['tokenRef'])=='access'


def test_oauth_refresh_rotates_both_tokens(tmp_path):
 root=tmp_path/'private'; root.mkdir(mode=0o700); p=root/'credential.json'; p.write_text(json.dumps({'type':'atlassian-oauth-3lo','client_id':'id','client_secret':'secret','refresh_token':'old','access_token':'old-access','site_alias':'work','scopes':['offline_access'],'expires_at':0})); p.chmod(0o600)
 out=o.refresh(transfer_root=root,output_path='credential.json',opener=lambda req,timeout:Response({'access_token':'new-access','refresh_token':'new-refresh','expires_in':10,'scope':'offline_access'}))
 saved=json.loads(p.read_text()); assert out['rotated'] and saved['access_token']=='new-access' and saved['refresh_token']=='new-refresh'


def test_oauth_rejects_aliased_paths_and_public_root(tmp_path):
 public=tmp_path/'public'; public.mkdir(mode=0o755); client=public/'client.json'; client.write_text('{}'); client.chmod(0o600)
 with pytest.raises(o.OAuthFailure) as e:o._private_path(public,'client.json',existing=True)
 assert e.value.code=='oauth_permissions'
 root=tmp_path/'private2'; root.mkdir(mode=0o700); client=root/'same.json'; client.write_text(json.dumps({'oauth2':{'client_id':'id','client_secret':'secret','redirect_uri':'http://127.0.0.1:8765/oauth/atlassian/callback','scopes':['offline_access','read:me']}})); client.chmod(0o600)
 with pytest.raises(o.OAuthFailure) as e:o.login(transfer_root=root,client_path='same.json',output_path='same.json',sites_output_path='sites.json',site_alias='work',resource_url='https://work.atlassian.net',managed_browser_devtools_url='http://127.0.0.1:18800',overwrite=True)
 assert e.value.code=='oauth_path_invalid'


def test_oauth_refresh_is_serialized(tmp_path):
 import threading
 root=tmp_path/'private'; root.mkdir(mode=0o700); p=root/'credential.json'; p.write_text(json.dumps({'type':'atlassian-oauth-3lo','client_id':'id','client_secret':'secret','refresh_token':'old','access_token':'old-access','site_alias':'work','scopes':['offline_access'],'expires_at':0})); p.chmod(0o600); calls=[]; guard=threading.Lock()
 def opener(req,timeout):
  supplied=json.loads(req.data)['refresh_token']
  with guard: calls.append(supplied)
  return Response({'access_token':'a-'+supplied,'refresh_token':'r1' if supplied=='old' else 'r2','expires_in':10,'scope':'offline_access'})
 results=[]
 def rotate(): results.append(o.refresh(transfer_root=root,output_path='credential.json',opener=opener)['rotated'])
 ts=[threading.Thread(target=rotate) for _ in range(2)]; [t.start() for t in ts]; [t.join() for t in ts]
 assert results==[True,True] and calls==['old','r1'] and json.loads(p.read_text())['refresh_token']=='r2'


def test_oauth_refresh_requires_preview_confirmation(tmp_path,monkeypatch):
 monkeypatch.setenv('ATLASSIAN_STATE_DIR',str(tmp_path/'state'))
 out=a.execute(ns(command='auth.oauth.refresh',site=None,transfer_root='/private',output_path='credential.json',dry_run=True,timeout_ms=30000))
 assert out['dryRun'] and out['request']=={'operation':'rotate-oauth-credentials'} and out['confirm']


def test_connected_skill_and_harness_identity_is_aligned():
 manifest=json.loads(Path('harnesses/atlassian/harness.json').read_text())
 skill=Path('skills/atlassian/SKILL.md').read_text()
 assert manifest['name']=='atlassian' and manifest['title']=='Atlassian'
 assert 'name: atlassian' in skill and '# Atlassian\n' in skill


def test_oauth_manifest_contracts_are_typed():
 manifest=json.loads((Path(__file__).parents[1]/'harness.json').read_text())
 login=manifest['commands']['auth.oauth.login']; assert {'secretUse','humanAccountAction','externalSideEffect'}<=set(login['safetyClasses'])
 refresh=manifest['commands']['auth.oauth.refresh']; assert {'secretUse','authReuse','humanAccountAction','externalSideEffect'}<=set(refresh['safetyClasses']) and manifest['authModel']['storesSecrets'] is True
 assert set(manifest['commands']['auth.oauth.status']['safetyClasses'])=={'secretUse','readOnly'}
 assert {'transferRoot','clientPath','outputPath','sitesOutputPath','siteAlias','resourceUrl','managedBrowserDevtoolsUrl'}<=set(login['inputSchema']['required'])


def test_contract_inventory():
 assert len(a.CONTRACTS)==29 and all(x.startswith(('auth.','jira.','confluence.')) for x in a.CONTRACTS)
