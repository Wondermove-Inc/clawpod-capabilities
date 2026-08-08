import importlib.util, json, os, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
import pytest

HERE=Path(__file__).parents[1]; SCRIPT=HERE/'synology_smb_storage.py'
spec=importlib.util.spec_from_file_location('smb',SCRIPT); smb=importlib.util.module_from_spec(spec); spec.loader.exec_module(smb)
def args(**kw): return SimpleNamespace(**kw)

def test_preview_enforces_exact_smb311():
 d=smb.preview(args(server='nas.local',share='team',account='user'))
 assert d['options']==['vers=3.1.1','nosuid','nodev','noexec','cache=strict']
 assert smb.SMBCLIENT_PROTOCOL==('--option=client min protocol=SMB3_11','--option=client max protocol=SMB3_11')

def test_backend_secret_passwd_only_and_redacted(monkeypatch):
 monkeypatch.setenv('SYNOLOGY_SMB_PASSWORD','secret')
 seen={}
 def fake(argv,**kw):
  seen.update(argv=argv,kw=kw); return SimpleNamespace(args=argv,returncode=1,stdout='secret',stderr='secret')
 monkeypatch.setattr(subprocess,'run',fake)
 cp=smb.run(['tool'],credential='secret')
 assert seen['kw']['stdin'] is subprocess.DEVNULL and seen['kw']['env']['PASSWD']=='secret'
 assert 'SYNOLOGY_SMB_PASSWORD' not in seen['kw']['env'] and 'secret' not in seen['argv']
 assert cp.stdout==cp.stderr==''

def test_discovery_unique_ambiguous_protocol_and_no_password_stdin_flag(monkeypatch):
 monkeypatch.setenv('SYNOLOGY_SMB_PASSWORD','secret'); calls=[]
 def fake(argv,**kw): calls.append((argv,kw)); return SimpleNamespace(returncode=0,stdout='Disk|one|x\n',stderr='')
 monkeypatch.setattr(subprocess,'run',fake)
 assert smb.discover(args(server='nas',account='u'))['selectedShare']=='one'
 argv,kw=calls[-1]; assert '--password-stdin' not in argv and all(x in argv for x in smb.SMBCLIENT_PROTOCOL); assert kw['stdin'] is subprocess.DEVNULL
 monkeypatch.setattr(subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout='Disk|one|x\nDisk|two|x\n',stderr=''))
 assert smb.discover(args(server='nas',account='u'))['ambiguous'] is True

def test_bad_credentials_and_backend_output_redacted(monkeypatch):
 monkeypatch.setenv('SYNOLOGY_SMB_PASSWORD','top-secret')
 monkeypatch.setattr(subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=1,stdout='top-secret',stderr='top-secret'))
 with pytest.raises(smb.Fault) as e:smb.discover(args(server='nas',account='u'))
 assert 'top-secret' not in e.value.msg+str(e.value.details)

def test_backend_failure_and_reflected_secret_not_returned(monkeypatch):
 monkeypatch.setenv('SYNOLOGY_SMB_PASSWORD','secret')
 monkeypatch.setattr(subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout='Disk|secret|x\nDisk|safe|x\n',stderr=''))
 d=smb.discover(args(server='nas',account='u')); assert d['shares']==['safe'] and 'secret' not in json.dumps(d)
 monkeypatch.setattr(subprocess,'run',lambda *a,**k: (_ for _ in ()).throw(FileNotFoundError(2,'missing')))
 with pytest.raises(smb.Fault) as e:smb.discover(args(server='nas',account='u'))
 assert e.value.code=='BACKEND_UNAVAILABLE'

def test_validation_and_mount_conflict(monkeypatch,tmp_path):
 with pytest.raises(smb.Fault): smb.valid_server('nas/x')
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); monkeypatch.setattr(smb,'mount_record',lambda:{'fstype':'tmpfs','source':'tmpfs'})
 with pytest.raises(smb.Fault) as e:smb.mount_apply(args(server='nas',share='x',account='u'))
 assert e.value.code=='MOUNT_CONFLICT'

def test_mount_command_secret_not_argv(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); monkeypatch.setattr(smb,'mount_record',lambda:None); monkeypatch.setattr(smb,'mounted',lambda:{'fstype':'cifs','source':'//nas/team'}); monkeypatch.setenv('SYNOLOGY_SMB_PASSWORD','secret'); seen={}
 def fake(argv,**kw): seen.update(argv=argv,kw=kw); return SimpleNamespace(returncode=0)
 monkeypatch.setattr(smb,'run',fake); smb.mount_apply(args(server='nas',share='team',account='u'))
 assert 'secret' not in seen['argv']; assert seen['kw']['credential']=='secret'; assert 'vers=3.1.1' in seen['argv'][-1]

