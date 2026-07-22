"""Regression coverage for the installed OpenClaw CLI Harness lifecycle schema."""
import json,re,subprocess,sys,unittest
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
 def test_generator_is_idempotent(self):
  before={(ROOT/name).read_bytes() for name in ('harness.json','command_contracts.json')}
  subprocess.run([sys.executable,str(ROOT/'scripts/generate_schemas.py')],check=True)
  after={(ROOT/name).read_bytes() for name in ('harness.json','command_contracts.json')}
  self.assertEqual(before,after)
 def test_lifecycle_schemas_use_exact_run_intent_subset(self):
  supported={'type','required','properties','additionalProperties'}
  def scan(node,path):
   self.assertIsInstance(node,dict,path)
   self.assertLessEqual(set(node),supported,path)
   if 'type' in node:self.assertIsInstance(node['type'],str,path)
   if node.get('additionalProperties') is False:self.assertTrue(node.get('properties'),path)
   for key,value in node.get('properties',{}).items():scan(value,f'{path}.{key}')
  for name,command in MAN['commands'].items():
   scan(command['inputSchema'],name+'.input')
   scan(command['outputSchema'],name+'.output')
 def test_scopes_and_rich_contracts_remain_outside_manifest(self):
  rich_keywords=set()
  def scan(node):
   if isinstance(node,dict):
    rich_keywords.update(set(node)-{'type','required','properties','additionalProperties'})
    for value in node.values():scan(value)
   elif isinstance(node,list):
    for value in node:scan(value)
  for name,contract in CONTRACTS.items():
   self.assertEqual(contract['inputSchema']['type'],'object')
   scan(contract['inputSchema']);scan(contract['outputSchema'])
   if not name.startswith('auth.'):self.assertTrue(contract['requiredScopes'],name)
  self.assertTrue({'pattern','minimum','maximum','minLength','maxLength','items','const'} <= rich_keywords)

if __name__=='__main__':unittest.main()
