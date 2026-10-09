import hashlib, importlib.util, json, os, shutil, stat, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/'clawpod_video_studio.py'
spec=importlib.util.spec_from_file_location('om',CLI); om=importlib.util.module_from_spec(spec); spec.loader.exec_module(om)

def resolved_runtime():
 return om.runtime({},required=False)
NEEDS_RUNTIME=unittest.skipUnless(resolved_runtime(),'pinned OpenMontage runtime is not installed on this host')
NEEDS_RUNTIME_VENV=unittest.skipUnless(resolved_runtime() and (resolved_runtime()/'.clawpod-venv'/'bin'/'python').exists(),'pinned OpenMontage runtime venv is not installed on this host')

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
  p,o=self.invoke('project.create',{'projectId':pid,'pipelineId':pipeline,'idempotencyKey':'k'})
  if (o.get('error') or {}).get('code')=='RUNTIME_NOT_FOUND':self.skipTest('pinned OpenMontage runtime is not installed on this host')
  self.assertEqual(p.returncode,0); return o
 def wait_job(self,jid,states=('succeeded','failed','cancelled'),timeout=8):
  deadline=time.time()+timeout; last=None
  while time.time()<deadline:
   _,last=self.invoke('run.status',{'jobId':jid})
   if last['data']['state'] in states: return last['data']
   time.sleep(.05)
  self.fail(f'job {jid} did not reach {states}: {last}')
 def test_every_command_declared(self):
  manifest=json.loads((ROOT/'harness.json').read_text()); self.assertEqual(set(manifest['commands']),set(om.COMMANDS)); self.assertEqual(manifest['name'],'clawpod-video-studio'); self.assertEqual(manifest['title'],'ClawPod Video Studio')
 def test_stable_envelope(self):
  p,o=self.invoke('system.version'); self.assertEqual(p.returncode,0); self.assertEqual(o['schemaVersion'],'1.0'); self.assertTrue(o['ok']); self.assertIsNone(o['error'])
 @NEEDS_RUNTIME
 def test_all_pipelines_and_documentary_patch(self):
  p,o=self.invoke('pipeline.list'); self.assertEqual(len(o['data']['items']),13)
  for item in o['data']['items']:
   self.assertGreater(item['stageCount'],0); self.assertTrue(item['manifestDigest'].startswith('sha256:'))
   for stage in item['stages']:
    self.assertIsInstance(stage['tools'],list); self.assertIsInstance(stage['checkpointRequired'],bool); self.assertIsInstance(stage['produces'],list)
  documentary=next(item for item in o['data']['items'] if item['id']=='documentary-montage'); self.assertTrue(documentary['contractValid'])
  p,o=self.invoke('pipeline.inspect',{'pipelineId':'documentary-montage'}); self.assertEqual(p.returncode,0); self.assertTrue(o['data']['contractValid'])
  p,o=self.invoke('system.validate'); self.assertEqual(p.returncode,0); self.assertTrue(o['data']['valid']); self.assertIn('openmontage-documentary-category',o['data']['localPatches'])
 def test_pointer_only_onboarding_and_no_env(self):
  bad={'provider':'openai','bindings':{'OPENAI_API_KEY':'sk-real-looking-secret-123456789'}}
  p,o=self.invoke('connection.configure',bad); self.assertNotEqual(p.returncode,0); self.assertEqual(o['error']['code'],'INVALID_ARGUMENT'); self.assertNotIn('sk-real',p.stdout); self.assertFalse((self.root/'.env').exists())
  good={'provider':'openai','bindings':{'OPENAI_API_KEY':{'pointerId':'secret:openai:123456'}}}
  p,o=self.invoke('connection.configure',good); self.assertEqual(p.returncode,0); self.assertEqual(o['data']['status'],'configured_unverified'); self.assertEqual(o['data']['bindings']['OPENAI_API_KEY']['pointerId'],'secret:openai:123456')
 def test_partial_deferred_and_revoked_connections(self):
  p,o=self.invoke('connection.configure',{'provider':'volcengine','bindings':{'VOLC_ACCESSKEY':{'pointerId':'secret:volc:access1'}}}); self.assertEqual(o['data']['status'],'missing_companion_field'); self.assertIn('VOLC_SECRETKEY',o['data']['missing'])
  p,o=self.invoke('provider.summary'); self.assertEqual(o['data']['connected'],0)
  p,o=self.invoke('connection.revoke',{'provider':'volcengine'}); self.assertEqual(p.returncode,6)
  p,o=self.invoke('connection.revoke',{'provider':'volcengine','confirm':'remove-binding'}); self.assertEqual(p.returncode,0); self.assertEqual(o['data']['status'],'revoked')
  p,o=self.invoke('connection.list'); item=next(i for i in o['data']['items'] if i['provider']=='volcengine'); self.assertEqual(item['status'],'revoked'); self.assertEqual(item['bindings'],{})
 def test_project_idempotency_and_conflict(self):
  self.create(); p,o=self.invoke('project.create',{'projectId':'demo','pipelineId':'animated-explainer','idempotencyKey':'k'}); self.assertEqual(p.returncode,0)
  p,o=self.invoke('project.create',{'projectId':'demo','pipelineId':'cinematic','idempotencyKey':'k2'}); self.assertEqual(p.returncode,4); self.assertEqual(o['error']['code'],'CONFLICT')
 def test_path_traversal_and_symlink(self):
  self.create(); p,o=self.invoke('qa.run',{'projectId':'demo','relativePath':'../../etc/passwd'}); self.assertEqual(o['error']['code'],'PATH_VIOLATION')
  pdir=self.root/'projects'/'demo'; (pdir/'assets'/'ok').write_text('x'); (pdir/'assets'/'link').symlink_to('/etc/passwd'); p,o=self.invoke('qa.run',{'projectId':'demo','relativePath':'assets/link'}); self.assertEqual(o['error']['code'],'PATH_VIOLATION')
 def test_plan_prepare_exact_approval(self):
  self.create(); self.invoke('project.plan',{'projectId':'demo','plan':{'concept':'x'}})
  self.invoke('connection.configure',{'provider':'openai','bindings':{'OPENAI_API_KEY':{'pointerId':'secret:openai:approval-test'}}})
  p,o=self.invoke('run.prepare',{'projectId':'demo','providers':['openai'],'operations':['assets'],'maximumUsd':1.5}); intent=o['data']
  p,o=self.invoke('run.start',{'projectId':'demo','intentId':intent['intentId'],'planDigest':'sha256:changed','approvalReference':'a','maximumAuthorizedUsd':2}); self.assertEqual(p.returncode,6)
  p,o=self.invoke('run.start',{'projectId':'demo','intentId':intent['intentId'],'planDigest':intent['planDigest']}); self.assertEqual(p.returncode,6)
  old=os.environ.get('OPENAI_API_KEY'); os.environ['OPENAI_API_KEY']='unit-test-placeholder-not-a-real-key'
  try:
   expiry=om.require_future_expiry('2099-01-01T00:00:00Z'); binding=om.approval_binding_digest(intent['inputDigest'],intent['providers'],intent['operations'],intent['maximumUsd'],'approval-1',expiry)
   p,o=self.invoke('run.start',{'projectId':'demo','intentId':intent['intentId'],'planDigest':intent['planDigest'],'approvalReference':'approval-1','maximumAuthorizedUsd':1.5,'approvalExpiresAt':'2099-01-01T00:00:00Z','approvalBindingDigest':binding}); self.assertEqual(p.returncode,0); self.assertIn(o['data']['state'],('queued','running','succeeded'))
   final=self.wait_job(o['data']['jobId']); self.assertEqual(final['state'],'succeeded')
  finally:
   if old is None: os.environ.pop('OPENAI_API_KEY',None)
   else: os.environ['OPENAI_API_KEY']=old
 def test_run_prepare_binds_inferred_provider_contract(self):
  self.create(); self.invoke('project.plan',{'projectId':'demo','plan':{'concept':'provider-binding'}})
  op={'tool':'openai_image','input':{'prompt':'safe test prompt','output_path':'assets/test.png'},'maximumUsd':1.0}
  p,o=self.invoke('run.prepare',{'projectId':'demo','operations':[op],'maximumUsd':1.0}); self.assertEqual(p.returncode,6); self.assertEqual(o['error']['code'],'APPROVAL_REQUIRED'); self.assertIn('openai',o['error']['details']['missingProviders'])
  p,o=self.invoke('run.prepare',{'projectId':'demo','operations':[op],'providers':['openai'],'maximumUsd':0.5}); self.assertEqual(p.returncode,6); self.assertEqual(o['error']['code'],'COST_CEILING_EXCEEDED')
  p,o=self.invoke('run.prepare',{'projectId':'demo','operations':[op],'providers':['openai'],'maximumUsd':1.0}); self.assertEqual(p.returncode,0); self.assertEqual(o['data']['providers'],['openai']); self.assertEqual(o['data']['operations'][0]['provider'],'openai')
 def test_cancel_requires_confirmation_and_preserves_artifacts(self):
  self.create(); self.invoke('project.plan',{'projectId':'demo','plan':{'concept':'x'}})
  operation={'tool':'ffmpeg','input':{'args':['-re','-f','lavfi','-i','testsrc=size=16x16:rate=1','-t','30','-f','null','-']},'timeoutSeconds':60}
  _,o=self.invoke('run.prepare',{'projectId':'demo','operations':[operation]}); i=o['data']; _,o=self.invoke('run.start',{'projectId':'demo','intentId':i['intentId'],'planDigest':i['planDigest']}); jid=o['data']['jobId']
  p,o=self.invoke('run.cancel',{'jobId':jid}); self.assertEqual(p.returncode,6)
  p,o=self.invoke('run.cancel',{'jobId':jid,'confirm':'cancel-job','ownerNonce':o.get('data',{}).get('ownerNonce','wrong')}); self.assertEqual(p.returncode,6)
  _,state=self.invoke('run.status',{'jobId':jid}); nonce=state['data']['ownerNonce']
  p,o=self.invoke('run.cancel',{'jobId':jid,'confirm':'cancel-job','ownerNonce':nonce}); self.assertEqual(o['data']['state'],'cancel_requested')
  final=self.wait_job(jid); self.assertEqual(final['state'],'cancelled')
  p,o=self.invoke('run.cancel',{'jobId':jid}); self.assertEqual(p.returncode,0); self.assertTrue(o['data']['cancelIdempotent'])
 def test_detached_job_uses_immutable_intent_snapshot(self):
  self.create(); self.invoke('project.plan',{'projectId':'demo','plan':{'concept':'immutable'}})
  op={'tool':'ffmpeg','input':{'args':['-re','-f','lavfi','-i','testsrc=size=16x16:rate=1','-t','1','-f','null','-']},'timeoutSeconds':5}
  _,prepared=self.invoke('run.prepare',{'projectId':'demo','operations':[op]}); intent=prepared['data']; _,started=self.invoke('run.start',{'projectId':'demo','intentId':intent['intentId'],'planDigest':intent['planDigest']}); jid=started['data']['jobId']
  p,rejected=self.invoke('run.resume',{'projectId':'demo','jobId':jid,'intentId':intent['intentId'],'planDigest':intent['planDigest']}); self.assertEqual(p.returncode,4); self.assertEqual(rejected['error']['code'],'CONFLICT')
  self.invoke('run.prepare',{'projectId':'demo','operations':['research']})
  final=self.wait_job(jid,timeout=10); self.assertEqual(final['state'],'succeeded'); self.assertEqual(final['intentDigest'],intent['inputDigest']); self.assertEqual(final['intentSnapshot']['operations'][0]['tool'],'ffmpeg')
 def test_human_checkpoint_pauses_and_resumes(self):
  self.create(); self.invoke('project.plan',{'projectId':'demo','plan':{'concept':'gate'}})
  ops=['research',{'checkpoint':'research'},'proposal']; _,prepared=self.invoke('run.prepare',{'projectId':'demo','operations':ops}); intent=prepared['data']
  _,started=self.invoke('run.start',{'projectId':'demo','intentId':intent['intentId'],'planDigest':intent['planDigest']}); first=started['data']['jobId']
  waiting=self.wait_job(first,states=('awaiting_human','failed')); self.assertEqual(waiting['state'],'awaiting_human'); self.assertEqual(waiting['stage'],'research')
  p,o=self.invoke('checkpoint.approve',{'projectId':'demo','stage':'research'}); self.assertEqual(p.returncode,2)
  artifact=self.root/'projects'/'demo'/'artifacts'/'research.json'; artifact.write_text('{"approved":true}')
  expiry=om.require_future_expiry('2099-01-01T00:00:00Z'); digest=om.file_sha(artifact); binding=om.checkpoint_approval_binding_digest(first,waiting['intentDigest'],'research',digest,'gate-approval',expiry)
  p,o=self.invoke('checkpoint.approve',{'projectId':'demo','jobId':first,'stage':'research','relativePath':'artifacts/research.json','artifactDigest':digest,'approvalReference':'gate-approval','approvalExpiresAt':'2099-01-01T00:00:00Z','approvalBindingDigest':binding}); self.assertEqual(p.returncode,0)
  _,resumed=self.invoke('run.resume',{'projectId':'demo','jobId':first,'intentId':intent['intentId'],'planDigest':intent['planDigest']}); final=self.wait_job(resumed['data']['jobId']); self.assertEqual(final['state'],'succeeded')
  p,duplicate=self.invoke('run.resume',{'projectId':'demo','jobId':first,'intentId':intent['intentId'],'planDigest':intent['planDigest']}); self.assertEqual(p.returncode,4); self.assertEqual(duplicate['error']['code'],'CONFLICT')
 def test_resume_uses_validated_checkpoint(self):
  self.create(); self.invoke('project.plan',{'projectId':'demo','plan':{'concept':'resume'}})
  operations=['research',{'tool':'ffmpeg','input':{'args':['-definitely-invalid-option']},'timeoutSeconds':2}]
  _,prepared=self.invoke('run.prepare',{'projectId':'demo','operations':operations}); intent=prepared['data']
  _,started=self.invoke('run.start',{'projectId':'demo','intentId':intent['intentId'],'planDigest':intent['planDigest']}); first=started['data']['jobId']
  final=self.wait_job(first); self.assertEqual(final['state'],'failed')
  _,resumed=self.invoke('run.resume',{'projectId':'demo','jobId':first,'intentId':intent['intentId'],'planDigest':intent['planDigest']}); second=resumed['data']['jobId']; self.assertEqual(resumed['data']['resumedFrom'],first); self.assertEqual(resumed['data']['progress']['completed'],1)
  final2=self.wait_job(second); self.assertEqual(final2['state'],'failed')
  _,logs=self.invoke('run.logs',{'jobId':second}); self.assertNotIn('research',logs['data']['text']); self.assertIn('"index":1',logs['data']['text'])
 def test_redaction(self):
  v=om.redact({'authorization':'Bearer abc','nested':{'apiKey':'topsecret'},'safe':'hello'}); self.assertEqual(v['authorization'],'[REDACTED]'); self.assertEqual(v['nested']['apiKey'],'[REDACTED]'); self.assertEqual(v['safe'],'hello')
 def test_malformed_input_and_stable_exit(self):
  p=subprocess.run([sys.executable,str(CLI),'system.version','--root',str(self.root),'--input-json','{'],text=True,capture_output=True); o=json.loads(p.stdout); self.assertEqual(p.returncode,2); self.assertEqual(o['error']['code'],'INVALID_ARGUMENT')
 def test_qa_and_artifact_integrity(self):
  self.create(); f=self.root/'projects'/'demo'/'renders'/'final.mp4'
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc=size=32x32:rate=2','-t','1','-c:v','mpeg4','-y',str(f)],check=True)
  p,o=self.invoke('qa.run',{'projectId':'demo','relativePath':'renders/final.mp4'}); self.assertEqual(p.returncode,0); self.assertEqual(o['data']['status'],'passed'); self.assertTrue(o['data']['checks']['video']['passed'])
  bad=self.root/'projects'/'demo'/'renders'/'invalid.mp4'; bad.write_bytes(b'not-a-real-video')
  p,o=self.invoke('qa.run',{'projectId':'demo','relativePath':'renders/invalid.mp4'}); self.assertEqual(p.returncode,0); self.assertEqual(o['data']['status'],'failed')
  p,o=self.invoke('artifact.list',{'projectId':'demo'}); self.assertGreaterEqual(len(o['data']['items']),3); self.assertTrue(all(i['sha256'].startswith('sha256:') for i in o['data']['items']))
 @NEEDS_RUNTIME_VENV
 def test_upstream_registry_and_local_tool_execution(self):
  runtime=resolved_runtime()
  p=subprocess.run([str(runtime/'.clawpod-venv/bin/python'),str(CLI),'_openmontage_runner'],input=json.dumps({'operation':'list'}),text=True,capture_output=True,env={**os.environ,'OPENMONTAGE_RUNTIME':str(runtime)})
  listing=json.loads(p.stdout); self.assertEqual(p.returncode,0); self.assertGreaterEqual(listing['data']['count'],100); self.assertIn('audio_probe',listing['data']['names'])
  self.create(); wav=self.root/'projects'/'demo'/'assets'/'tone.wav'; subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=0.2','-y',str(wav)],check=True)
  payload={'tool':'audio_probe','projectId':'demo','input':{'input_path':'assets/tone.wav'},'maximumUsd':0}
  p,o=self.invoke('tool.prepare',payload); self.assertEqual(p.returncode,0); payload['toolDigest']=o['data']['toolDigest']
  p,o=self.invoke('tool.run',payload); self.assertEqual(p.returncode,0); self.assertEqual(o['data']['tool'],'audio_probe'); self.assertEqual(o['data']['cost']['actualUsd'],0); self.assertIn('data_digest',o['data']['result']); self.assertNotIn('data',o['data']['result'])
 def test_tool_path_and_ffmpeg_argv_are_bounded(self):
  self.create()
  p,o=self.invoke('tool.prepare',{'tool':'audio_probe','input':{'input_path':'../../etc/passwd'},'projectId':'demo'}); self.assertEqual(p.returncode,2); self.assertEqual(o['error']['code'],'PATH_VIOLATION')
  payload={'tool':'ffmpeg','projectId':'demo','input':{'args':['-i','/etc/passwd','renders/out.mp4']}}
  p,o=self.invoke('tool.prepare',payload); self.assertEqual(p.returncode,0); payload['toolDigest']=o['data']['toolDigest']
  p,o=self.invoke('tool.run',payload); self.assertEqual(p.returncode,2); self.assertEqual(o['error']['code'],'PATH_VIOLATION')
 @NEEDS_RUNTIME
 def test_api_tool_requires_ceiling_approval_and_injected_secret(self):
  p,o=self.invoke('tool.prepare',{'tool':'openai_image','input':{'prompt':'x'},'maximumUsd':0}); self.assertEqual(p.returncode,6); self.assertEqual(o['error']['code'],'COST_CEILING_REQUIRED')
  payload={'tool':'openai_image','input':{'prompt':'x'},'maximumUsd':1.0}
  p,o=self.invoke('tool.prepare',payload); self.assertEqual(p.returncode,0); payload['toolDigest']=o['data']['toolDigest']
  p,o=self.invoke('tool.run',payload); self.assertEqual(p.returncode,6); self.assertEqual(o['error']['code'],'APPROVAL_REQUIRED')
  payload.update(approvalReference='approval-test',maximumAuthorizedUsd=1.0,approvalExpiresAt='2099-01-01T00:00:00Z')
  expiry=om.require_future_expiry(payload['approvalExpiresAt']); spec_payload={k:payload[k] for k in ('tool','input','maximumUsd')}; spec_payload.update(projectId=None,provider='openai',model=None,operation='execute',timeoutSeconds=60)
  payload['approvalBindingDigest']=om.tool_approval_binding_digest(payload['toolDigest'],spec_payload,'approval-test',expiry)
  p,o=self.invoke('tool.run',payload); self.assertEqual(p.returncode,5); self.assertEqual(o['error']['code'],'AUTH_REQUIRED')
 def test_nonbillable_verifier_success_and_auth_failure(self):
  class Response:
   status=200
   def __enter__(self): return self
   def __exit__(self,*args): return False
   def read(self,n): return b'{"data":[{"id":"model"}]}'
  with mock.patch.object(om.urllib.request,'urlopen',return_value=Response()):
   result=om.verify_provider('openai',{'OPENAI_API_KEY':'unit-test-placeholder'}); self.assertEqual(result['status'],'connected'); self.assertFalse(result['verification']['billingAttempted']); self.assertEqual(result['verification']['summary']['itemCount'],1); self.assertNotIn('unit-test-placeholder',json.dumps(result))
  with mock.patch.object(om.urllib.request,'urlopen',side_effect=om.urllib.error.HTTPError('https://api.openai.com/v1/models',401,'unauthorized',{},None)):
   with self.assertRaises(om.E) as ctx: om.verify_provider('openai',{'OPENAI_API_KEY':'unit-test-placeholder'})
   self.assertEqual(ctx.exception.code,'AUTH_INVALID')
 def test_secret_file_permissions_are_enforced(self):
  secret=self.root/'injected-secret'; secret.parent.mkdir(parents=True,exist_ok=True); secret.write_text('placeholder'); secret.chmod(0o644)
  self.invoke('connection.configure',{'provider':'openai','bindings':{'OPENAI_API_KEY':{'pointerId':'secret:openai:file-test','source':'file','fileEnvironment':'OPENAI_TEST_FILE'}}})
  old=os.environ.get('OPENAI_TEST_FILE'); os.environ['OPENAI_TEST_FILE']=str(secret)
  try:
   p,o=self.invoke('connection.verify',{'provider':'openai','approvalReference':'verify-test'}); self.assertEqual(p.returncode,5); self.assertEqual(o['error']['code'],'SECRET_FILE_PERMISSIONS')
  finally:
   if old is None: os.environ.pop('OPENAI_TEST_FILE',None)
   else: os.environ['OPENAI_TEST_FILE']=old
 def test_install_state_requires_onboarding(self):
  p,o=self.invoke('install.inspect'); self.assertTrue(o['data']['onboardingRequired']); self.assertFalse(o['data']['connected'])

