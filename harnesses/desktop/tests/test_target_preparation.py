import importlib.util
import json
import pathlib
import subprocess
import sys
import pytest

SPEC=importlib.util.spec_from_file_location('target_desktop',pathlib.Path(__file__).parents[1]/'desktop.py')
D=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(D)

@pytest.mark.parametrize('requested,window,expected', [('7','7',0), ('8','7',20)])
def test_observation_binds_expected_window_without_input(tmp_path,monkeypatch,capsys,requested,window,expected):
    root=tmp_path/'runs';root.mkdir()
    monkeypatch.setenv('DESKTOP_RUNS_ROOT',str(root))
    calls=[]
    observation={'windowId':window,'revision':3,'targetDigest':'fresh','focused':True}
    def call(argv,timeout):
        calls.append(argv)
        return subprocess.CompletedProcess(argv,0,json.dumps(observation),''),None
    monkeypatch.setattr(D,'backend_call',call)
    monkeypatch.setattr(sys,'argv',['desktop','ui.observe','--input',json.dumps({'target':{'kind':'accessibility','nodeId':'n1','windowId':requested}})])
    assert D.main()==expected
    out=json.loads(capsys.readouterr().out)
    assert len(calls)==1 and calls[0][1:3]==['observe','--json']
    if expected==0:
        assert out['result']['target']['targetDigest']=='fresh'
        assert out['result']['target']['observedRevision']==3
        assert out['result']['targetPreparationOnly'] is True
    else:
        assert out['error']['code']=='STALE_TARGET'

def test_ambiguous_accessibility_name_rejected(tmp_path,monkeypatch,capsys):
    root=tmp_path/'runs';root.mkdir();monkeypatch.setenv('DESKTOP_RUNS_ROOT',str(root))
    obs={'nodes':[{'id':'a','name':'Save'},{'id':'b','name':'Save'}]}
    monkeypatch.setattr(D,'backend_call',lambda a,t:(subprocess.CompletedProcess(a,0,json.dumps(obs),''),None))
    monkeypatch.setattr(sys,'argv',['desktop','ui.observe','--input',json.dumps({'target':{'kind':'accessibility','name':'Save'}})])
    assert D.main()==20
    assert json.loads(capsys.readouterr().out)['error']['code']=='TARGET_AMBIGUOUS'
