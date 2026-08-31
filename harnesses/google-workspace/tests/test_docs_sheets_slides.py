"""Docs, Sheets, and Slides surface tests (0.4.0): URL mapping, scopes, bodies, gating, and mock E2E."""
from __future__ import annotations
import json,os,subprocess,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; CLI=ROOT/'google_workspace.py'
sys.path.insert(0,str(ROOT))
from google_workspace_core.catalog import catalog,operation,preflight
from google_workspace_core.contracts import body_schema
from google_workspace_core.scopes import required_scopes,enforce
from google_workspace_core.core import SCOPES

URLS={
 'docs.documents.get':('GET','https://docs.googleapis.com/v1/documents/documentId'),
 'docs.documents.create':('POST','https://docs.googleapis.com/v1/documents'),
 'docs.documents.batchUpdate':('POST','https://docs.googleapis.com/v1/documents/documentId:batchUpdate'),
 'sheets.spreadsheets.get':('GET','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId'),
 'sheets.spreadsheets.getByDataFilter':('POST','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId:getByDataFilter'),
 'sheets.spreadsheets.create':('POST','https://sheets.googleapis.com/v4/spreadsheets'),
 'sheets.spreadsheets.batchUpdate':('POST','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId:batchUpdate'),
 'sheets.values.get':('GET','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId/values/A1%3AB2'),
 'sheets.values.update':('PUT','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId/values/A1%3AB2'),
 'sheets.values.append':('POST','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId/values/A1%3AB2:append'),
 'sheets.values.clear':('POST','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId/values/A1%3AB2:clear'),
 'sheets.values.batchGet':('GET','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId/values:batchGet'),
 'sheets.values.batchUpdate':('POST','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId/values:batchUpdate'),
 'sheets.values.batchClear':('POST','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId/values:batchClear'),
 'sheets.values.batchGetByDataFilter':('POST','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId/values:batchGetByDataFilter'),
 'sheets.values.batchClearByDataFilter':('POST','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId/values:batchClearByDataFilter'),
 'sheets.sheets.copyTo':('POST','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId/sheets/sheetId:copyTo'),
 'sheets.developerMetadata.get':('GET','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId/developerMetadata/metadataId'),
 'sheets.developerMetadata.search':('POST','https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId/developerMetadata:search'),
 'slides.presentations.get':('GET','https://slides.googleapis.com/v1/presentations/presentationId'),
 'slides.presentations.create':('POST','https://slides.googleapis.com/v1/presentations'),
 'slides.presentations.batchUpdate':('POST','https://slides.googleapis.com/v1/presentations/presentationId:batchUpdate'),
 'slides.pages.get':('GET','https://slides.googleapis.com/v1/presentations/presentationId/pages/pageObjectId'),
 'slides.pages.getThumbnail':('GET','https://slides.googleapis.com/v1/presentations/presentationId/pages/pageObjectId/thumbnail'),
}
IDS={'documentId':'documentId','spreadsheetId':'spreadsheetId','presentationId':'presentationId','pageObjectId':'pageObjectId','sheetId':'sheetId','metadataId':'metadataId','range':'A1:B2'}

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  isolated={'GOOGLE_WORKSPACE_BINDING_ROOT':str(Path(self.tmp.name)/'bindings'),'GOOGLE_WORKSPACE_STATE_FILE':str(Path(self.tmp.name)/'state.json')}
  self.env_patch=patch.dict(os.environ,isolated);self.env_patch.start();self.addCleanup(self.env_patch.stop)
 def cli(self,*args,env=None):
  e=os.environ.copy();e.update(env or {});return subprocess.run([sys.executable,str(CLI),*args],text=True,capture_output=True,env=e)
 def mock(self,response):
  p=Path(self.tmp.name)/'mock.json';p.write_text(json.dumps(response));return str(p)

 def test_every_editor_command_is_in_the_catalog_with_scopes(self):
  entries=catalog()
  for name in list(URLS)+['docs.read','sheets.read','slides.read']:
   self.assertIn(name,entries,name)
   self.assertTrue(required_scopes(name),name)
 def test_url_and_method_mapping_is_exact(self):
  for name,(method,url) in URLS.items():
   op=operation(name,IDS)
   self.assertEqual((op['method'],op['url']),(method,url),name)
 def test_missing_identifiers_fail_closed(self):
  for name in ('docs.documents.batchUpdate','sheets.values.update','slides.pages.get','sheets.sheets.copyTo','sheets.developerMetadata.get'):
   with self.assertRaises(Exception):operation(name,{})
 def test_read_write_scope_split(self):
  self.assertEqual(required_scopes('docs.documents.get'),{'https://www.googleapis.com/auth/documents.readonly'})
  self.assertEqual(required_scopes('docs.documents.batchUpdate'),{'https://www.googleapis.com/auth/documents'})
  self.assertEqual(required_scopes('sheets.values.batchGet'),{'https://www.googleapis.com/auth/spreadsheets.readonly'})
  self.assertEqual(required_scopes('sheets.values.batchGetByDataFilter'),{'https://www.googleapis.com/auth/spreadsheets'})
  self.assertEqual(required_scopes('sheets.developerMetadata.get'),{'https://www.googleapis.com/auth/spreadsheets'})
  self.assertEqual(required_scopes('sheets.values.clear'),{'https://www.googleapis.com/auth/spreadsheets'})
  self.assertEqual(required_scopes('slides.pages.getThumbnail'),{'https://www.googleapis.com/auth/presentations.readonly'})
  self.assertEqual(required_scopes('slides.presentations.batchUpdate'),{'https://www.googleapis.com/auth/presentations'})
 def test_full_scope_satisfies_readonly_and_readonly_never_writes(self):
  enforce('sheets.values.get',['https://www.googleapis.com/auth/spreadsheets'])
  with self.assertRaises(PermissionError):enforce('sheets.values.update',['https://www.googleapis.com/auth/spreadsheets.readonly'])
 def test_drive_scopes_satisfy_editor_apis_like_google_does(self):
  # Google accepts drive / drive.file on the editor APIs; the local gate must not be stricter.
  enforce('docs.documents.batchUpdate',['https://www.googleapis.com/auth/drive'])
  enforce('sheets.values.update',['https://www.googleapis.com/auth/drive.file'])
  enforce('slides.read',['https://www.googleapis.com/auth/drive.readonly'])
  with self.assertRaises(PermissionError):enforce('sheets.values.update',['https://www.googleapis.com/auth/drive.readonly'])
  with self.assertRaises(PermissionError):enforce('docs.documents.batchUpdate',['https://www.googleapis.com/auth/drive.metadata.readonly'])
 def test_profiles_cover_all_six_scopes(self):
  for profile,scope in (('docs-read','documents.readonly'),('docs-edit','documents'),('sheets-read','spreadsheets.readonly'),('sheets-edit','spreadsheets'),('slides-read','presentations.readonly'),('slides-edit','presentations')):
   self.assertEqual(SCOPES[profile],['https://www.googleapis.com/auth/'+scope])
  for scope in ('documents','spreadsheets','presentations'):
   self.assertIn('https://www.googleapis.com/auth/'+scope,SCOPES['workspace-max'])
 def test_batch_update_bodies_require_requests(self):
  for name in ('docs.documents.batchUpdate','sheets.spreadsheets.batchUpdate','slides.presentations.batchUpdate'):
   self.assertIn('requests',body_schema(name,'POST')['required'])
  self.assertNotIn('targetRevisionId',body_schema('slides.presentations.batchUpdate','POST')['properties']['writeControl']['properties'])
  self.assertEqual(body_schema('sheets.values.update','PUT')['required'],['values'])
  self.assertEqual(body_schema('sheets.values.batchUpdate','POST')['required'],['valueInputOption','data'])
 def test_safety_classes_gate_mutations(self):
  entries=catalog()
  for name in ('docs.documents.get','sheets.values.get','slides.read','sheets.developerMetadata.search','sheets.spreadsheets.getByDataFilter'):
   self.assertIn('readOnly',entries[name]['safetyClasses'],name)
  for name in ('docs.documents.batchUpdate','sheets.values.update','slides.presentations.create','sheets.sheets.copyTo'):
   self.assertIn('writeSafe',entries[name]['safetyClasses'],name)
  for name in ('sheets.values.clear','sheets.values.batchClear','sheets.values.batchClearByDataFilter'):
   self.assertIn('destructive',entries[name]['safetyClasses'],name)
 def test_preflight_reads_are_valid_and_cheap(self):
  self.assertEqual(preflight('sheets.values.update',IDS)['url'],'https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId/values/A1%3AB2')
  self.assertEqual(preflight('docs.documents.batchUpdate',IDS)['url'],'https://docs.googleapis.com/v1/documents/documentId')
  self.assertEqual(preflight('sheets.values.batchUpdate',IDS),{'method':'GET','url':'https://sheets.googleapis.com/v4/spreadsheets/spreadsheetId','query':{'fields':'spreadsheetId'},'etag':False,'strategy':'parent'})
  self.assertIsNone(preflight('slides.presentations.create',{})['method'])

 def test_sheets_read_e2e_normalizes_values(self):
  p=self.mock([{'body':{'range':'Sheet1!A1:B2','majorDimension':'ROWS','values':[['a','b'],['c','d']]}}])
  r=self.cli('sheets.read','--account','work','--params',json.dumps({'spreadsheetId':'s','range':'Sheet1!A1:B2'}),'--json',env={'GOOGLE_WORKSPACE_MOCK_HTTP':p})
  self.assertEqual(r.returncode,0,r.stdout+r.stderr);o=json.loads(r.stdout)
  self.assertEqual(o['data']['items'][0]['rowCount'],2);self.assertEqual(o['data']['items'][0]['values'][1],['c','d'])
  self.assertEqual(o['provenance']['api'],'sheets')
 def test_docs_read_e2e_extracts_text(self):
  doc={'documentId':'d','title':'제안서','revisionId':'r1','body':{'content':[{'paragraph':{'elements':[{'textRun':{'content':'첫 문단\n'}}]}},{'paragraph':{'elements':[{'textRun':{'content':'둘째 문단\n'}}]}}]}}
  p=self.mock([{'body':doc}])
  r=self.cli('docs.read','--account','work','--params',json.dumps({'documentId':'d'}),'--json',env={'GOOGLE_WORKSPACE_MOCK_HTTP':p})
  self.assertEqual(r.returncode,0,r.stdout+r.stderr);o=json.loads(r.stdout)
  self.assertEqual(o['data']['items'][0]['text'],'첫 문단\n둘째 문단');self.assertEqual(o['data']['items'][0]['paragraphCount'],2)
 def test_slides_read_e2e_outlines_slides(self):
  pres={'presentationId':'p','title':'덱','revisionId':'r','slides':[{'objectId':'s1','pageElements':[{'shape':{'text':{'textElements':[{'textRun':{'content':'표지 제목'}}]}}}]}]}
  p=self.mock([{'body':pres}])
  r=self.cli('slides.read','--account','work','--params',json.dumps({'presentationId':'p'}),'--json',env={'GOOGLE_WORKSPACE_MOCK_HTTP':p})
  self.assertEqual(r.returncode,0,r.stdout+r.stderr);o=json.loads(r.stdout)
  self.assertEqual(o['data']['items'][0]['slideCount'],1);self.assertEqual(o['data']['items'][0]['slides'][0]['text'],['표지 제목'])
 def test_values_update_requires_preview_then_confirm(self):
  args=('sheets.values.update','--account','work','--params',json.dumps({'spreadsheetId':'s','range':'A1:B2','valueInputOption':'RAW'}),'--body',json.dumps({'values':[['x']]}),'--json')
  p=self.mock([{'body':{'spreadsheetId':'s'}}])
  r=self.cli(*args,'--dry-run',env={'GOOGLE_WORKSPACE_MOCK_HTTP':p})
  self.assertEqual(r.returncode,0,r.stdout+r.stderr);o=json.loads(r.stdout)
  self.assertTrue(o['data']['preview']);self.assertTrue(o['data']['effectDigest'])
  r=self.cli(*args,env={'GOOGLE_WORKSPACE_MOCK_HTTP':self.mock([{'body':{}}])})
  self.assertNotEqual(r.returncode,0);self.assertEqual(json.loads(r.stdout)['error']['code'],'APPROVAL_REQUIRED')
 def test_values_update_confirm_executes_put(self):
  args=('sheets.values.update','--account','work','--params',json.dumps({'spreadsheetId':'s','range':'A1:B2','valueInputOption':'RAW'}),'--body',json.dumps({'values':[['x','y']]}),'--json')
  r=self.cli(*args,'--dry-run',env={'GOOGLE_WORKSPACE_MOCK_HTTP':self.mock([{'body':{'spreadsheetId':'s'}}])})
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  token=json.loads(r.stdout)['data']['effectDigest']
  # confirm re-probes the guarded resource once, then performs the single PUT
  p=self.mock([{'body':{'spreadsheetId':'s'}},{'body':{'spreadsheetId':'s','updatedRange':'Sheet1!A1:B2','updatedCells':2}}])
  r=self.cli(*args,'--confirm',token,env={'GOOGLE_WORKSPACE_MOCK_HTTP':p})
  self.assertEqual(r.returncode,0,r.stdout+r.stderr);o=json.loads(r.stdout)
  self.assertEqual(o['data']['resource']['updatedCells'],2,o)
  self.assertEqual(o['effects'][0]['kind'],'confirmed')
 def test_readonly_scope_binding_blocks_write(self):
  self.assertEqual(sorted(json.loads((ROOT/'command_contracts.json').read_text())['sheets.values.update']['requiredScopes']),['https://www.googleapis.com/auth/spreadsheets'])

if __name__=='__main__':unittest.main()
