from __future__ import annotations
import json, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from google_workspace_core.catalog import catalog, operation, OperationError
from google_workspace_core.core import run
from google_workspace_core.security import safe_path

class AdversarialContract(unittest.TestCase):
 def test_every_remote_command_has_resolved_https_request(self):
  samples={"userId":"me","messageId":"m/id","threadId":"t/id","attachmentId":"a/id","labelId":"l/id","draftId":"d/id","calendarId":"c/id","eventId":"e/id","ruleId":"r/id","settingId":"s/id","fileId":"f/id","permissionId":"p/id","commentId":"c/id","replyId":"r/id","revisionId":"v/id","driveId":"d/id","sendAsEmail":"alias@example.invalid","smimeInfoId":"cert/id","forwardingEmail":"f@example.invalid","delegateEmail":"d@example.invalid"}
  for command in catalog():
   if command.startswith("auth."): continue
   with self.subTest(command=command):
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
 def test_transfer_operations_use_media_endpoints(self):
  self.assertEqual(operation("drive.files.download",{"fileId":"f"})["query"],{"alt":"media"})
  self.assertEqual(operation("drive.files.export",{"fileId":"f","mimeType":"text/plain"})["url"].split("/")[-1],"export")
 def test_path_rejects_output_parent_symlink(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); outside=root.parent/(root.name+"-outside"); outside.mkdir()
   self.addCleanup(lambda: outside.rmdir())
   (root/"link").symlink_to(outside,target_is_directory=True)
   with self.assertRaises(ValueError): safe_path(d,"link/file",output=True)

if __name__=="__main__": unittest.main()
