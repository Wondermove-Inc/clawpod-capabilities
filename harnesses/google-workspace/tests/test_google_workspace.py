from __future__ import annotations
import base64,json,os,stat,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; CLI=ROOT/'google_workspace.py'; MAN=json.loads((ROOT/'harness.json').read_text())
import sys
sys.path.insert(0,str(ROOT))
from google_workspace_core.catalog import catalog,operation
from google_workspace_core.mime import compose_message
from google_workspace_core.security import digest,safe_path,atomic_write,redact
from google_workspace_core.transport import ScriptedTransport,retry_request,HTTPError
from google_workspace_core.validation import validate,ValidationError

class Tests(unittest.TestCase):
 def cli(self,*args,env=None,input=None):
  e=os.environ.copy();e.update(env or {});return subprocess.run([sys.executable,str(CLI),*args],input=input,text=True,capture_output=True,env=e)
 def mock(self,response):
  d=tempfile.TemporaryDirectory();p=Path(d.name)/'mock.json';p.write_text(json.dumps(response));self.addCleanup(d.cleanup);return str(p)
 def test_inventory_count(self):self.assertEqual(len(catalog()),151)
 def test_inventory_services(self):self.assertTrue(all(any(k.startswith(x) for x in ('auth.','gmail.','calendar.','drive.')) for k in catalog()))
 def test_closed_schemas(self):self.assertTrue(all(not c['inputSchema']['additionalProperties'] for c in catalog().values()))
 def test_all_have_argmap(self):self.assertTrue(all(c['argMap'] for c in catalog().values()))
 def test_external_safety(self):self.assertIn('externalSideEffect',catalog()['gmail.messages.send']['safetyClasses'])
 def test_destructive_safety(self):self.assertIn('destructive',catalog()['drive.files.delete']['safetyClasses'])
 def test_auth_safety(self):self.assertIn('secretUse',catalog()['auth.accounts.status']['safetyClasses'])
 def test_discovery_subprocess(self):
  r=self.cli('--list-commands');o=json.loads(r.stdout);self.assertEqual(r.returncode,0);self.assertEqual(len(o['data']['commands']),151)
 def test_unknown_one_json(self):
  r=self.cli('nope','--json');self.assertEqual(r.returncode,2);self.assertFalse(json.loads(r.stdout)['ok']);self.assertEqual(len(r.stdout.strip().splitlines()),1)
 def test_scope_list_no_auth(self):
  r=self.cli('auth.scopes.list','--json');self.assertEqual(r.returncode,0);self.assertIn('drive-file',json.loads(r.stdout)['data']['profiles'])
 def test_preview_requires_auth(self):
  r=self.cli('gmail.messages.send','--account','work','--preview','--body','{"compose":{"to":["sink@example.invalid"],"subject":"x","text":"y"}}','--json');o=json.loads(r.stdout);self.assertEqual(r.returncode,3);self.assertEqual(o['error']['code'],'AUTH_REQUIRED')
 def test_external_auth_before_confirm(self):
  r=self.cli('calendar.events.insert','--account','work','--params','{"calendarId":"primary"}','--body','{"summary":"x"}','--json');self.assertEqual(r.returncode,3);self.assertEqual(json.loads(r.stdout)['error']['code'],'AUTH_REQUIRED')
 def test_digest_stable(self):self.assertEqual(digest('x','a',{'body':{'b':1},'preview':True}),digest('x','a',{'body':{'b':1}}))
 def test_digest_account_bound(self):self.assertNotEqual(digest('x','a',{}),digest('x','b',{}))
 def test_gmail_url(self):self.assertEqual(operation('gmail.messages.get',{'messageId':'m'})['url'],'https://gmail.googleapis.com/gmail/v1/users/me/messages/m')
 def test_calendar_url_encoding_contract(self):self.assertIn('calendars/c/events/e',operation('calendar.events.get',{'calendarId':'c','eventId':'e'})['url'])
 def test_drive_permission_url(self):self.assertTrue(operation('drive.permissions.get',{'fileId':'f','permissionId':'p'})['url'].endswith('/files/f/permissions/p'))
 def test_etag_header_and_list_normalization(self):
  p=self.mock([{'body':{'files':[{'id':'f'}],'nextPageToken':'n'}}]);r=self.cli('drive.files.list','--account','work','--if-match','etag','--json',env={'GOOGLE_WORKSPACE_MOCK_HTTP':p});o=json.loads(r.stdout);self.assertEqual(r.returncode,0);self.assertEqual(o['data']['items'][0]['id'],'f');self.assertNotEqual(o['page']['nextPageToken'],'n')
 def test_provider_404(self):
  p=self.mock([{'status':404,'error':'notFound'}]);r=self.cli('drive.files.get','--account','work','--params','{"fileId":"f"}','--json',env={'GOOGLE_WORKSPACE_MOCK_HTTP':p});self.assertEqual(r.returncode,5);self.assertEqual(json.loads(r.stdout)['error']['code'],'NOT_FOUND')
 def test_sync_410(self):
  p=self.mock([{'status':410,'error':'gone'}]);r=self.cli('calendar.events.list','--account','work','--params','{"calendarId":"c"}','--json',env={'GOOGLE_WORKSPACE_MOCK_HTTP':p});self.assertEqual(r.returncode,6);self.assertEqual(json.loads(r.stdout)['error']['code'],'SYNC_TOKEN_EXPIRED')
 def test_unpersisted_confirmation_rejected(self):
  body={'compose':{'to':['sink@example.invalid'],'subject':'s','text':'t'}};effect=digest('gmail.messages.send','work',{'body':body})
  p=self.mock([{'status':503,'error':'backendError'}]);r=self.cli('gmail.messages.send','--account','work','--body',json.dumps(body),'--confirm',effect,'--json',env={'GOOGLE_WORKSPACE_MOCK_HTTP':p});self.assertEqual(r.returncode,4);self.assertEqual(json.loads(r.stdout)['error']['code'],'APPROVAL_REQUIRED')
 def test_mime_crlf_and_unicode(self):
  raw,atts=compose_message({'to':['a@example.invalid'],'subject':'안녕','text':'body'});decoded=base64.urlsafe_b64decode(raw+'='*(-len(raw)%4));self.assertIn(b'\r\n',decoded);self.assertEqual(atts,[])
 def test_header_injection(self):
  with self.assertRaises(ValueError):compose_message({'to':['a@example.invalid\r\nBcc:x'],'subject':'x','text':'y'})
 def test_invalid_timezone(self):
  with self.assertRaises(ValidationError) as c:validate({'body':{'timeZone':'Mars/Olympus'}})
  self.assertEqual(c.exception.code,'INVALID_TIME_ZONE')
 def test_invalid_recurrence(self):
  with self.assertRaises(ValidationError):validate({'body':{'recurrence':['DROP TABLE']}})
 def test_invalid_fields(self):
  with self.assertRaises(ValueError):validate({'fields':['id,$evil']})
 def test_traversal(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):safe_path(d,'../escape')
 def test_symlink(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'real').mkdir();(p/'link').symlink_to(p/'real',target_is_directory=True)
   with self.assertRaises(ValueError):safe_path(d,'link/x')
 def test_atomic_overwrite_refusal(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x';atomic_write(p,b'a')
   with self.assertRaises(FileExistsError):atomic_write(p,b'b')
 def test_transfer_subprocess(self):
  with tempfile.TemporaryDirectory() as d:
   encoded=base64.urlsafe_b64encode(b'hello').rstrip(b'=').decode();m=self.mock([{'body':{'data':encoded,'mimeType':'text/plain'}}]);r=self.cli('gmail.attachments.get','--account','work','--params','{"messageId":"m","attachmentId":"a"}','--transfer-root',d,'--output-path','hello.txt','--json',env={'GOOGLE_WORKSPACE_MOCK_HTTP':m});self.assertEqual(r.returncode,0,r.stdout);self.assertEqual((Path(d)/'hello.txt').read_bytes(),b'hello')
 def test_input_json_stdin(self):
  m=self.mock([{'body':{'id':'f'}}]);r=self.cli('drive.files.get','--input-json','-','--json',input='{"account":"work","params":{"fileId":"f"}}',env={'GOOGLE_WORKSPACE_MOCK_HTTP':m});self.assertEqual(r.returncode,0);self.assertEqual(json.loads(r.stdout)['data']['resource']['id'],'f')
 def test_secret_redaction(self):self.assertEqual(redact({'access_token':'CANARY','nested':{'body':'private'}}),{'access_token':'[REDACTED]','nested':{'body':'[REDACTED]'}})
 def test_login_setup_requirement(self):
  r=self.cli('auth.login','--account','work','--preview','--json');self.assertEqual(r.returncode,11);self.assertIn('PKCE receiver',json.loads(r.stdout)['error']['message'])
 def test_retry_transient(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'m';p.write_text(json.dumps([{'status':503,'error':'x'},{'body':{'ok':1}}]));t=ScriptedTransport(p);status,headers,body,n=retry_request(t,'GET','https://example.invalid',sleep=lambda x:None,jitter=lambda:0);self.assertEqual(n,1)
 def test_no_retry_unsafe(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'m';p.write_text(json.dumps([{'status':503,'error':'x'},{'body':{}}]));t=ScriptedTransport(p)
   with self.assertRaises(HTTPError):retry_request(t,'POST','https://example.invalid',safe=False)
   self.assertEqual(len(t.requests),1)
if __name__=='__main__':unittest.main()
