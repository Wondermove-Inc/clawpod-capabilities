"""Independent regressions for the eight release blockers found by audit v2."""
import json,os,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from google_workspace_core.catalog import catalog,operation
from google_workspace_core.core import run
from google_workspace_core.scopes import required_scopes
from google_workspace_core.state import issue_preview

class ReleaseAuditV3(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);os.environ['GOOGLE_WORKSPACE_STATE_FILE']=str(Path(self.t.name)/'state.json')
 def tearDown(self):
  for k in ('GOOGLE_WORKSPACE_STATE_FILE','GOOGLE_WORKSPACE_MOCK_HTTP','GOOGLE_WORKSPACE_HTTPS_RECEIVER','GOOGLE_WORKSPACE_PUBSUB_TOPIC'):os.environ.pop(k,None)
 def mock(self,responses):
  p=Path(self.t.name)/f'{time.time_ns()}.json';p.write_text(json.dumps(responses));os.environ['GOOGLE_WORKSPACE_MOCK_HTTP']=str(p);return p
 def test_body_schemas_are_typed_by_family(self):
  expected={'gmail.labels.create':('name','string'),'gmail.messages.batchModify':('ids','array'),'calendar.freebusy.query':('items','array'),'calendar.events.insert':('start','object'),'drive.permissions.create':('role','string'),'drive.sharedDrives.create':('name','string')}
  for cmd,(field,typ) in expected.items():
   body=catalog()[cmd]['inputSchema']['properties']['body'];self.assertIn(field,body['properties'],cmd);self.assertEqual(body['properties'][field]['type'],typ,cmd)
  self.assertIn('name',catalog()['gmail.labels.create']['inputSchema']['properties']['body']['required'])
 def test_all_mutations_require_dry_run_confirmation_and_digest_is_canonical(self):
  payload={'account':'a','params':{'fileId':'f'},'body':{'name':'n'}};self.mock([]);out,code=run('drive.files.update',payload);self.assertEqual((code,out['error']['code']),(4,'APPROVAL_REQUIRED'))
  self.mock([{'body':{'id':'f','etag':'e'}}]);out,code=run('drive.files.update',{**payload,'dryRun':True});self.assertEqual(code,0,out);self.assertEqual(out['data']['effectDigest'],out['effects'][0]['effectDigest'])
 def test_idempotency_replay_precedes_confirmation_consumption(self):
  p={'account':'a','params':{'fileId':'f'},'body':{'name':'n'},'idempotencyKey':'k'};target=operation('drive.files.update',p['params'])['url'];token=issue_preview('drive.files.update','a',{**p,'dryRun':True},target,None);self.mock([{'body':{'id':'f'}}]);first,code=run('drive.files.update',{**p,'confirm':token});self.assertEqual(code,0,first)
  self.mock([]);second,code=run('drive.files.update',{**p,'confirm':token});self.assertEqual(code,0,second);self.assertEqual(second,first)
 def test_upload_modes_and_strict_range_resume(self):
  Path(self.t.name,'in').write_bytes(b'abc');p={'account':'a','transferRoot':self.t.name,'inputPath':'in','params':{'uploadType':'simple'},'body':{'name':'x'}};token=issue_preview('drive.files.upload','a',{**p,'dryRun':True},operation('drive.files.upload',p['params'])['url'],None);self.mock([{'body':{'id':'f'}}]);out,code=run('drive.files.upload',{**p,'confirm':token});self.assertEqual(code,0,out)
  Path(self.t.name,'out').write_bytes(b'a');self.mock([{'status':200,'bodyBase64':'YmM='}]);out,code=run('drive.files.download',{'account':'a','transferRoot':self.t.name,'outputPath':'out','overwrite':True,'resume':True,'params':{'fileId':'f'}});self.assertEqual(out['error']['code'],'PRECONDITION_FAILED')
 def test_pagination_does_not_fetch_past_max_items(self):
  self.mock([{'body':{'files':[{'id':'1'}],'nextPageToken':'more'}}]);out,code=run('drive.files.list',{'account':'a','allPages':True,'maxItems':1});self.assertEqual(code,0,out);self.assertEqual(out['page']['pagesFetched'],1)
 def test_batch_halts_after_systemic_auth(self):
  self.mock([{'status':401,'error':'invalidCredentials'}]);out,code=run('drive.files.get',{'account':'a','batch':[{'params':{'fileId':'1'}},{'params':{'fileId':'2'}}]});self.assertEqual(code,9);self.assertEqual(out['data']['haltedOn'],'AUTH_EXPIRED');self.assertFalse(out['data']['items'][1]['launched'])
 def test_watch_requires_exact_configured_receiver(self):
  body={'id':'c','type':'web_hook','address':'https://receiver.invalid/hook'};self.mock([]);out,code=run('calendar.events.watch',{'account':'a','params':{'calendarId':'c'},'body':body,'dryRun':True});self.assertEqual(out['error']['code'],'UNSUPPORTED_BY_CONTRACT')
  os.environ['GOOGLE_WORKSPACE_HTTPS_RECEIVER']='https://other.invalid/hook';self.mock([]);out,code=run('calendar.events.watch',{'account':'a','params':{'calendarId':'c'},'body':body,'dryRun':True});self.assertEqual(out['error']['code'],'INVALID_ARGUMENT')
 def test_least_privilege_scopes(self):
  self.assertEqual(required_scopes('gmail.labels.create'),{'https://www.googleapis.com/auth/gmail.labels'})
  self.assertEqual(required_scopes('gmail.settings.smime.insert'),{'https://www.googleapis.com/auth/gmail.settings.sharing'})
  self.assertEqual(required_scopes('drive.folders.create'),{'https://www.googleapis.com/auth/drive.file'})
 def test_strict_provider_semantics(self):
  bad=[('drive.files.move',{'account':'a','params':{'fileId':'f','addParents':'a,b','removeParents':'c'},'body':{'name':'x'}}),('drive.permissions.create',{'account':'a','params':{'fileId':'f'},'body':{'type':'user','role':'reader','emailAddress':'x@example.test'}}),('calendar.events.insert',{'account':'a','params':{'calendarId':'c'},'body':{'summary':'x'}})]
  for cmd,p in bad:
   self.mock([]);out,code=run(cmd,p);self.assertEqual(code,2,(cmd,out));self.assertEqual(out['error']['code'],'INVALID_ARGUMENT')
if __name__=='__main__':unittest.main()
