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

if __name__=='__main__':unittest.main()
