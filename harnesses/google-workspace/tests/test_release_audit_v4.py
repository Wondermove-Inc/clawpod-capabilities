"""Independent v4 release gate, written without trusting prior audit tests."""
import json,os,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from google_workspace_core.catalog import catalog,operation,preflight
from google_workspace_core.core import run

SAMPLES={k:k for k in ('messageId','threadId','attachmentId','labelId','draftId','calendarId','eventId','ruleId','settingId','fileId','permissionId','commentId','replyId','revisionId','driveId','sendAsEmail','smimeInfoId','forwardingEmail','delegateEmail','filterId')};SAMPLES.update(userId='me',kind='imap',mimeType='text/plain',requestId='request',pageToken='page')

class ReleaseAuditV4(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  os.environ['GOOGLE_WORKSPACE_STATE_FILE']=str(Path(self.tmp.name)/'state.json')
 def tearDown(self):
  for key in ('GOOGLE_WORKSPACE_STATE_FILE','GOOGLE_WORKSPACE_MOCK_HTTP'):os.environ.pop(key,None)
 def mock(self,responses):
  path=Path(self.tmp.name)/f'{time.time_ns()}.json';path.write_text(json.dumps(responses));os.environ['GOOGLE_WORKSPACE_MOCK_HTTP']=str(path)
 def test_inventory_schemas_scopes_and_recursive_closure(self):
  commands=catalog();self.assertEqual(len(commands),151);self.assertEqual(sum(not k.startswith('auth.') for k in commands),144)
  open_nodes=[]
  def scan(node,path):
   if isinstance(node,dict):
    if node.get('type')=='object' and node.get('additionalProperties') is True:open_nodes.append(path)
    for key,value in node.items():scan(value,path+'/'+key)
   elif isinstance(node,list):
    for i,value in enumerate(node):scan(value,path+f'/{i}')
  for name,meta in commands.items():
   scan(meta['inputSchema'],name+'/input');scan(meta['outputSchema'],name+'/output')
   if not name.startswith('auth.'):self.assertTrue(meta.get('requiredScopes'),name)
  self.assertEqual(open_nodes,[])
 def test_every_mutation_preflight_is_nonmutating_and_never_uses_fake_etag_field(self):
  for name,meta in catalog().items():
   if not any(x in meta['safetyClasses'] for x in ('writeSafe','externalSideEffect','destructive')) or name.startswith('auth.'):continue
   op=operation(name,SAMPLES);check=preflight(name,SAMPLES)
   self.assertIn(check['method'],(None,'GET'),name)
   action_suffixes=('/modify','/trash','/untrash','/send','/verify','/setDefault','/clear','/transferOwnership','/move','/copy','/watch','/hide','/unhide','/stop')
   if op['url'].endswith(action_suffixes):self.assertNotEqual(check['url'],op['url'],name)
   fields=check['query'].get('fields','');self.assertNotIn('etag',fields.split(','),name)
 def test_etag_bound_preview_executes_and_stale_target_is_rejected(self):
  base={'account':'a','params':{'fileId':'f'},'body':{'name':'n'}}
  self.mock([{'headers':{'ETag':'E1'},'body':{'id':'f'}}]);preview,code=run('drive.files.update',{**base,'dryRun':True});self.assertEqual(code,0,preview);self.assertEqual(preview['data']['etag'],'E1')
  self.mock([{'headers':{'ETag':'E1'},'body':{'id':'f'}},{'body':{'id':'f'}}]);done,code=run('drive.files.update',{**base,'confirm':preview['data']['effectDigest']});self.assertEqual(code,0,done)
  self.mock([{'headers':{'ETag':'E2'},'body':{'id':'f'}}]);rejected,code=run('drive.files.update',{**base,'confirm':preview['data']['effectDigest']});self.assertEqual((code,rejected['error']['code']),(4,'APPROVAL_REQUIRED'))
 def test_initial_page_request_obeys_max_items(self):
  import google_workspace_core.core as core
  seen=[];old=core.ScriptedTransport
  class Capture(old):
   def request(self,*args,**kwargs):seen.append(dict(kwargs.get('query') or {}));return super().request(*args,**kwargs)
  core.ScriptedTransport=Capture;self.addCleanup(setattr,core,'ScriptedTransport',old)
  self.mock([{'body':{'files':[{'id':'1'}],'nextPageToken':'unused'}}]);out,code=run('drive.files.list',{'account':'a','allPages':True,'pageSize':100,'maxItems':1});self.assertEqual(code,0,out);self.assertEqual(seen,[{'pageSize':1}])

if __name__=='__main__':unittest.main()
