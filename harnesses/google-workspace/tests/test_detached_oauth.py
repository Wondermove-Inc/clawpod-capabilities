import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from google_workspace_core.catalog import catalog
from google_workspace_core import oauth_jobs

class DetachedOAuth(unittest.TestCase):
 def cli(self,*args,env=None):
  return subprocess.run([sys.executable,str(ROOT/'google_workspace.py'),*args,'--json'],text=True,capture_output=True,env=env,timeout=10)
 def test_contracts_are_short_typed_and_legacy_fails_fast(self):
  commands=catalog()
  for name in ('auth.login.start','auth.login.status','auth.login.finalize','auth.login.cancel','auth.login.recover'):self.assertIn(name,commands)
  manifest=json.loads((ROOT/'harness.json').read_text());self.assertLessEqual(manifest['execution']['timeoutMs'],10000)
  started=time.monotonic();r=self.cli('auth.login','--account','work','--transfer-root','/tmp','--body','{"clientPath":"client.json","profiles":["identity"]}')
  self.assertLess(time.monotonic()-started,2);self.assertEqual(json.loads(r.stdout)['error']['code'],'LOGIN_DETACHED_REQUIRED')
 def test_handle_validation_and_recover_are_sanitized(self):
  with tempfile.TemporaryDirectory() as td:
   old=os.environ.get('GOOGLE_WORKSPACE_BINDING_ROOT');os.environ['GOOGLE_WORKSPACE_BINDING_ROOT']=td
   try:
    with self.assertRaises(Exception):oauth_jobs.status('../bad')
    result=oauth_jobs.recover(max_jobs=3);self.assertEqual(result,{'items':[],'scanned':0,'active':0,'terminal':0})
   finally:
    if old is None:os.environ.pop('GOOGLE_WORKSPACE_BINDING_ROOT',None)
    else:os.environ['GOOGLE_WORKSPACE_BINDING_ROOT']=old
 def test_worker_has_no_gateway_dependency(self):
  text=(ROOT/'google_workspace_core/oauth_jobs.py').read_text().lower()
  for forbidden in ('openclaw','harness.run','gateway websocket','/v1/responses'):self.assertNotIn(forbidden,text)
  self.assertIn('start_new_session=true',text)
 def test_schema_bounds(self):
  c=catalog();start=c['auth.login.start']['inputSchema'];self.assertEqual(start['properties']['timeoutMs']['maximum'],600000)
  self.assertEqual(c['auth.login.status']['inputSchema']['required'],['handle'])
  self.assertEqual(c['auth.login.recover']['inputSchema']['properties']['maxJobs']['maximum'],100)

