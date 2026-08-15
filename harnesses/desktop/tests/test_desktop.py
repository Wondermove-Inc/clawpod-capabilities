import json, os, pathlib, subprocess, tempfile
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
