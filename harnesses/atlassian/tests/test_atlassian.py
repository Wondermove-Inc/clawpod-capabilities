import io,json,os,stat,subprocess,sys,time
from pathlib import Path
from urllib.error import HTTPError
import pytest
sys.path.insert(0,str(Path(__file__).parents[1])); import atlassian as a

def sites(tmp_path,auth=None):
 p=tmp_path/'sites.json'; p.write_text(json.dumps({'sites':{'one':{'baseUrl':'https://one.atlassian.net','auth':auth or {'type':'oauth','tokenRef':'env:TEST_TOKEN'}},'two':{'baseUrl':'https://two.atlassian.net','auth':{'type':'oauth','tokenRef':'env:OTHER_TOKEN'}}}})); p.chmod(0o600); return p
class Response:
 def __init__(self,data): self.data=json.dumps(data).encode()
 def __enter__(self): return self
 def __exit__(self,*x): pass
 def read(self): return self.data

def ns(**kw):
 base=dict(command='jira.issues.get',site='one',sites_file=None,params=None,body=None,dry_run=False,confirm=None,idempotency_key=None,input_path=None,transfer_root=None,max_upload_bytes=1024,timeout_ms=100,retries=0,all_pages=False,max_pages=10,max_items=1000,issueIdOrKey='A-1',commentId=None,projectIdOrKey=None,pageId=None,spaceId=None); base.update(kw); return type('N',(),base)()
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
 monkeypatch.setenv('TEST_TOKEN','one-token'); monkeypatch.setenv('OTHER_TOKEN','two-token'); p=sites(tmp_path); assert a.get_site('one',p)['baseUrl']!=a.get_site('two',p)['baseUrl']
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

def test_contract_inventory():
 assert len(a.CONTRACTS)==26 and all(x.startswith(('auth.','jira.','confluence.')) for x in a.CONTRACTS)