if __name__=='__main__': unittest.main()


class ProvisionTests(unittest.TestCase):
 """Offline coverage of install.provision with a local fixture upstream; the real fetch is exercised on agent images."""
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); base=Path(self.t.name); self.state=base/'state'; self.state.mkdir()
  up=base/'upstream'; (up/'pipeline_defs').mkdir(parents=True); (up/'tools').mkdir(); (up/'remotion-composer').mkdir()
  (up/'pipeline_defs'/'demo.yaml').write_text('name: demo\nstages: []\n'); (up/'tools'/'README').write_text('tools\n')
  (up/'remotion-composer'/'package-lock.json').write_text('{"lockfileVersion":3}\n'); (up/'target.txt').write_text('before\n')
  git=lambda *a:subprocess.run(['git','-C',str(up),*a],check=True,capture_output=True,text=True).stdout.strip()
  git('init','-q'); git('config','user.email','t@example.invalid'); git('config','user.name','t'); git('add','-A'); git('commit','-qm','fixture')
  self.commit=git('rev-parse','HEAD'); self.tree=git('rev-parse','HEAD^{tree}'); self.upstream=up
  self.patch=base/'fix.patch'; self.patch.write_text('--- a/target.txt\n+++ b/target.txt\n@@ -1 +1 @@\n-before\n+after\n')
  after='sha256:'+hashlib.sha256(b'after\n').hexdigest()
  self.saved={k:getattr(om,k) for k in ('UPSTREAM_COMMIT','UPSTREAM_LOCK','DEPENDENCY_LOCK','PACKAGE_ROOT','provision_python','provision_node','locked_python_pins','installed_python_distributions')}
  pkg=base/'pkg'; (pkg/'patches').mkdir(parents=True); shutil.copy(self.patch,pkg/'patches'/'fix.patch'); shutil.copy(ROOT/'requirements.lock',pkg/'requirements.lock')
  om.PACKAGE_ROOT=pkg; om.UPSTREAM_COMMIT=self.commit
  om.UPSTREAM_LOCK={**om.UPSTREAM_LOCK,'commit':self.commit,'treeDigest':'git:'+self.tree,'patches':[{'id':'fix','path':'patches/fix.patch','sha256':'sha256:'+hashlib.sha256(self.patch.read_bytes()).hexdigest()}],'patchedFiles':[{'path':'target.txt','sha256':after}]}
  om.DEPENDENCY_LOCK={**om.DEPENDENCY_LOCK,'npmLockDigest':'sha256:'+hashlib.sha256((up/'remotion-composer'/'package-lock.json').read_bytes()).hexdigest()}
  def fake_python(stage):
   b=stage/'.clawpod-venv'/'bin'; b.mkdir(parents=True); (b/'python').symlink_to(Path(sys.executable).resolve())
  om.provision_python=fake_python; om.provision_node=lambda stage:(stage/'remotion-composer'/'node_modules').mkdir()
  om.locked_python_pins=lambda:{'demo':'1.0'}; om.installed_python_distributions=lambda py:{'demo':'1.0'}
 def tearDown(self):
  for k,v in self.saved.items(): setattr(om,k,v)
  self.t.cleanup()
 def test_provision_fetches_patches_validates_and_activates_with_backup(self):
  status=self.state/'provision.json'
  active=om.provision_runtime(self.state,str(self.upstream),status)
  self.assertTrue(active['valid'],active); runtime=self.state/'runtime'
  self.assertEqual((runtime/'target.txt').read_text(),'after\n'); self.assertTrue((runtime/'remotion-composer'/'node_modules').is_dir())
  self.assertEqual(json.loads(status.read_text())['step'],'activate')
  om.provision_runtime(self.state,str(self.upstream),status)
  self.assertTrue((self.state/'runtime.backup').is_dir()); self.assertFalse(list(self.state.glob('runtime.provision-*')))
 def test_provision_rejects_wrong_tree_and_activates_nothing(self):
  om.UPSTREAM_LOCK={**om.UPSTREAM_LOCK,'treeDigest':'git:'+'0'*40}
  with self.assertRaises(om.E) as caught: om.provision_runtime(self.state,str(self.upstream),self.state/'provision.json')
  self.assertEqual(caught.exception.code,'DIGEST_MISMATCH'); self.assertFalse((self.state/'runtime').exists()); self.assertFalse(list(self.state.glob('runtime.provision-*')))
 def test_python_environment_check_names_missing_and_unexpected(self):
  status=self.state/'provision.json'; om.provision_runtime(self.state,str(self.upstream),status)
  om.installed_python_distributions=lambda py:{'demo':'2.0','extra':'1'}
  v=om.validate_runtime({'runtimePath':str(self.state/'runtime')}); check=v['checks']['pythonEnvironment']
  self.assertFalse(v['valid']); self.assertEqual(check['missing'],['demo==1.0']); self.assertEqual(check['unexpected'],['demo==2.0','extra==1'])

