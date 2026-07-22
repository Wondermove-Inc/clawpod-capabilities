"""Regression coverage for the installed OpenClaw CLI Harness lifecycle schema."""
import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MAN=json.loads((ROOT/'harness.json').read_text())
CONTRACTS=json.loads((ROOT/'command_contracts.json').read_text())

class RuntimeManifest(unittest.TestCase):
 def test_actual_runtime_enums_and_command_grammar(self):
  safety={'readOnly','writeSafe','modifiesSource','destructive','secretUse','externalSideEffect','authReuse','humanAccountAction'}
  values={'string','number','integer','boolean','enum','path'}
  self.assertEqual(len(MAN['commands']),151)
  self.assertEqual(len(CONTRACTS),151)
  canonical=set()
  for alias,command in MAN['commands'].items():
   self.assertRegex(alias,r'^[a-z0-9][a-z0-9._:-]{0,127}$')
   self.assertTrue(set(command['safetyClasses']) <= safety)
   self.assertTrue(command['safetyClasses'])
   self.assertNotIn('requiredScopes',command)
   canonical.add(command['baseArgv'][0])
   for arg in command['argMap']:
    self.assertIn(arg['valueType'],values)
    if arg['valueType']=='boolean':self.assertEqual(arg['type'],'booleanFlag')
   for name in ('fields','params','body','batch'):
    if name in command['inputSchema']['properties']:
     self.assertEqual(command['inputSchema']['properties'][name],{'type':'string'})
  self.assertEqual(canonical,set(CONTRACTS))
 def test_scopes_and_rich_contracts_remain_outside_manifest(self):
  for name,contract in CONTRACTS.items():
   self.assertEqual(contract['inputSchema']['type'],'object')
   if not name.startswith('auth.'):self.assertTrue(contract['requiredScopes'],name)

if __name__=='__main__':unittest.main()
