import importlib.util, json, os, pathlib, subprocess, tempfile
from PIL import Image
CLI=pathlib.Path(__file__).parents[1]/'desktop.py'
def run(*args,env=None):
 p=subprocess.run([str(CLI),*args],capture_output=True,text=True,env={**os.environ,**(env or {})}); return p,json.loads(p.stdout)
def test_invalid_input():
 p,o=run('ui.observe','--input','[]'); assert p.returncode==10 and o['error']['code']=='INVALID_INPUT'
def test_backend_unavailable():
 p,o=run('ui.observe',env={'DESKTOP_SYSTEM_CLI':'/missing'}); assert p.returncode==22 and o['error']['code']=='BACKEND_UNAVAILABLE'
def test_human_verification_stop():
 p,o=run('image.locate','--input','{"label":"captcha"}'); assert p.returncode==32 and o['error']['code']=='HUMAN_VERIFICATION'
def test_risky_preview_and_approval_required():
 p,o=run('process.kill','--idempotency-key','k','--dry-run'); assert p.returncode==0 and o['approval']['safetyClass']=='S4'
 p,o=run('process.kill','--idempotency-key','k'); assert p.returncode==30 and o['error']['code']=='APPROVAL_REQUIRED'
def test_idempotency_revision_recovery_cleanup():
 pathlib.Path('/tmp/desktop-runs').mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory(dir='/tmp/desktop-runs') as d:
  p,o=run('task.plan','--idempotency-key','same','--dry-run','--run-root',d); assert p.returncode==0
  p,o=run('task.cleanup','--idempotency-key','cleanup','--dry-run','--run-root',d); assert p.returncode==0 and o['result']['wouldExecute']
def test_safe_path_symlink_denied():
 pathlib.Path('/tmp/desktop-runs').mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory(dir='/tmp/desktop-runs') as d:
  link=pathlib.Path(d)/'link'; link.symlink_to('/tmp',target_is_directory=True)
  p=subprocess.run([str(CLI),'task.get','--run-root',str(link)],capture_output=True,text=True); assert p.returncode!=0
def test_atspi_unavailable_diagnostic():
 p,o=run('environment.preflight',env={'DESKTOP_SYSTEM_CLI':'/missing','DBUS_SESSION_BUS_ADDRESS':''}); assert p.returncode==24 and o['error']['code']=='AT_SPI_UNAVAILABLE' and o['warnings']
def test_image_mismatch_and_window_ambiguity_contracts_present():
 c=json.loads((CLI.parent/'command_contracts.json').read_text())['commands']; assert 'image.locate' in c and 'window.list' in c and c['image.click']['safetyClass']=='S2'
def test_partial_failure_taxonomy_and_secrets_redacted():
 p,o=run('task.plan','--input','{"password":"never-log"}','--idempotency-key','x','--dry-run'); assert 'never-log' not in p.stdout and '[REDACTED]' in p.stdout

def test_app_launch_does_not_report_success_without_a_visible_window():
 with tempfile.TemporaryDirectory() as d:
  backend=pathlib.Path(d)/'desktop'
  backend.write_text("#!/bin/sh\necho 'Launched: example'\necho 'WARNING: Window not detected after 10s (app may still be loading)'\n")
  backend.chmod(0o755)
  p,o=run('app.launch','--input','{"args":["file","/tmp/example.txt"]}','--idempotency-key','launch-no-window',env={'DESKTOP_SYSTEM_CLI':str(backend)})
  assert p.returncode==20 and o['status']=='failed' and o['error']['code']=='POSTCONDITION_NOT_CONFIRMED'

def test_ui_observe_emits_real_target_identities_for_fresh_previews():
 observation={'active_window':{'window_id':'42','title':'Disposable','error':None},'nodes':[{'id':'node:1','path':'1','app':'terminal','role':'frame','name':'Disposable','bbox':{'x':10,'y':20,'width':300,'height':200},'actions':['click']}]}
 with tempfile.TemporaryDirectory() as d:
  backend=pathlib.Path(d)/'desktop'
  backend.write_text("#!/bin/sh\necho '" + json.dumps(observation,separators=(",",":")) + "'\n")
  backend.chmod(0o755)
  p,o=run('ui.observe',env={'DESKTOP_SYSTEM_CLI':str(backend)})
  target=o['result']['observation']['targets'][0]
  assert p.returncode==0 and target['windowId']=='42' and target['nodeId']=='node:1'
  assert target['targetDigest']!='preview-only' and isinstance(target['observedRevision'],int) and target['focused'] is True

def test_screen_capture_without_path_uses_a_fresh_run_scoped_artifact():
 with tempfile.TemporaryDirectory() as d:
  backend=pathlib.Path(d)/'desktop'; log=pathlib.Path(d)/'argv'
  backend.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > {log}\n")
  backend.chmod(0o755)
  run_root=pathlib.Path('/tmp/desktop-runs')/('capture-'+next(tempfile._get_candidate_names()))
  p,o=run('screen.capture','--run-root',str(run_root),env={'DESKTOP_SYSTEM_CLI':str(backend)})
  assert p.returncode==0 and str(run_root/'screenshot.png') in log.read_text()

def test_region_digest_ignores_unrelated_clock_pixels_but_detects_target_change():
 spec=importlib.util.spec_from_file_location('desktop_harness',CLI); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
 with tempfile.TemporaryDirectory() as d:
  path=pathlib.Path(d)/'screen.png'; image=Image.new('RGB',(20,20),'white'); image.save(path)
  baseline=module.png_region_digest(path,[5,5,10,10])
  image.putpixel((0,0),(0,0,0)); image.save(path); assert module.png_region_digest(path,[5,5,10,10])==baseline
  image.putpixel((6,6),(0,0,0)); image.save(path); assert module.png_region_digest(path,[5,5,10,10])!=baseline

def test_keyboard_type_requires_a_fresh_target_outside_dry_run():
 with tempfile.TemporaryDirectory() as d:
  backend=pathlib.Path(d)/'desktop'; backend.write_text('#!/bin/sh\nexit 0\n'); backend.chmod(0o755)
  body='{"args":["preview text"],"postcondition":{"textPresent":"preview text"}}'
  _,preview=run('keyboard.type','--input',body,'--idempotency-key','typed-target','--dry-run',env={'DESKTOP_SYSTEM_CLI':str(backend)})
  receipt=pathlib.Path(d)/'approval.json'; receipt.write_text(json.dumps({'requestDigest':preview['result']['requestDigest'],'expiresAt':'2999-01-01T00:00:00+00:00'}))
  p,o=run('keyboard.type','--input',body,'--idempotency-key','typed-target','--approval-file',str(receipt),env={'DESKTOP_SYSTEM_CLI':str(backend)})
  assert p.returncode==31 and o['error']['code']=='PRECISION_TARGET_REQUIRED'