class ProvisionStartTests(unittest.TestCase):
 def test_fast_worker_failure_is_not_overwritten_by_the_starting_status(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d)/'state'; r.mkdir()
   class FastFailingPopen:
    def __init__(self,*a,**k):
     # The worker records its failure before the parent regains control.
     (r/'provision.json').write_text(json.dumps({"state":"failed","error":{"code":"PREREQUISITE_MISSING","message":"git is required"},"pid":None}))
     self.pid=os.getpid()
   from types import SimpleNamespace
   with mock.patch.object(om.subprocess,'Popen',FastFailingPopen):
    st,_=om.handler('install.provision',SimpleNamespace(root=str(r),project_id=None,pipeline_id=None,provider=None,job_id=None),{})
   saved=json.loads((r/'provision.json').read_text())
   self.assertEqual(saved['state'],'failed'); self.assertEqual(saved['error']['code'],'PREREQUISITE_MISSING'); self.assertEqual(st['state'],'failed')

class ProvisionStatusOwnershipTests(unittest.TestCase):
 def args(self,r):
  from types import SimpleNamespace
  return SimpleNamespace(root=str(r),project_id=None,pipeline_id=None,provider=None,job_id=None)
 def test_parent_never_writes_after_spawning_so_a_late_worker_result_survives(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d)/'state'; r.mkdir(); statusp=r/'provision.json'
   real_readj=om.readj
   class Popen:
    def __init__(self,*a,**k): self.pid=os.getpid()
   def worker_finishes_during_parent_read(path,default=None):
    # The worker's final write lands while the parent is still inside the handler after Popen.
    if Path(path)==statusp and json.loads(statusp.read_text()).get('state')=='running':
     statusp.write_text(json.dumps({"state":"failed","error":{"code":"PREREQUISITE_MISSING","message":"git is required"},"pid":None}))
    return real_readj(path,default)
   with mock.patch.object(om.subprocess,'Popen',Popen):
    real_atomic=om.atomic; writes=[]
    def arm_after_first_write(path,data):
     writes.append(dict(data)); real_atomic(path,data); om.readj=worker_finishes_during_parent_read
    with mock.patch.object(om,'atomic',arm_after_first_write):
     try: st,_=om.handler('install.provision',self.args(r),{})
     finally: om.readj=real_readj
   saved=json.loads(statusp.read_text())
   self.assertEqual(saved['state'],'failed'); self.assertEqual(saved['error']['code'],'PREREQUISITE_MISSING'); self.assertEqual(st['pid'],os.getpid())
   # Only the pre-spawn record is written by the parent; any later write could clobber a result landing between read and write.
   self.assertEqual(len(writes),1); self.assertIsNone(writes[0]['pid'])
 def test_a_failed_spawn_is_recorded_and_a_retry_starts_immediately(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d)/'state'; r.mkdir()
   with mock.patch.object(om.subprocess,'Popen',side_effect=OSError(11,'Resource temporarily unavailable')):
    with self.assertRaises(om.E) as e: om.handler('install.provision',self.args(r),{})
   self.assertEqual(e.exception.code,'SPAWN_FAILED')
   saved=json.loads((r/'provision.json').read_text()); self.assertEqual(saved['state'],'failed'); self.assertIn('Resource temporarily unavailable',saved['error']['message'])
   spawned=[]
   class Popen:
    def __init__(self,*a,**k): spawned.append(a); self.pid=os.getpid()
   with mock.patch.object(om.subprocess,'Popen',Popen): st,_=om.handler('install.provision',self.args(r),{})
   self.assertEqual(len(spawned),1); self.assertEqual(st['state'],'running')
 def test_a_just_started_record_without_pid_blocks_a_second_start(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d)/'state'; r.mkdir(); (r/'provision.json').write_text(json.dumps({"state":"running","pid":None,"startedAt":om.now()}))
   with mock.patch.object(om.subprocess,'Popen',side_effect=AssertionError('must not spawn')):
    st,w=om.handler('install.provision',self.args(r),{})
   self.assertEqual(st['state'],'running'); self.assertIn('already running',w[0])
 def test_a_stale_record_without_pid_is_reported_as_a_dead_worker(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d)/'state'; r.mkdir()
   old=(om.dt.datetime.now(om.dt.timezone.utc)-om.dt.timedelta(minutes=5)).isoformat()
   (r/'provision.json').write_text(json.dumps({"state":"running","pid":None,"startedAt":old}))
   st,_=om.handler('install.inspect',self.args(r),{})
   self.assertEqual(st['provision']['state'],'failed'); self.assertEqual(st['provision']['error']['code'],'WORKER_DIED')
   (r/'provision.json').write_text(json.dumps({"state":"running","pid":None,"startedAt":om.now()}))
   st,_=om.handler('install.inspect',self.args(r),{}); self.assertEqual(st['provision']['state'],'running')