class FinalizePaths(unittest.TestCase):
 def setUp(self):
  self._old=os.environ.get('GOOGLE_WORKSPACE_BINDING_ROOT')
  self._td=tempfile.TemporaryDirectory();os.environ['GOOGLE_WORKSPACE_BINDING_ROOT']=self._td.name
 def tearDown(self):
  if self._old is None:os.environ.pop('GOOGLE_WORKSPACE_BINDING_ROOT',None)
  else:os.environ['GOOGLE_WORKSPACE_BINDING_ROOT']=self._old
  self._td.cleanup()
 def bundle(self,alias='work'):
  return {'accounts':{alias:{'subject_hash':'sha256:'+'a'*64,'email':'user@example.com','scopes':['https://www.googleapis.com/auth/gmail.readonly']}}}
 def ready_job(self,alias='work',bundle_alias=None):
  import hashlib,secrets
  from google_workspace_core.bindings import binding_root,list_bindings
  jobs=oauth_jobs._jobs();handle=secrets.token_urlsafe(32)
  staged=jobs/'staging'/(handle+'.json');staged.write_text(json.dumps(self.bundle(bundle_alias or alias)))
  _,rev=list_bindings(root=binding_root())
  now=oauth_jobs._now()
  doc={'schemaVersion':1,'handle':handle,'status':'ready_to_finalize','createdAt':now,'updatedAt':now,'expiresAt':now,'deadline':time.time()+600,'account':alias,'revision':2,'bindingRevision':rev,'overwrite':False,'result':{'email':'user@example.com'},'stagedDigest':hashlib.sha256(staged.read_bytes()).hexdigest()}
  oauth_jobs._save(jobs,doc);return jobs,handle,staged
 def test_finalize_moves_staged_credential_into_protected_storage_and_binds(self):
  from google_workspace_core.bindings import binding_root,list_bindings
  jobs,handle,staged=self.ready_job()
  out=oauth_jobs.finalize(handle)
  self.assertEqual(out['status'],'finalized');self.assertTrue(out['bound'])
  self.assertFalse(staged.exists())
  items,_=list_bindings(root=binding_root(),validate_paths=True)
  item=next(x for x in items if x['alias']=='work')
  self.assertTrue(item['healthy'])
  registry=json.loads(next(binding_root().glob('bindings.v1*.json')).read_text()) if list(binding_root().glob('bindings.v1*.json')) else json.loads((binding_root()/'bindings.json').read_text())
  ref=registry['bindings']['work']['credentialRef'];self.assertRegex(ref,r'^credentials/[a-f0-9]{32}\.json$')
  self.assertTrue((binding_root()/ref).exists())
  self.assertTrue(oauth_jobs.finalize(handle)['alreadyFinalized'])
 def test_finalize_register_failure_restores_staged_credential_for_retry(self):
  from google_workspace_core.bindings import BindingError,binding_root
  jobs,handle,staged=self.ready_job(alias='work',bundle_alias='other')
  digest=staged.read_bytes()
  with self.assertRaises(BindingError) as ctx:oauth_jobs.finalize(handle)
  self.assertEqual(ctx.exception.code,'BINDING_IDENTITY_MISMATCH')
  self.assertTrue(staged.exists());self.assertEqual(staged.read_bytes(),digest)
  self.assertEqual(list((binding_root()/'credentials').glob('*.json')),[])
  self.assertEqual(oauth_jobs.status(handle)['status'],'ready_to_finalize')
 def test_worker_preserves_credentials_and_finalizes_when_smoke_tests_fail(self):
  import secrets
  jobs=oauth_jobs._jobs();handle=secrets.token_urlsafe(32)
  now=oauth_jobs._now()
  doc={'schemaVersion':1,'handle':handle,'status':'pending_browser','createdAt':now,'updatedAt':now,'expiresAt':now,'deadline':time.time()+600,'account':'work','revision':1,'bindingRevision':0,'overwrite':False}
  oauth_jobs._save(jobs,doc)
  cfg={'handle':handle,'transferRoot':'/tmp','clientPath':'client.json','profiles':['identity'],'managedBrowserDevtoolsUrl':None,'smokeTests':['gmail'],'timeout':5,'account':'work'}
  oauth_jobs._atomic(jobs/(handle+'.config.json'),cfg)
  bundle=self.bundle()
  def fake_login(**kwargs):
   Path(kwargs['output_root'],kwargs['output_path']).write_text(json.dumps(bundle))
   return {'email':'user@example.com','subject_hash':'sha256:'+'a'*64,'scopes':bundle['accounts']['work']['scopes'],'smokeTests':{'gmail':{'ok':False,'error':'AUTH_REQUIRED'}}}
  real=oauth_jobs.desktop_login;oauth_jobs.desktop_login=fake_login
  try:oauth_jobs.worker(handle)
  finally:oauth_jobs.desktop_login=real
  out=oauth_jobs.status(handle)
  self.assertEqual(out['status'],'ready_to_finalize')
  self.assertFalse(out['result']['smokeTestsPassed']);self.assertEqual(out['result']['failedSmokeTests'],['gmail'])
  self.assertTrue((jobs/'staging'/(handle+'.json')).exists())
  self.assertEqual(oauth_jobs.finalize(handle)['status'],'finalized')

if __name__=='__main__':unittest.main()
