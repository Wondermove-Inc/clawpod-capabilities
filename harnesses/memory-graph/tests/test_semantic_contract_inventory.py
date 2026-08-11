import hashlib, importlib.util, json, re, subprocess, unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]
class SemanticContractInventory(unittest.TestCase):
 def load(self):
  spec=importlib.util.spec_from_file_location('contracts',P/'semantic_contract_inventory.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
 def test_every_manifest_semantic_command_has_exact_handler_contract(self):
  module=self.load(); manifest=json.loads((P/'harness.json').read_text()); semantic={k for k in manifest['commands'] if k.startswith('semantic-')}
  self.assertEqual(semantic,set(module.CONTRACTS)); inv=module.inventory(); self.assertEqual(len(inv['commands']),len(semantic))
  source=(P/'memory_graph.py').read_text()
  for item in inv['commands']:
   spec=manifest['commands'][item['command']]
   self.assertEqual(item['required_output_fields'],['ok','schema_version','command','effects'])
   self.assertEqual(item['safety_classes'],spec['safetyClasses'])
   self.assertIn(item['handler'].split('.')[-1],source)
   private={'semantic-extractor-input','semantic-validate-proposals','semantic-review-queue','semantic-approve','semantic-build','semantic-reconcile','semantic-reconcile-verify'}
   expected=['write_file'] if item['command']=='semantic-export-html' else ['write_private_output'] if item['command'] in private else []
   self.assertEqual(item['effects'],expected)
   self.assertFalse(item['error_envelope']['secret_values_allowed']); self.assertTrue(item['redaction']['stdout_must_not_echo_secret'])
 def test_extractor_output_name_remains_relative_string_and_root_is_gateway_output_path(self):
  manifest=json.loads((P/'harness.json').read_text())
  private={'semantic-extractor-input','semantic-validate-proposals','semantic-review-queue','semantic-approve','semantic-build','semantic-reconcile','semantic-reconcile-verify'}
  for command in private:
   args={item['arg']:item for item in manifest['commands'][command]['argMap']}
   self.assertEqual(args['output']['valueType'],'string'); self.assertNotIn('pathRole',args['output'])
   self.assertEqual(args['outputRoot']['valueType'],'path'); self.assertEqual(args['outputRoot']['pathRole'],'output')
   self.assertEqual(manifest['commands'][command]['safetyClasses'],['writeSafe'])
 def test_inventory_digest_and_cli_are_deterministic(self):
  first=subprocess.check_output(['python3',str(P/'semantic_contract_inventory.py')]); second=subprocess.check_output(['python3',str(P/'semantic_contract_inventory.py')]); self.assertEqual(first,second)
  out=json.loads(first); digest=out.pop('inventory_sha256'); self.assertEqual(digest,hashlib.sha256(json.dumps(out,sort_keys=True,separators=(',',':')).encode()).hexdigest())
 def test_runtime_success_and_error_envelopes_and_secret_redaction(self):
  fixture=P/'tests/fixtures/entity-proposals'; root=fixture
  ok=subprocess.run([str(P/'memory_graph.py'),'semantic-extractor-input','--root',str(root),'--agent-id','test-agent','--workspace-id','test-workspace'],text=True,capture_output=True)
  self.assertEqual(ok.returncode,0,ok.stderr); payload=json.loads(ok.stdout); self.assertTrue(payload['ok']); self.assertEqual(payload['effects'],[])
  secret='password=abcdefghijklmnop'; bad=root/'secret-contract.json'; bad.write_text(json.dumps({'secret':secret}))
  try:
   result=subprocess.run([str(P/'memory_graph.py'),'semantic-build','--root',str(root),'--input',bad.name],text=True,capture_output=True)
  finally: bad.unlink()
  self.assertEqual(result.returncode,2); error=json.loads(result.stdout); self.assertFalse(error['ok']); self.assertEqual(error['effects'],[]); self.assertNotIn(secret,result.stdout+result.stderr); self.assertTrue({'schema_version','command','effects','error'}<=set(error))
if __name__=='__main__': unittest.main()
