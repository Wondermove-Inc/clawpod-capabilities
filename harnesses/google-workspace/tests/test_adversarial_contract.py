from __future__ import annotations
import json, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from google_workspace_core.catalog import catalog, operation, OperationError
from google_workspace_core.core import run
from google_workspace_core.security import safe_path
from google_workspace_core.mime import compose_message

class AdversarialContract(unittest.TestCase):
 def test_every_remote_command_has_resolved_https_request(self):
  samples={"userId":"me","messageId":"m/id","threadId":"t/id","attachmentId":"a/id","labelId":"l/id","draftId":"d/id","calendarId":"c/id","eventId":"e/id","ruleId":"r/id","settingId":"s/id","fileId":"f/id","permissionId":"p/id","commentId":"c/id","replyId":"r/id","revisionId":"v/id","driveId":"d/id","sendAsEmail":"alias@example.invalid","smimeInfoId":"cert/id","forwardingEmail":"f@example.invalid","delegateEmail":"d@example.invalid","filterId":"filter/id","kind":"imap","mimeType":"text/plain","requestId":"test-request"}
  for command in catalog():
   if command.startswith("auth."): continue
   with self.subTest(command=command):
    if command in ("drive.files.upload","drive.files.download","drive.files.export"):
     with self.assertRaisesRegex(OperationError,"binary .* transport is not implemented"): operation(command,samples)
     continue
    op=operation(command,samples)
    self.assertIn(op["method"],{"GET","POST","PUT","PATCH","DELETE"})
    self.assertTrue(op["url"].startswith("https://"))
    self.assertNotIn("{",op["url"])
    self.assertNotIn("/id",op["url"],"resource IDs must be URL encoded")
 def test_required_identifiers_fail_before_preview(self):
  for command,params in [("gmail.messages.get",{}),("calendar.events.delete",{"calendarId":"c"}),("drive.permissions.delete",{"fileId":"f"})]:
   out,code=run(command,{"account":"work","params":params,"preview":True})
   self.assertEqual(code,2,command); self.assertEqual(out["error"]["code"],"INVALID_ARGUMENT")
 def test_search_alias_maps_to_files_list(self):
  op=operation("drive.files.search",{})
  self.assertEqual(op["method"],"GET"); self.assertTrue(op["url"].endswith("/files"))
 def test_drive_trash_is_patch_not_nonexistent_rpc(self):
  for command in ("drive.files.trash","drive.files.untrash"):
   op=operation(command,{"fileId":"f"}); self.assertEqual(op["method"],"PATCH"); self.assertTrue(op["url"].endswith("/files/f"))
 def test_unimplemented_binary_transfers_fail_precisely(self):
  for command,params in (("drive.files.upload",{}),("drive.files.download",{"fileId":"f"}),("drive.files.export",{"fileId":"f","mimeType":"text/plain"})):
   with self.assertRaisesRegex(OperationError,"binary .* transport is not implemented"): operation(command,params)
 def test_all_pages_never_silently_fetches_one_page(self):
  out,code=run("drive.files.list",{"account":"work","allPages":True})
  self.assertEqual(code,11); self.assertEqual(out["error"]["code"],"UNSUPPORTED_BY_CONTRACT")
 def test_attachment_paths_are_root_confined(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,"escapes transfer root"):
    compose_message({"to":["a@example.invalid"],"attachments":[{"path":"../secret"}]},d)
 def test_path_rejects_output_parent_symlink(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); outside=root.parent/(root.name+"-outside"); outside.mkdir()
   self.addCleanup(lambda: outside.rmdir())
   (root/"link").symlink_to(outside,target_is_directory=True)
   with self.assertRaises(ValueError): safe_path(d,"link/file",output=True)

if __name__=="__main__": unittest.main()