class ProvisionWorkerIdentityTests(unittest.TestCase):
 def test_worker_records_its_own_pid_before_any_step(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d)/'state'; r.mkdir(); (r/'provision.json').write_text(json.dumps({"state":"running","pid":None}))
   seen={}
   def fake_provision(root,source,statusp):
    seen.update(json.loads(statusp.read_text())); raise om.E("PREREQUISITE_MISSING","git is required")
   with mock.patch.object(om,'provision_runtime',fake_provision):
    self.assertEqual(om.provision_worker(r,'https://example.invalid/repo'),1)
   self.assertEqual(seen['pid'],os.getpid()); self.assertEqual(seen['state'],'running')
   final=json.loads((r/'provision.json').read_text()); self.assertEqual(final['state'],'failed'); self.assertEqual(final['error']['code'],'PREREQUISITE_MISSING')

class LockParsingTests(unittest.TestCase):
 def test_locked_pins_exclude_installer_tooling_and_digest_is_deterministic(self):
  pins=om.locked_python_pins(); self.assertGreater(len(pins),10); self.assertFalse(om.INSTALLER_DISTRIBUTIONS & set(pins))
  self.assertEqual(om.environment_digest(pins),om.environment_digest(dict(reversed(list(pins.items())))))
  self.assertNotIn('pip',om.installed_python_distributions(Path(sys.executable)) or {})
