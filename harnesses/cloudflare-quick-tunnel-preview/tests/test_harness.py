import importlib.util,json,os,stat,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; CLI=ROOT/'cloudflare_quick_tunnel_preview.py'
spec=importlib.util.spec_from_file_location('qt',CLI);qt=importlib.util.module_from_spec(spec);spec.loader.exec_module(qt)
class Unit(unittest.TestCase):
 def test_url_is_strict(self):
  self.assertTrue(qt.validurl('https://safe-name.trycloudflare.com'))
  for x in ('http://x.trycloudflare.com','https://trycloudflare.com','https://x.trycloudflare.com.evil','https://x.trycloudflare.com/path','https://u:p@x.trycloudflare.com'):
   self.assertFalse(qt.validurl(x),x)
 def test_loopback_only_and_port(self):
  self.assertIn('127.0.0.1:1',qt.target('127.0.0.1',1,False))
  for host in ('localhost','0.0.0.0','192.168.1.2'):
   with self.assertRaises(qt.Fail):qt.target(host,8000,False)
  with self.assertRaises(qt.Fail):qt.target('127.0.0.1',0,False)
 def test_binary_rejects_relative_symlink_and_writable(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'c';p.write_text('#!/bin/sh\n');p.chmod(0o755)
   self.assertEqual(qt.binary(str(p))['path'],str(p))
   with self.assertRaises(qt.Fail):qt.binary('relative')
   l=Path(d)/'l';l.symlink_to(p)
   with self.assertRaises(qt.Fail):qt.binary(str(l))
   p.chmod(0o775)
   with self.assertRaises(qt.Fail):qt.binary(str(p))
 def test_owner_only_state_and_malformed_state(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);p.chmod(0o700);(p/'state.json').write_text('{}');(p/'state.json').chmod(0o600)
   with self.assertRaises(qt.Fail) as c:qt.load(p)
   self.assertEqual(c.exception.code,'MALFORMED_STATE')
   p.chmod(0o755)
   with self.assertRaises(qt.Fail):qt.root(p)
 def test_sanitized_bounded_logs(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'l';p.write_text('token=abcdefgh\n'+'x'*20000);p.chmod(0o600)
   x=qt.slog(p);self.assertNotIn('abcdefgh',x);self.assertLessEqual(len(x),4096)
class E2E(unittest.TestCase):
 def call(self,*a):return subprocess.run([sys.executable,str(CLI),*a],text=True,capture_output=True)
 def test_status_absent_and_stop_idempotent(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'state';r=self.call('status','--state-root',str(p));self.assertEqual(r.returncode,0);self.assertEqual(json.loads(r.stdout)['data']['state'],'absent')
   r=self.call('stop','--state-root',str(p));self.assertEqual(r.returncode,0);self.assertFalse(json.loads(r.stdout)['data']['changed'])
 def test_preflight_installed_entrypoint_failure_is_json(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);p.chmod(0o700);r=self.call('preflight','--state-root',str(p),'--cloudflared','relative','--port','8000','--skip-connect')
   self.assertEqual(r.returncode,2);self.assertEqual(json.loads(r.stdout)['error']['code'],'UNSAFE_BINARY')
 def test_manifest_current_gateway_subset(self):
  m=json.loads((ROOT/'harness.json').read_text());self.assertEqual(set(m['commands']),{'status','preflight','start','inspect','stop'})
  allowed={'readOnly','writeSafe','destructive','externalSideEffect'}
  for c in m['commands'].values():
   self.assertTrue(set(c['safetyClasses'])<=allowed)
   for schema in (c['inputSchema'],c['outputSchema']):self.assertTrue(set(schema)<={'type','required','properties','additionalProperties'})
if __name__=='__main__':unittest.main()
