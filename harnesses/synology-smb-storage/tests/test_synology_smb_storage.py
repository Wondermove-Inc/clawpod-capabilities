import importlib.util, json, os, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
import pytest

HERE=Path(__file__).parents[1]; SCRIPT=HERE/'synology_smb_storage.py'
spec=importlib.util.spec_from_file_location('smb',SCRIPT); smb=importlib.util.module_from_spec(spec); spec.loader.exec_module(smb)

def args(**kw): return SimpleNamespace(**kw)

def test_preview_enforces_smb3_and_safe_options():
 d=smb.preview(args(server='nas.local',share='team',account='user'))
 assert d['target']=='/workspace/shared'; assert d['options']==['vers=3.0','nosuid','nodev','noexec','cache=strict']

def test_validation_and_traversal():
 with pytest.raises(smb.Fault): smb.valid_server('nas/x')
 with pytest.raises(smb.Fault): smb.valid_name('../x','share')
 with pytest.raises(smb.Fault): smb.relpath('../secret')

def test_discovery_unique_and_ambiguous(monkeypatch):
 monkeypatch.setenv('SYNOLOGY_SMB_PASSWORD','secret')
 monkeypatch.setattr(smb,'smb',lambda *x,**k: SimpleNamespace(returncode=0,stdout='Disk|one|x\n'))
 assert smb.discover(args(server='nas',account='u'))['selectedShare']=='one'
 monkeypatch.setattr(smb,'smb',lambda *x,**k: SimpleNamespace(returncode=0,stdout='Disk|one|x\nDisk|two|x\n'))
 assert smb.discover(args(server='nas',account='u'))['ambiguous'] is True

def test_bad_credentials_redacted(monkeypatch):
 monkeypatch.setenv('SYNOLOGY_SMB_PASSWORD','top-secret')
 monkeypatch.setattr(smb,'smb',lambda *x,**k: SimpleNamespace(returncode=1,stdout='',stderr='top-secret'))
 with pytest.raises(smb.Fault) as e: smb.discover(args(server='nas',account='u'))
 assert 'top-secret' not in str(e.value.msg)+str(e.value.details)

def test_mount_command_fixed_and_password_not_argv(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); monkeypatch.setattr(smb,'mounted',lambda:None); monkeypatch.setenv('SYNOLOGY_SMB_PASSWORD','secret')
 seen={}
 def fake(argv,**kw): seen.update(argv=argv,kw=kw); return SimpleNamespace(returncode=0)
 monkeypatch.setattr(smb,'run',fake)
 smb.mount_apply(args(server='nas',share='team',account='u'))
 assert 'secret' not in ' '.join(seen['argv']); assert seen['kw']['secret']=='secret'; assert 'vers=3.0' in seen['argv'][-1]

def test_backend_unavailable_and_mount_failure(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); monkeypatch.setattr(smb,'mounted',lambda:None); monkeypatch.setenv('SYNOLOGY_SMB_PASSWORD','secret')
 real_run=smb.run
 monkeypatch.setattr(smb,'run',lambda *a,**k: SimpleNamespace(returncode=32))
 with pytest.raises(smb.Fault) as e:smb.mount_apply(args(server='nas',share='x',account='u'))
 assert e.value.code=='MOUNT_FAILED' and e.value.details['retrySafe'] is True
 monkeypatch.setattr(smb,'run',real_run)
 monkeypatch.setattr(subprocess,'run',lambda *a,**k: (_ for _ in ()).throw(FileNotFoundError(2,'missing')))
 with pytest.raises(smb.Fault) as e:smb.run(['missing'])
 assert e.value.code=='BACKEND_UNAVAILABLE'

def test_existing_mount_and_nonempty_conflict(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); monkeypatch.setattr(smb,'mounted',lambda:'mount')
 with pytest.raises(smb.Fault) as e:smb.mount_apply(args(server='nas',share='x',account='u'))
 assert e.value.code=='MOUNT_CONFLICT'

def test_layout_permission_denial(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path/'shared'); monkeypatch.setattr(smb,'mounted',lambda:'mount')
 monkeypatch.setattr(Path,'mkdir',lambda *a,**k: (_ for _ in ()).throw(PermissionError()))
 with pytest.raises(PermissionError): smb.layout(args(org_id='org',agent_id='agent'),True)

def test_workflow_lifecycle_preserves_unrelated_and_agents(tmp_path):
 wf=tmp_path/'WORKFLOW.md'; ag=tmp_path/'AGENTS.md'; wf.write_bytes(b'prefix\n'); ag.write_bytes(b'untouched')
 a=args(workflow=str(wf)); smb.workflow(a); out=wf.read_bytes(); assert out.startswith(b'prefix\n'); assert smb.BEGIN.encode() in out; assert ag.read_bytes()==b'untouched'
 smb.workflow(a,True); assert wf.read_bytes()==b'prefix\n'

def test_workflow_replaces_block_and_malformed_fails_closed(tmp_path):
 wf=tmp_path/'WORKFLOW.md'; original=b'A\n'+smb.BEGIN.encode()+b'\nold\n'+smb.END.encode()+b'\nZ\n'; wf.write_bytes(original)
 smb.workflow(args(workflow=str(wf))); assert wf.read_bytes().startswith(b'A\n'); assert wf.read_bytes().endswith(b'\nZ\n')
 bad=b'x\n<!-- BEGIN SYNOLOGY SMB STORAGE POLICY v0.1.0 -->\n'; wf.write_bytes(bad)
 with pytest.raises(smb.Fault): smb.workflow(args(workflow=str(wf)))
 assert wf.read_bytes()==bad

def test_file_ops_and_traversal(monkeypatch,tmp_path):
 monkeypatch.setattr(smb,'ROOT',tmp_path); monkeypatch.setattr(smb,'mounted',lambda:'mount'); src=tmp_path.parent/'src'; src.write_bytes(b'abc')
 d=smb.fileop(args(path='org/a.txt',source=str(src),overwrite=False),'put'); assert d['bytes']==3
 assert smb.fileop(args(path='org/a.txt'),'get')['contentBase64']=='YWJj'
 with pytest.raises(smb.Fault): smb.fileop(args(path='../bad'),'list')

def test_installed_cli_subprocess_json():
 cp=subprocess.run([sys.executable,str(SCRIPT),'auth.contract'],text=True,capture_output=True,check=True)
 d=json.loads(cp.stdout); assert d['ok']; assert d['data']['passwordPersisted'] is False
 assert 'password' not in cp.stderr.lower()
 bad=subprocess.run([sys.executable,str(SCRIPT),'mount.preview','--server','bad/x'],text=True,capture_output=True)
 assert json.loads(bad.stdout)['error']['code']=='INVALID_INPUT'
