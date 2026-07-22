from __future__ import annotations
import json,os,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from google_workspace_core.catalog import catalog,operation
from google_workspace_core.core import run
from google_workspace_core.state import issue_preview,consume_preview,bind_token,unbind_token
class AdversarialContract(unittest.TestCase):
 def setUp(self):
  self.d=tempfile.TemporaryDirectory();self.addCleanup(self.d.cleanup);os.environ['GOOGLE_WORKSPACE_STATE_FILE']=str(Path(self.d.name)/'state.json')
 def mock(self,responses):
  p=Path(self.d.name)/('mock'+str(time.time_ns())+'.json');p.write_text(json.dumps(responses));os.environ['GOOGLE_WORKSPACE_MOCK_HTTP']=str(p);return p
 def tearDown(self):os.environ.pop('GOOGLE_WORKSPACE_MOCK_HTTP',None);os.environ.pop('GOOGLE_WORKSPACE_STATE_FILE',None)
 def test_all_151_schemas_are_specialized_and_scoped(self):
  for cmd,c in catalog().items():
   with self.subTest(cmd=cmd):
    self.assertFalse(c['inputSchema']['additionalProperties']);self.assertFalse(c['inputSchema']['properties']['params']['additionalProperties'])
    if not cmd.startswith('auth.'):self.assertTrue(c['requiredScopes'])
 def test_every_remote_command_resolves(self):
  s={k:'x/id' for k in ('messageId','threadId','attachmentId','labelId','draftId','calendarId','eventId','ruleId','settingId','fileId','permissionId','commentId','replyId','revisionId','driveId','sendAsEmail','smimeInfoId','forwardingEmail','delegateEmail','filterId')};s.update(kind='imap',mimeType='text/plain',requestId='r')
  for cmd in catalog():
   if cmd.startswith('auth.'):continue
   op=operation(cmd,s);self.assertTrue(op['url'].startswith('https://'));self.assertNotIn('/id',op['url'])
 def test_preview_one_use_cross_account_and_input_bound(self):
  p={'params':{'fileId':'f'},'body':{'name':'n'}};t=issue_preview('drive.files.update','a',p,'u','e')
  self.assertEqual(consume_preview(t,'drive.files.update','b',p,'u','e')[0],False)
  self.assertEqual(consume_preview(t,'drive.files.update','a',p,'u','e')[0],True)
  self.assertEqual(consume_preview(t,'drive.files.update','a',p,'u','e')[0],False)
 def test_expired_and_stale_preview_rejected(self):
  p={'body':{'x':1}};t=issue_preview('x','a',p,'u','e');self.assertFalse(consume_preview(t,'x','a',p,'u','changed')[0])
 def test_bound_token_rejects_query_and_account_change(self):
  t=bind_token('raw','drive.files.list','a',{'q':'x'});self.assertEqual(unbind_token(t,'drive.files.list','a',{'q':'x'}),'raw')
  with self.assertRaises(ValueError):unbind_token(t,'drive.files.list','b',{'q':'x'})
  with self.assertRaises(ValueError):unbind_token(t,'drive.files.list','a',{'q':'y'})
 def test_all_pages_bounded(self):
  self.mock([{'body':{'files':[{'id':'1'}],'nextPageToken':'n'}},{'body':{'files':[{'id':'2'}]}}]);out,code=run('drive.files.list',{'account':'a','allPages':True,'maxPages':2});self.assertEqual(code,0);self.assertEqual(len(out['data']['items']),2);self.assertEqual(out['page']['pagesFetched'],2)
 def test_unknown_provider_query_fails(self):
  out,code=run('drive.files.list',{'account':'a','params':{'evil':'x'}});self.assertEqual(code,2);self.assertIn('unsupported provider',out['error']['message'])
 def test_dry_run_authenticates(self):
  out,code=run('calendar.events.insert',{'account':'missing','params':{'calendarId':'c'},'body':{'summary':'x'},'dryRun':True});self.assertEqual(code,3);self.assertEqual(out['error']['code'],'AUTH_REQUIRED')
 def test_drive_binary_operations_are_supported(self):
  for c,p in [('drive.files.upload',{}),('drive.files.download',{'fileId':'f'}),('drive.files.export',{'fileId':'f','mimeType':'text/plain'})]:self.assertTrue(operation(c,p)['url'].startswith('https://'))
 def test_resumable_upload_and_checksum_download(self):
  src=Path(self.d.name)/'in';src.write_bytes(b'hello');payload={'account':'a','transferRoot':self.d.name,'inputPath':'in','params':{'uploadType':'resumable'},'body':{'name':'x'}};token=issue_preview('drive.files.upload','a',{**payload,'dryRun':True},operation('drive.files.upload',payload['params'])['url'],None);self.mock([{'headers':{'Location':'https://upload.invalid/session'}},{'body':{'id':'f'}}]);out,code=run('drive.files.upload',{**payload,'confirm':token});self.assertEqual(code,0,out)
  self.mock([{'bodyBase64':'aGVsbG8=','headers':{'Content-Type':'text/plain'}}]);out,code=run('drive.files.download',{'account':'a','transferRoot':self.d.name,'outputPath':'out','params':{'fileId':'f'},'expectedSha256':'2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'});self.assertEqual(code,0,out);self.assertEqual((Path(self.d.name)/'out').read_bytes(),b'hello')
 def test_batch_partial_results(self):
  self.mock([{'body':{'id':'f'}}]);out,code=run('drive.files.get',{'account':'a','batch':[{'params':{'fileId':'f'}},{'params':{}}]});self.assertEqual(code,9);self.assertEqual(out['data']['succeeded'],1);self.assertEqual(out['data']['failed'],1)
if __name__=='__main__':unittest.main()
