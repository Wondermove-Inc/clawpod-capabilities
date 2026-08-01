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
 cp=smb.run(['tool'],secret='secret')
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

def test_validation_traversal_and_mount_conflict(monkeypatch,tmp_path):
 with pytest.raises(smb.Fault): smb.valid_server('nas/x')
 with pytest.raises(smb.Fault): smb.relpath('../secret')
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); monkeypatch.setattr(smb,'mount_record',lambda:{'fstype':'tmpfs','source':'tmpfs'})
 with pytest.raises(smb.Fault) as e:smb.mount_apply(args(server='nas',share='x',account='u'))
 assert e.value.code=='MOUNT_CONFLICT'

def test_mount_command_secret_not_argv(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); monkeypatch.setattr(smb,'mount_record',lambda:None); monkeypatch.setattr(smb,'mounted',lambda:{'fstype':'cifs','source':'//nas/team'}); monkeypatch.setenv('SYNOLOGY_SMB_PASSWORD','secret'); seen={}
 def fake(argv,**kw): seen.update(argv=argv,kw=kw); return SimpleNamespace(returncode=0)
 monkeypatch.setattr(smb,'run',fake); smb.mount_apply(args(server='nas',share='team',account='u'))
 assert 'secret' not in seen['argv']; assert seen['kw']['secret']=='secret'; assert 'vers=3.1.1' in seen['argv'][-1]

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

def test_file_bounds_transfer_root_symlink_and_list(monkeypatch,tmp_path):
 root=tmp_path/'shared'; root.mkdir(); transfer=tmp_path/'transfer'; transfer.mkdir(); (transfer/'src').write_bytes(b'abc')
 monkeypatch.setattr(smb,'ROOT',root); monkeypatch.setattr(smb,'mounted',lambda:'mount')
 put=args(path='org/a.txt',transfer_root=str(transfer),source='src',overwrite=False,max_bytes=3)
 assert smb.fileop(put,'put')['bytes']==3
 assert smb.fileop(args(path='org/a.txt',max_bytes=3),'get')['contentBase64']=='YWJj'
 with pytest.raises(smb.Fault): smb.fileop(args(path='org/a.txt',max_bytes=2),'get')
 outside=tmp_path/'outside'; outside.write_bytes(b'x'); (transfer/'link').symlink_to(outside)
 with pytest.raises(smb.Fault): smb.fileop(args(path='x',transfer_root=str(transfer),source='link',overwrite=False,max_bytes=10),'put')
 (root/'escape').symlink_to(outside)
 listing=smb.fileop(args(path='.',max_bytes=None),'list'); assert {'name':'escape','type':'symlink','size':None} in listing['entries']
 with pytest.raises(smb.Fault): smb.fileop(args(path='escape',max_bytes=10),'get')

def test_preflight_contract(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); d=smb.preflight()
 assert d['protocol']['dialect']=='SMB3.1.1'; assert 'capSysAdmin' in d['privilege']; assert 'conflict' in d['mountRoot']

def test_manifest_safety_and_transfer_contracts():
 h=json.loads((HERE/'harness.json').read_text())['commands']; cc=json.loads((HERE/'command_contracts.json').read_text())
 expected={'shares.discover':['readOnly','secretUse'],'mount.apply':['secretUse','writeSafe'],'auth.onboard':['secretUse','writeSafe','externalSideEffect'],'layout.ensure':['externalSideEffect','writeSafe'],'file.put':['externalSideEffect','writeSafe'],'mount.unmount':['writeSafe'],'workflow.install':['writeSafe'],'workflow.rollback':['writeSafe']}
 for name,classes in expected.items(): assert h[name]['safetyClasses']==classes and cc[name]['safetyClasses']==classes
 assert 'transferRoot' in h['file.put']['inputSchema']['required']; assert h['file.get']['inputSchema']['properties']['maxBytes']['maximum']==smb.HARD_MAX_BYTES

def test_installed_cli_subprocess_json():
 cp=subprocess.run([sys.executable,str(SCRIPT),'auth.contract'],text=True,capture_output=True,check=True); d=json.loads(cp.stdout)
 assert d['ok'] and d['data']['backendPasswordTransport']=='PASSWD environment only'
 bad=subprocess.run([sys.executable,str(SCRIPT),'mount.preview','--server','bad/x'],text=True,capture_output=True); assert json.loads(bad.stdout)['error']['code']=='INVALID_INPUT'