def test_mount_backend_failure(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); monkeypatch.setattr(smb,'mount_record',lambda:None); monkeypatch.setattr(smb,'mounted',lambda:None); monkeypatch.setenv('SYNOLOGY_SMB_PASSWORD','secret')
 monkeypatch.setattr(smb,'run',lambda *a,**k:SimpleNamespace(returncode=32))
 with pytest.raises(smb.Fault) as e:smb.mount_apply(args(server='nas',share='team',account='u'))
 assert e.value.code=='MOUNT_FAILED' and e.value.details['retrySafe']

def test_mount_success_requires_source_verification(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); monkeypatch.setattr(smb,'mount_record',lambda:None); monkeypatch.setattr(smb,'mounted',lambda:None); monkeypatch.setenv('SYNOLOGY_SMB_PASSWORD','secret')
 monkeypatch.setattr(smb,'run',lambda *a,**k:SimpleNamespace(returncode=0))
 with pytest.raises(smb.Fault) as e:smb.mount_apply(args(server='nas',share='team',account='u'))
 assert e.value.code=='MOUNT_VERIFY_FAILED' and not e.value.details['retrySafe']

def restore_args(): return args(server='nas.local',share='team',account='user')

def restore_ready(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared')
 monkeypatch.setattr(smb.shutil,'which',lambda name:'/sbin/mount.cifs' if name=='mount.cifs' else None)
 monkeypatch.setattr(smb.os,'geteuid',lambda:0)

def test_restore_success_and_fixed_contract(monkeypatch,tmp_path):
 restore_ready(monkeypatch,tmp_path); monkeypatch.setenv(smb.PASSWORD_ENV,'secret'); records=[None,{'fstype':'cifs','source':'//nas.local/team'}]; seen={}
 monkeypatch.setattr(smb,'mount_record',lambda:records.pop(0))
 def fake(argv,**kw): seen.update(argv=argv,kw=kw); return SimpleNamespace(returncode=0)
 monkeypatch.setattr(smb,'run',fake)
 d=smb.mount_restore(restore_args())
 assert d['mounted'] and d['changed'] and d['secretUsed'] and d['externalSideEffect']
 assert d['source']=='//nas.local/team' and d['target']==str(tmp_path/'shared')
 assert seen['kw']['credential']=='secret' and 'secret' not in seen['argv']
 assert seen['argv'][-1]=='vers=3.1.1,nosuid,nodev,noexec,cache=strict,username=user'

def test_restore_already_mounted_noop_without_secret(monkeypatch,tmp_path):
 restore_ready(monkeypatch,tmp_path); monkeypatch.delenv(smb.PASSWORD_ENV,raising=False)
 monkeypatch.setattr(smb,'mount_record',lambda:{'fstype':'cifs','source':'//nas.local/team'})
 monkeypatch.setattr(smb,'run',lambda *a,**k:pytest.fail('backend must not run'))
 d=smb.mount_restore(restore_args())
 assert d['mounted'] and not d['changed'] and not d['secretUsed'] and not d['externalSideEffect']

def test_restore_missing_secret_and_conflicts(monkeypatch,tmp_path):
 restore_ready(monkeypatch,tmp_path); monkeypatch.delenv(smb.PASSWORD_ENV,raising=False); monkeypatch.setattr(smb,'mount_record',lambda:None)
 with pytest.raises(smb.Fault) as e:smb.mount_restore(restore_args())
 assert e.value.code=='AUTH_REQUIRED'
 monkeypatch.setattr(smb,'mount_record',lambda:{'fstype':'cifs','source':'//other/share'})
 with pytest.raises(smb.Fault) as e:smb.mount_restore(restore_args())
 assert e.value.code=='MOUNT_CONFLICT'
 monkeypatch.setattr(smb,'mount_record',lambda:None); smb.ROOT.mkdir(); (smb.ROOT/'local').write_text('x')
 with pytest.raises(smb.Fault) as e:smb.mount_restore(restore_args())
 assert e.value.code=='MOUNT_CONFLICT'

@pytest.mark.parametrize('values',[
 {'server':'bad/server','share':'team','account':'user'},
 {'server':'nas.local','share':'bad/share','account':'user'},
 {'server':'nas.local','share':'team','account':'bad account'},
])
def test_restore_rejects_malformed_identifiers(monkeypatch,tmp_path,values):
 restore_ready(monkeypatch,tmp_path); monkeypatch.setenv(smb.PASSWORD_ENV,'secret')
 monkeypatch.setattr(smb,'run',lambda *a,**k:pytest.fail('backend must not run'))
 with pytest.raises(smb.Fault) as e:smb.mount_restore(args(**values))
 assert e.value.code=='INVALID_INPUT'

def test_restore_backend_and_verification_failures(monkeypatch,tmp_path):
 restore_ready(monkeypatch,tmp_path); monkeypatch.setenv(smb.PASSWORD_ENV,'secret'); monkeypatch.setattr(smb,'mount_record',lambda:None)
 monkeypatch.setattr(smb,'run',lambda *a,**k:SimpleNamespace(returncode=32))
 with pytest.raises(smb.Fault) as e:smb.mount_restore(restore_args())
 assert e.value.code=='MOUNT_FAILED'
 monkeypatch.setattr(smb,'run',lambda *a,**k:SimpleNamespace(returncode=0))
 with pytest.raises(smb.Fault) as e:smb.mount_restore(restore_args())
 assert e.value.code=='MOUNT_VERIFY_FAILED'

def test_restore_repeated_invocation_and_secret_redaction(monkeypatch,tmp_path,capsys):
 restore_ready(monkeypatch,tmp_path); secret='never-print-this'; monkeypatch.setenv(smb.PASSWORD_ENV,secret); state={'record':None,'calls':0}
 monkeypatch.setattr(smb,'mount_record',lambda:state['record'])
 def fake(argv,**kw): state['calls']+=1; state['record']={'fstype':'cifs','source':'//nas.local/team'}; return SimpleNamespace(returncode=0)
 monkeypatch.setattr(smb,'run',fake)
 first=smb.mount_restore(restore_args()); second=smb.mount_restore(restore_args())
 assert first['changed'] and not second['changed'] and state['calls']==1
 smb.emit('mount.restore',second); assert secret not in capsys.readouterr().out

def test_layout_permission_denial(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); (tmp_path/'shared').mkdir(); monkeypatch.setattr(smb,'mounted',lambda:'mount')
 monkeypatch.setattr(Path,'mkdir',lambda *a,**k: (_ for _ in ()).throw(PermissionError()))
 with pytest.raises(PermissionError): smb.layout(args(org_id='org',agent_id='agent'),True)

def test_workflow_lifecycle_and_malformed(tmp_path):
 wf=tmp_path/'WORKFLOW.md'; ag=tmp_path/'AGENTS.md'; wf.write_bytes(b'prefix\n'); ag.write_bytes(b'untouched')
 a=args(workflow=str(wf)); smb.workflow(a); assert wf.read_bytes().startswith(b'prefix\n'); assert ag.read_bytes()==b'untouched'; smb.workflow(a,True); assert wf.read_bytes()==b'prefix\n'
 bad=b'x\n<!-- BEGIN SYNOLOGY SMB STORAGE POLICY v0.1.0 -->\n'; wf.write_bytes(bad)
 with pytest.raises(smb.Fault): smb.workflow(a)
 assert wf.read_bytes()==bad

def test_onboard_rolls_back_layout_workflow_and_new_mount(monkeypatch,tmp_path):
 root=tmp_path/'shared'; root.mkdir(); wf=tmp_path/'WORKFLOW.md'; wf.write_bytes(b'original\n'); monkeypatch.setattr(smb,'ROOT',root); state={'mounted':False,'unmounted':False}
 monkeypatch.setattr(smb,'discover',lambda a:{'shares':['one'],'selectedShare':'one','ambiguous':False})
 monkeypatch.setattr(smb,'mounted',lambda:'mount' if state['mounted'] else None)
 def apply(a): state['mounted']=True; return {'mounted':True}
 monkeypatch.setattr(smb,'mount_apply',apply)
 real_workflow=smb.workflow
 def fail_policy(a): real_workflow(a); raise smb.Fault('POLICY_FAIL','failed')
 monkeypatch.setattr(smb,'workflow',fail_policy)
 def undo(a): state['mounted']=False; state['unmounted']=True; return {'changed':True}
 monkeypatch.setattr(smb,'unmount',undo)
 a=args(server='nas',account='u',share=None,workflow=str(wf),org_id='org',agent_id='agent')
 with pytest.raises(smb.Fault) as e:smb.onboard(a)
 rb=e.value.details['rollback']; assert rb['complete'] and rb['workflowRestored'] and rb['backupRestored'] and rb['unmountedNewMount']; assert wf.read_bytes()==b'original\n'; assert not wf.with_suffix('.md.synology-smb-storage.bak').exists(); assert not (root/'org').exists()

def test_onboard_never_unmounts_preexisting(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); monkeypatch.setattr(smb,'discover',lambda a:{'shares':['one'],'selectedShare':'one'}); monkeypatch.setattr(smb,'mounted',lambda:'existing')
 called=[]; monkeypatch.setattr(smb,'unmount',lambda a:called.append(1))
 with pytest.raises(smb.Fault): smb.onboard(args(server='nas',account='u',share=None,workflow=str(tmp_path/'w'),org_id='o',agent_id='a'))
 assert called==[]

def test_preflight_contract(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); d=smb.preflight()
 assert d['protocol']['dialect']=='SMB3.1.1'; assert 'capSysAdmin' in d['privilege']; assert 'conflict' in d['mountRoot']

def test_manifest_safety_and_control_plane_contracts():
 h=json.loads((HERE/'harness.json').read_text())['commands']; cc=json.loads((HERE/'command_contracts.json').read_text())
 expected={'shares.discover':['readOnly','secretUse'],'mount.apply':['secretUse','writeSafe'],'mount.restore':['secretUse','externalSideEffect'],'auth.onboard':['secretUse','writeSafe','externalSideEffect'],'layout.ensure':['externalSideEffect','writeSafe'],'mount.unmount':['writeSafe'],'workflow.install':['writeSafe'],'workflow.rollback':['writeSafe']}
 for name,classes in expected.items(): assert h[name]['safetyClasses']==classes and cc[name]['safetyClasses']==classes
 assert len(h)==13 and len([name for name in cc if name!='directCredentialSecretBinding'])==13

def test_file_commands_absent_from_manifest_contracts_parser_and_discovery():
 removed={'file.list','file.get','file.put'}
 manifest=json.loads((HERE/'harness.json').read_text())
 contracts=json.loads((HERE/'command_contracts.json').read_text())
 assert removed.isdisjoint(manifest['commands'])
 assert removed.isdisjoint(contracts)
 choices=smb.parser()._subparsers._group_actions[0].choices
 assert removed.isdisjoint(choices)
 help_result=subprocess.run([sys.executable,str(SCRIPT),'--help'],text=True,capture_output=True,check=True)
 assert all(command not in help_result.stdout for command in removed)

def test_skill_requires_exact_mount_verification_os_commands_approval_and_destructive_caution():
 skill=(HERE.parents[1]/'skills'/'synology-smb-storage'/'SKILL.md').read_text()
 assert '/workspace/shared' in skill and 'filesystem type must be `cifs`' in skill
 assert 'source must equal the approved `//<server>/<share>`' in skill
 assert 'OS filesystem commands' in skill and 'Harness has no file copy, move, read, write, or list commands' in skill
 assert 'Obtain approval' in skill and 'destructive' in skill
 assert all(command not in skill for command in ('file.list','file.get','file.put'))

def test_manifest_input_schemas_use_gateway_supported_keywords():
 supported={'type'}
 for filename in ('harness.json','command_contracts.json'):
  document=json.loads((HERE/filename).read_text()); commands=document.get('commands',document)
  for command_name,command in commands.items():
   if command_name=='directCredentialSecretBinding': continue
   for argument_name,schema in command['inputSchema'].get('properties',{}).items():
    assert set(schema)<=supported,f'{filename}: {command_name}.{argument_name}'

def test_installed_cli_subprocess_json():
 cp=subprocess.run([sys.executable,str(SCRIPT),'auth.contract'],text=True,capture_output=True,check=True); d=json.loads(cp.stdout)
 assert d['ok'] and d['data']['backendPasswordTransport']=='PASSWD environment only'
 bad=subprocess.run([sys.executable,str(SCRIPT),'mount.preview','--server','bad/x'],text=True,capture_output=True); assert json.loads(bad.stdout)['error']['code']=='INVALID_INPUT'


def test_per_run_secretrefs_manifest_contract():
 import json
 from pathlib import Path
 root=Path(__file__).resolve()
 while not (root/'harnesses').exists(): root=root.parent
 manifest=json.loads((root/'harnesses/synology-smb-storage/harness.json').read_text())
 binding=json.loads((root/'harnesses/synology-smb-storage/command_contracts.json').read_text())['directCredentialSecretBinding']
 assert manifest['version']=='0.1.4' and 'credentialEnvironment' not in manifest
 assert binding['names']==['SYNOLOGY_SMB_PASSWORD'] and binding['parameter']=='secretRefs'
 assert binding['prepareRunMustMatch'] and not binding['manifestStoresPointer']
 assert json.loads((root/'skills/synology-smb-storage/capability.json').read_text())['linkedHarness']['version']=='0.1.4'
