import importlib.util, json, os, pathlib, subprocess, tempfile
from PIL import Image
CLI=pathlib.Path(__file__).parents[1]/'desktop.py'
METRICS=pathlib.Path(__file__).parent/'fixtures'/'xdpyinfo-static.sh'
def run(*args,env=None):
 base={'DISPLAY':':disposable-test','DESKTOP_METRICS_CLI':str(METRICS)}
 p=subprocess.run([str(CLI),*args],capture_output=True,text=True,env={**os.environ,**base,**(env or {})}); return p,json.loads(p.stdout)
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

def test_display_mutations_and_session_replacement_are_rejected_before_dispatch():
 with tempfile.TemporaryDirectory() as d:
  backend=pathlib.Path(d)/'desktop'; log=pathlib.Path(d)/'called'
  backend.write_text(f'#!/bin/sh\ntouch {log}\n'); backend.chmod(0o755)
  attempts=[
   {'args':['xrandr','--dpi','144']}, {'args':['xfconf-query','-p','/Xft/DPI','-s','144']},
   {'args':['xrdb','-merge','Xft.dpi: 144']}, {'args':['gsettings','set','org.gnome.desktop.interface','text-scaling-factor','1.5']},
   {'args':['Xvfb',':77','-screen','0','1280x720x24']}, {'resolution':'1280x720','dpi':96},
  ]
  for i,body in enumerate(attempts):
   p,o=run('app.launch','--input',json.dumps(body),'--idempotency-key',f'forbidden-{i}',env={'DESKTOP_SYSTEM_CLI':str(backend)})
   assert p.returncode==31 and o['error']['code'] in {'DISPLAY_MUTATION_FORBIDDEN','DESKTOP_SESSION_MUTATION_FORBIDDEN'}
  assert not log.exists()

def test_display_metric_drift_fails_closed():
 with tempfile.TemporaryDirectory() as d:
  root=pathlib.Path(d); count=root/'count'; metrics=root/'metrics'; backend=root/'desktop'
  metrics.write_text('#!/bin/sh\nn=0; [ -f "'+str(count)+'" ] && n=$(cat "'+str(count)+'"); n=$((n+1)); echo $n > "'+str(count)+'"\ndpi=96; [ "$n" -gt 1 ] && dpi=120\nprintf "  dimensions:    1920x1080 pixels (508x285 millimeters)\\n  resolution:    %sx%s dots per inch\\n" "$dpi" "$dpi"\n')
  metrics.chmod(0o755); backend.write_text('#!/bin/sh\necho "{}"\n'); backend.chmod(0o755)
  p,o=run('ui.observe',env={'DESKTOP_SYSTEM_CLI':str(backend),'DESKTOP_METRICS_CLI':str(metrics)})
  assert p.returncode==25 and o['error']['code']=='DESKTOP_STATE_CHANGED'
  assert o['error']['details']['before']['dpiX']==96 and o['error']['details']['after']['dpiX']==120

def test_session_lifecycle_discoverability_is_preserved_but_fails_closed_before_dispatch():
 contracts=json.loads((CLI.parent/'command_contracts.json').read_text())['commands']
 lifecycle={'session.open','session.recover','session.close'}
 assert lifecycle <= set(contracts) and len(contracts)==67
 assert {name:contracts[name]['safetyClass'] for name in lifecycle}=={'session.open':'S0','session.recover':'S0','session.close':'S2'}
 manifest=json.loads((CLI.parent/'harness.json').read_text())['commands']
 assert manifest['session.open']['safetyClasses']==manifest['session.recover']['safetyClasses']==['readOnly']
 assert manifest['session.close']['safetyClasses']==['writeSafe','humanAccountAction']
 with tempfile.TemporaryDirectory() as d:
  backend=pathlib.Path(d)/'desktop'; log=pathlib.Path(d)/'called'
  backend.write_text(f'#!/bin/sh\ntouch {log}\n'); backend.chmod(0o755)
  for command in lifecycle:
   p,o=run(command,'--input','{}',env={'DESKTOP_SYSTEM_CLI':str(backend)})
   assert p.returncode==31 and o['error']['code']=='SESSION_LIFECYCLE_FORBIDDEN'
   assert o['error']['details']=={'contract':'existing-session-only','command':command}
  assert not log.exists()

def test_session_display_mutation_collision_prefers_the_stronger_display_rule():
 p,o=run('session.open','--input','{"args":["xrandr","--dpi","144"]}')
 assert p.returncode==31 and o['error']['code']=='DISPLAY_MUTATION_FORBIDDEN'

def test_session_guard_does_not_collide_with_safe_app_close_contract():
 p,o=run('app.close','--input','{}','--idempotency-key','safe-app-close','--dry-run')
 assert p.returncode==0 and o['result']['wouldExecute'] is True

def test_engine_implements_all_advertised_commands():
 # Regression: every contract command that desktop.py delegates to the engine
 # must have an engine dispatch branch (v3.0.3 advertised ~20 unimplemented ->
 # "Unknown command"). Static parity check against the bundled engine source.
 import re
 engine_src=(CLI.parent/'engine'/'desktop').read_text()
 tokens=set(re.findall(r"'([a-z0-9-]+)'",engine_src))
 src=CLI.read_text()
 contracts=json.loads((CLI.parent/'command_contracts.json').read_text())['commands']
 OBS=set(re.search(r"OBS=set\('([^']+)'",src).group(1).split())
 # Only task.*/session.* are synthetic in desktop.py now; the former inspect/list
 # stubs (window.list, clipboard.inspect, ...) route to the engine as of 3.0.5.
 synth=set()
 special={'window.move'}  # desktop.py routes to xdotool directly
 MAP=dict(re.findall(r"'([^']+)':\['([^']+)'",re.search(r"MAP=\{(.*?)\}",src,re.S).group(1)))
 missing=[]
 for cmd in contracts:
  if cmd in OBS or cmd in synth or cmd in special or cmd.startswith(('task.','session.')): continue
  eng=MAP.get(cmd,cmd.replace('.','-'))
  if eng not in tokens: missing.append((cmd,eng))
 assert not missing, f"engine missing dispatch for: {missing}"

def test_portal_action_blocked_without_dbus():
 p,o=run('file-dialog.open','--idempotency-key','fd',env={'DBUS_SESSION_BUS_ADDRESS':''})
 assert p.returncode==22 and o['error']['code']=='DBUS_SESSION_UNAVAILABLE'

def test_engine_new_commands_not_unknown():
 # Direct engine dispatch: new commands must reach their handler, never the
 # generic "Unknown command" fall-through. Args omitted on purpose -> handler
 # emits its own usage/guard error.
 ENGINE=CLI.parent/'engine'/'desktop'
 for c in ('window-activate','window-resize','window-maximize','clipboard-clear',
           'process-kill','pointer-move','download-move','dialog-respond',
           'window-list','window-get','screen-list','app-get',
           'dialog-inspect','clipboard-inspect','download-inspect'):
  p=subprocess.run([str(ENGINE),c],capture_output=True,text=True,timeout=15)
  assert 'Unknown command' not in (p.stdout+p.stderr), f"{c} not dispatched"
