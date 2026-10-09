"""Gmail usage paths an agent hits first: gmail.read headers, provider-native params, self-correcting errors."""
from __future__ import annotations
import base64,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from google_workspace_core import core
from google_workspace_core.transport import ScriptedTransport

def b64(text):return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")

class Recording(ScriptedTransport):
 last=None
 def __init__(self,path):super().__init__(path);Recording.last=self

class GmailUsage(unittest.TestCase):
 def call(self,command,payload,responses):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"mock.json";path.write_text(json.dumps(responses))
   with patch.dict(os.environ,{"GOOGLE_WORKSPACE_MOCK_HTTP":str(path)}),patch.object(core,"ScriptedTransport",Recording):
    out,code=core.run(command,{"account":"work",**payload})
  return out,code,(Recording.last.requests if Recording.last else [])

 def meta(self,mid,subject,sender="Alice <alice@example.com>"):
  return {"body":{"id":mid,"threadId":"t-"+mid,"labelIds":["INBOX","UNREAD"],"snippet":"preview "+mid,"internalDate":"1791513286000","payload":{"headers":[{"name":"From","value":sender},{"name":"To","value":"captain@example.com"},{"name":"Subject","value":subject},{"name":"Date","value":"Thu, 8 Oct 2026 19:34:46 -0700"}]}}}

 def test_gmail_read_fetches_headers_for_each_listed_message(self):
  responses=[{"body":{"messages":[{"id":"m1","threadId":"t-m1"},{"id":"m2","threadId":"t-m2"}]}},self.meta("m1","주간 보고"),self.meta("m2","Invoice")]
  out,code,reqs=self.call("gmail.read",{"params":{"q":"in:inbox newer_than:1d","maxResults":10}},responses)
  self.assertEqual(code,0,out)
  items=out["data"]["items"]
  self.assertEqual([x["subject"] for x in items],["주간 보고","Invoice"])
  self.assertEqual(items[0]["sender"],"Alice <alice@example.com>");self.assertEqual(items[0]["snippet"],"preview m1")
  self.assertTrue(reqs[0]["url"].endswith("/users/me/messages"))
  self.assertEqual(reqs[0]["query"]["fields"],"nextPageToken,messages(id,threadId)")
  self.assertTrue(reqs[1]["url"].endswith("/users/me/messages/m1"))
  self.assertEqual(reqs[1]["query"],{"format":"metadata","metadataHeaders":["From","To","Cc","Subject","Date"]})
  self.assertEqual(len(reqs),3)

 def test_gmail_read_include_body_decodes_text_and_skips_attachments(self):
  full={"body":{"id":"m1","threadId":"t1","snippet":"s","payload":{"mimeType":"multipart/mixed","headers":[{"name":"Subject","value":"본문"}],"parts":[
   {"mimeType":"multipart/alternative","parts":[{"mimeType":"text/plain","body":{"data":b64("안녕하세요\n본문입니다")}},{"mimeType":"text/html","body":{"data":b64("<p>안녕하세요</p>")}}]},
   {"mimeType":"text/plain","filename":"notes.txt","body":{"attachmentId":"a1","size":10}}]}}}
  out,code,reqs=self.call("gmail.read",{"params":{"includeBody":True}},[{"body":{"messages":[{"id":"m1"}]}},full])
  self.assertEqual(code,0,out)
  body=out["data"]["items"][0]["body"]
  self.assertEqual(body["text"],"안녕하세요\n본문입니다");self.assertEqual(body["html"],"<p>안녕하세요</p>")
  self.assertEqual(reqs[1]["query"],{"format":"full"})

 def test_gmail_read_threads_use_newest_message_and_skip_deleted(self):
  thread={"body":{"id":"t1","messages":[self.meta("old","첫 메일")["body"],self.meta("new","Re: 첫 메일")["body"]]}}
  responses=[{"body":{"threads":[{"id":"t1","snippet":"x"},{"id":"gone","snippet":"y"}]}},thread,{"status":404,"error":"notFound"}]
  out,code,reqs=self.call("gmail.read",{"params":{"mode":"threads"}},responses)
  self.assertEqual(code,0,out)
  self.assertEqual(out["data"]["items"][0]["subject"],"Re: 첫 메일")
  self.assertEqual(out["data"]["items"][1]["id"],"gone")
  self.assertTrue(reqs[1]["url"].endswith("/users/me/threads/t1"))

 def test_gmail_read_auth_failure_on_detail_fetch_is_reported(self):
  out,code,_=self.call("gmail.read",{},[{"body":{"messages":[{"id":"m1"}]}},{"status":401,"error":"authError"}])
  self.assertNotEqual(code,0);self.assertEqual(out["error"]["code"],"AUTH_EXPIRED")

 def test_provider_native_user_id_format_and_metadata_headers_are_accepted(self):
  out,code,reqs=self.call("gmail.messages.get",{"params":{"userId":"me","messageId":"m1","format":"metadata","metadataHeaders":["From","Subject"]}},[self.meta("m1","x")])
  self.assertEqual(code,0,out)
  self.assertTrue(reqs[0]["url"].endswith("/users/me/messages/m1"))
  self.assertEqual(reqs[0]["query"],{"format":"metadata","metadataHeaders":["From","Subject"]})
  out,code,reqs=self.call("gmail.messages.list",{"params":{"userId":"me","q":"in:inbox","maxResults":5}},[{"body":{"messages":[]}}])
  self.assertEqual(code,0,out);self.assertNotIn("userId",reqs[0]["query"])

 def test_provider_native_id_maps_to_the_single_required_identifier(self):
  out,code,reqs=self.call("gmail.messages.get",{"params":{"id":"m1"}},[self.meta("m1","x")])
  self.assertEqual(code,0,out);self.assertTrue(reqs[0]["url"].endswith("/messages/m1"))
  out,code,reqs=self.call("drive.files.get",{"params":{"id":"f1"}},[{"body":{"id":"f1","name":"a.pdf"}}])
  self.assertEqual(code,0,out);self.assertTrue(reqs[0]["url"].endswith("/files/f1"))

 def test_id_is_not_guessed_when_ambiguous_or_already_named(self):
  out,code,_=self.call("gmail.attachments.get",{"params":{"id":"x","messageId":"m1"}},[])
  self.assertEqual(code,2);self.assertIn("missing required field(s): attachmentId",out["error"]["message"])
  out,code,_=self.call("gmail.messages.get",{"params":{"id":"x","messageId":"m1"}},[])
  self.assertEqual(code,2);self.assertIn("unsupported provider query/identifier(s): id",out["error"]["message"])

 def test_gmail_trash_needs_no_body_and_sends_none(self):
  preview,code,_=self.call("gmail.messages.trash",{"params":{"messageId":"m1"},"dryRun":True},[{"body":{"id":"m1","labelIds":["INBOX"]}}])
  self.assertEqual(code,0,preview)
  out,code,reqs=self.call("gmail.messages.trash",{"params":{"messageId":"m1"},"confirm":preview["data"]["effectDigest"]},[{"body":{"id":"m1","labelIds":["INBOX"]}},{"body":{"id":"m1","labelIds":["TRASH"]}}])
  self.assertEqual(code,0,out)
  trash=[r for r in reqs if r["url"].endswith("/messages/m1/trash")]
  self.assertEqual(len(trash),1);self.assertEqual(trash[0]["method"],"POST");self.assertIsNone(trash[0]["body"])

 def test_rejections_list_the_accepted_fields(self):
  out,code,_=self.call("gmail.messages.list",{"params":{"pageLimit":3}},[])
  self.assertEqual(code,2)
  self.assertIn("accepted: includeSpamTrash, labelIds, maxResults",out["error"]["message"])
  out,code,_=self.call("gmail.messages.get",{"params":{}},[])
  self.assertEqual(code,2)
  self.assertIn("missing required field(s): messageId; accepted: format, messageId, metadataHeaders, userId",out["error"]["message"])

 def test_editor_requests_and_numeric_cells_reach_the_provider(self):
  out,code,reqs=self.call("docs.documents.batchUpdate",{"params":{"documentId":"d"},"body":{"requests":[{"insertText":{"location":{"index":1},"text":"요약\n"}}]},"dryRun":True},[{"body":{"documentId":"d"}}])
  self.assertEqual(code,0,out)
  out,code,_=self.call("sheets.values.update",{"params":{"spreadsheetId":"s","range":"A1:B2","valueInputOption":"USER_ENTERED"},"body":{"values":[["이름","점수"],["가",95.5]]},"dryRun":True},[{"body":{"spreadsheetId":"s"}}])
  self.assertEqual(code,0,out)
  out,code,_=self.call("docs.documents.batchUpdate",{"params":{"documentId":"d"},"body":{"requests":[{"insertText":{},"deleteContentRange":{}}]},"dryRun":True},[])
  self.assertEqual(code,2)

 def test_skill_examples_use_cli_harness_inputs(self):
  skill=(ROOT.parents[1]/"skills"/"google-workspace"/"SKILL.md").read_text()
  self.assertIn("cli_harness",skill);self.assertIn("harness.run.prepare",skill);self.assertIn("approvalIntentHash",skill)
  self.assertNotIn("google-workspace gmail.",skill)

 def test_harness_only_keys_never_reach_provider_query(self):
  _,code,reqs=self.call("gmail.read",{"params":{"mode":"threads","includeBody":True,"userId":"me","q":"x"}},[{"body":{"threads":[]}}])
  self.assertEqual(code,0);self.assertFalse({"mode","includeBody","userId"}&set(reqs[0]["query"]));self.assertEqual(reqs[0]["query"]["q"],"x")
  _,code,reqs=self.call("drive.read",{"params":{"mode":"search","q":"name contains 'a'"}},[{"body":{"files":[]}}])
  self.assertEqual(code,0);self.assertNotIn("mode",reqs[0]["query"])
  _,code,reqs=self.call("drive.read",{"params":{"mode":"get","fileId":"f1"}},[{"body":{"id":"f1"}}])
  self.assertEqual(code,0);self.assertFalse({"mode","fileId","pageSize"}&set(reqs[0]["query"]));self.assertTrue(reqs[0]["url"].endswith("/files/f1"))
  _,code,reqs=self.call("calendar.read",{"params":{"calendarId":"team@example.com"}},[{"body":{"items":[]}}])
  self.assertEqual(code,0);self.assertNotIn("calendarId",reqs[0]["query"]);self.assertIn("/calendars/team%40example.com/events",reqs[0]["url"])

 def test_id_is_never_aliased_on_create_style_commands(self):
  out,code,_=self.call("calendar.events.insert",{"params":{"id":"evt1","sendUpdates":"none"},"body":{"summary":"x","start":{"date":"2026-10-13"},"end":{"date":"2026-10-14"}},"dryRun":True},[])
  self.assertEqual(code,2);self.assertIn("calendarId",out["error"]["message"])
  out,code,_=self.call("drive.sharedDrives.create",{"params":{"id":"x"},"body":{"name":"n"},"dryRun":True},[])
  self.assertEqual(code,2)

 def test_gmail_trash_tolerates_legacy_trashed_body_but_sends_none(self):
  preview,code,_=self.call("gmail.messages.trash",{"params":{"messageId":"m1"},"body":{"trashed":True},"dryRun":True},[{"body":{"id":"m1"}}])
  self.assertEqual(code,0,preview)
  out,code,reqs=self.call("gmail.messages.trash",{"params":{"messageId":"m1"},"body":{"trashed":True},"confirm":preview["data"]["effectDigest"]},[{"body":{"id":"m1"}},{"body":{"id":"m1"}}])
  self.assertEqual(code,0,out);self.assertIsNone([r for r in reqs if r["url"].endswith("/trash")][0]["body"])

 def test_gmail_lists_do_not_advertise_unsupported_query_or_order(self):
  out,code,_=self.call("gmail.messages.list",{"params":{"orderBy":"date"}},[])
  self.assertEqual(code,2);msg=out["error"]["message"];accepted=msg.split("accepted: ",1)[1]
  self.assertNotIn("orderBy",accepted);self.assertNotIn("query",accepted.replace("q,","").split(", "))

 def test_gmail_read_returns_cc_and_decodes_declared_charset(self):
  euc=base64.urlsafe_b64encode("안녕하세요".encode("cp949")).decode().rstrip("=")
  full={"body":{"id":"m1","payload":{"mimeType":"text/plain","headers":[{"name":"Cc","value":"lee@example.com"},{"name":"Content-Type","value":"text/plain; charset=\"ks_c_5601-1987\""}],"body":{"data":euc}}}}
  out,code,_=self.call("gmail.read",{"params":{"includeBody":True}},[{"body":{"messages":[{"id":"m1"}]}},full])
  self.assertEqual(code,0,out);item=out["data"]["items"][0]
  self.assertEqual(item["cc"],"lee@example.com");self.assertEqual(item["body"]["text"],"안녕하세요")

 def test_page_token_is_bound_to_the_calendar_it_came_from(self):
  first,code,_=self.call("calendar.read",{"params":{"calendarId":"a@x.com"}},[{"body":{"items":[],"nextPageToken":"PT"}}])
  self.assertEqual(code,0,first);token=first["page"]["nextPageToken"];self.assertTrue(token)
  same,code,reqs=self.call("calendar.read",{"params":{"calendarId":"a@x.com"},"pageToken":token},[{"body":{"items":[]}}])
  self.assertEqual(code,0,same);self.assertEqual(reqs[0]["query"]["pageToken"],"PT")
  other,code,_=self.call("calendar.read",{"params":{"calendarId":"b@x.com"},"pageToken":token},[{"body":{"items":[]}}])
  self.assertEqual(code,2,other)

 def test_skill_examples_use_manifest_command_keys(self):
  import re
  keys=set(json.loads((ROOT/"harness.json").read_text())["commands"])
  for doc in ("SKILL.md","references/operations.md"):
   text=(ROOT.parents[1]/"skills"/"google-workspace"/doc).read_text()
   lines=[l for b in re.findall(r"```text\n(.*?)```",text,re.S) for l in b.splitlines() if re.match(r"^[a-z][\w.\-]+  \{",l)]
   self.assertTrue(lines,doc)
   for line in lines:self.assertIn(line.split("  ",1)[0],keys,line)

 def test_skill_teaches_gmail_calendar_drive_entry_points(self):
  skill=(ROOT.parents[1]/"skills"/"google-workspace"/"SKILL.md").read_text()
  for needle in ("gmail.read","calendar.read","drive.read","gmail.messages.get","messageId","calendar.events.insert","sendUpdates","drive.permissions.create","drive.files.export"):
   self.assertIn(needle,skill)

if __name__=="__main__":unittest.main()
