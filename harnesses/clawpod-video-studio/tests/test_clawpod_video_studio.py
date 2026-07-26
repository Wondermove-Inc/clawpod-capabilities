import importlib.util, json, os, stat, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/'clawpod_video_studio.py'
spec=importlib.util.spec_from_file_location('om',CLI); om=importlib.util.module_from_spec(spec); spec.loader.exec_module(om)

class HarnessTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.root=Path(self.t.name)/'state'
 def tearDown(self): self.t.cleanup()
 def invoke(self,cmd,payload=None,**opts):
  argv=[sys.executable,str(CLI),cmd,'--root',str(self.root)]
  if payload is not None: argv+=['--input-json',json.dumps(payload)]
  for k,v in opts.items(): argv += ['--'+k.replace('_','-'),str(v)]
  p=subprocess.run(argv,text=True,capture_output=True); self.assertTrue(p.stdout,p.stderr); return p,json.loads(p.stdout)
 def create(self,pid='demo',pipeline='animated-explainer'):
  p,o=self.invoke('project.create',{'projectId':pid,'pipelineId':pipeline,'idempotencyKey':'k'}); self.assertEqual(p.returncode,0); return o
 def test_every_command_declared(self):
  manifest=json.loads((ROOT/'harness.json').read_text()); self.assertEqual(set(manifest['commands']),set(om.COMMANDS)); self.assertEqual(manifest['name'],'clawpod-video-studio'); self.assertEqual(manifest['title'],'ClawPod Video Studio')
 def test_stable_envelope(self):
  p,o=self.invoke('system.version'); self.assertEqual(p.returncode,0); self.assertEqual(o['schemaVersion'],'1.0'); self.assertTrue(o['ok']); self.assertIsNone(o['error'])
 def test_all_pipelines_and_documentary_patch(self):
  p,o=self.invoke('pipeline.list'); self.assertEqual(len(o['data']['items']),13)
  documentary=next(item for item in o['data']['items'] if item['id']=='documentary-montage'); self.assertTrue(documentary['contractValid'])
  p,o=self.invoke('pipeline.inspect',{'pipelineId':'documentary-montage'}); self.assertEqual(p.returncode,0); self.assertTrue(o['data']['contractValid'])
  p,o=self.invoke('system.validate'); self.assertEqual(p.returncode,0); self.assertTrue(o['data']['valid']); self.assertIn('openmontage-documentary-category',o['data']['localPatches'])
 def test_pointer_only_onboarding_and_no_env(self):
  bad={'provider':'openai','bindings':{'OPENAI_API_KEY':'sk-real-looking-secret-123456789'}}
  p,o=self.invoke('connection.configure',bad); self.assertNotEqual(p.returncode,0); self.assertEqual(o['error']['code'],'INVALID_ARGUMENT'); self.assertNotIn('sk-real',p.stdout); self.assertFalse((self.root/'.env').exists())
  good={'provider':'openai','bindings':{'OPENAI_API_KEY':{'pointerId':'secret:openai:123456'}}}
  p,o=self.invoke('connection.configure',good); self.assertEqual(p.returncode,0); self.assertEqual(o['data']['status'],'configured_unverified'); self.assertEqual(o['data']['bindings']['OPENAI_API_KEY']['pointerId'],'secret:openai:123456')
 def test_partial_and_deferred_connections(self):
  p,o=self.invoke('connection.configure',{'provider':'volcengine','bindings':{'VOLC_ACCESSKEY':{'pointerId':'secret:volc:access1'}}}); self.assertEqual(o['data']['status'],'missing_companion_field'); self.assertIn('VOLC_SECRETKEY',o['data']['missing'])
  p,o=self.invoke('provider.summary'); self.assertEqual(o['data']['connected'],0)
 def test_project_idempotency_and_conflict(self):
  self.create(); p,o=self.invoke('project.create',{'projectId':'demo','pipelineId':'animated-explainer','idempotencyKey':'k'}); self.assertEqual(p.returncode,0)
  p,o=self.invoke('project.create',{'projectId':'demo','pipelineId':'cinematic','idempotencyKey':'k2'}); self.assertEqual(p.returncode,4); self.assertEqual(o['error']['code'],'CONFLICT')
 def test_path_traversal_and_symlink(self):
  self.create(); p,o=self.invoke('qa.run',{'projectId':'demo','relativePath':'../../etc/passwd'}); self.assertEqual(o['error']['code'],'PATH_VIOLATION')
  pdir=self.root/'projects'/'demo'; (pdir/'assets'/'ok').write_text('x'); (pdir/'assets'/'link').symlink_to('/etc/passwd'); p,o=self.invoke('qa.run',{'projectId':'demo','relativePath':'assets/link'}); self.assertEqual(o['error']['code'],'PATH_VIOLATION')
 def test_plan_prepare_exact_approval(self):
  self.create(); self.invoke('project.plan',{'projectId':'demo','plan':{'concept':'x'}})
  p,o=self.invoke('run.prepare',{'projectId':'demo','providers':['openai'],'operations':['assets'],'maximumUsd':1.5}); intent=o['data']
  p,o=self.invoke('run.start',{'projectId':'demo','intentId':intent['intentId'],'planDigest':'sha256:changed','approvalReference':'a','maximumAuthorizedUsd':2}); self.assertEqual(p.returncode,6)
  p,o=self.invoke('run.start',{'projectId':'demo','intentId':intent['intentId'],'planDigest':intent['planDigest']}); self.assertEqual(p.returncode,6)
  p,o=self.invoke('run.start',{'projectId':'demo','intentId':intent['intentId'],'planDigest':intent['planDigest'],'approvalReference':'approval-1','maximumAuthorizedUsd':1.5}); self.assertEqual(p.returncode,0); self.assertEqual(o['data']['state'],'awaiting_human')
 def test_cancel_requires_confirmation_and_preserves_artifacts(self):
  self.create(); self.invoke('project.plan',{'projectId':'demo','plan':{'concept':'x'}}); _,o=self.invoke('run.prepare',{'projectId':'demo','operations':[]}); i=o['data']; _,o=self.invoke('run.start',{'projectId':'demo','intentId':i['intentId'],'planDigest':i['planDigest']}); jid=o['data']['jobId']
  p,o=self.invoke('run.cancel',{'jobId':jid}); self.assertEqual(p.returncode,6)
  p,o=self.invoke('run.cancel',{'jobId':jid,'confirm':'cancel-job'}); self.assertEqual(o['data']['state'],'cancelled')
 def test_redaction(self):
  v=om.redact({'authorization':'Bearer abc','nested':{'apiKey':'topsecret'},'safe':'hello'}); self.assertEqual(v['authorization'],'[REDACTED]'); self.assertEqual(v['nested']['apiKey'],'[REDACTED]'); self.assertEqual(v['safe'],'hello')
 def test_malformed_input_and_stable_exit(self):
  p=subprocess.run([sys.executable,str(CLI),'system.version','--root',str(self.root),'--input-json','{'],text=True,capture_output=True); o=json.loads(p.stdout); self.assertEqual(p.returncode,2); self.assertEqual(o['error']['code'],'INVALID_ARGUMENT')
 def test_qa_and_artifact_integrity(self):
  self.create(); f=self.root/'projects'/'demo'/'renders'/'final.mp4'; f.write_bytes(b'not-a-real-video')
  p,o=self.invoke('qa.run',{'projectId':'demo','relativePath':'renders/final.mp4'}); self.assertEqual(p.returncode,0); self.assertEqual(o['data']['status'],'passed')
  p,o=self.invoke('artifact.list',{'projectId':'demo'}); self.assertGreaterEqual(len(o['data']['items']),2); self.assertTrue(all(i['sha256'].startswith('sha256:') for i in o['data']['items']))
 def test_install_state_requires_onboarding(self):
  p,o=self.invoke('install.inspect'); self.assertTrue(o['data']['onboardingRequired']); self.assertFalse(o['data']['connected'])

if __name__=='__main__': unittest.main()
