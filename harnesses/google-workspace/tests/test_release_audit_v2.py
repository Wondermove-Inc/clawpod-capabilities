"""Independent release-audit regressions, intentionally separate from implementation tests."""
import json, os, sys, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from google_workspace_core.catalog import operation

class ReleaseAuditV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from google_workspace_core.catalog import catalog
        cls.commands=catalog()

    def required(self, command):
        schema=self.commands[command]['inputSchema']
        return set(schema['required']),set(schema['properties']['params'].get('required',[]))

    def test_provider_required_watch_and_stop_bodies(self):
        for name in ('calendar.calendarList.watch','calendar.events.watch','calendar.acl.watch',
                     'calendar.channels.stop','drive.changes.watch','drive.files.watch','drive.channels.stop'):
            self.assertIn('body',self.required(name)[0],name)

    def test_provider_required_query_values(self):
        expected={'calendar.events.quickAdd':'text','calendar.events.move':'destination',
                  'drive.changes.list':'pageToken','drive.changes.watch':'pageToken',
                  'drive.sharedDrives.create':'requestId'}
        for name,key in expected.items():self.assertIn(key,self.required(name)[1],name)

    def test_gmail_label_patch_has_resource_id(self):
        op=operation('gmail.labels.patch',{'labelId':'a/b'})
        self.assertEqual(op['url'],'https://gmail.googleapis.com/gmail/v1/users/me/labels/a%2Fb')

    def test_virtual_drive_mutations_are_patch_not_fake_subresources(self):
        for action in ('trash','untrash'):
            op=operation('drive.files.'+action,{'fileId':'x'})
            self.assertEqual(op['method'],'PATCH')
            self.assertTrue(op['url'].endswith('/files/x'))

    def test_folder_create_uses_files_collection(self):
        op=operation('drive.folders.create',{})
        self.assertEqual(op['method'],'POST')
        self.assertTrue(op['url'].endswith('/files'))

if __name__=='__main__':unittest.main()
