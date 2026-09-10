"""F1 regression: real wrapper and human_input.press_key, final subprocess mocked.
Run with the deny-I/O runner as well as the regular source-only suite.
"""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import pytest

SPEC=importlib.util.spec_from_file_location('guard_binding_fixture',Path(__file__).with_name('test_return_focus_guard.py'))
F=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(F)
D=F.D

def invoke(world,inp,display,command='keyboard.key',dry=False):
    world.active_reads=0
    argv=['desktop',command,'--input',json.dumps(inp),'--idempotency-key','binding-test']
    if dry:argv+=['--dry-run']
    out=io.StringIO()
    env={'DESKTOP_DISPOSABLE_DISPLAY':'0','DESKTOP_SYSTEM_CLI':str(Path(D.__file__).parent/'engine'/'desktop')}
    with patch.dict(os.environ,env),patch.object(sys,'argv',argv),patch.object(D.subprocess,'run',world.run),patch.object(D.shutil,'which',lambda tool:tool),patch.object(D.time,'monotonic',lambda:world.clock),contextlib.redirect_stdout(out):
        if display is None:os.environ.pop('DISPLAY',None)
        else:os.environ['DISPLAY']=display
        code=D.main()
        assert os.environ.get('DISPLAY')==display  # No silent environment repair.
    return code,json.loads(out.getvalue())

@pytest.mark.parametrize('display',[None,'',':77',':99.0','localhost:99','unix:99',':099'])
@pytest.mark.parametrize('operation',['prepare','plain','capture'])
@pytest.mark.parametrize('dry',[False,True])
def test_unsupported_display_rejected_before_any_backend_io(display,operation,dry):
    world=F.Fixture();inp=world.prepared(operation=='capture')
    if operation=='prepare':inp={'target':copy.deepcopy(F.TARGET),'prepareFocusGuard':True}
    before=len(world.calls)
    code,out=invoke(world,inp,display,'ui.observe' if operation=='prepare' else 'keyboard.key',dry)
    assert code==25 and out['error']['code']=='FOCUS_GUARD_DISPLAY_UNSUPPORTED'
    assert len(world.calls)==before and world.keys==0

@pytest.mark.parametrize('capture',[False,True])
def test_foreign_guard_snapshot_duplicate_id_rejected_on_supported_display(capture):
    world=F.Fixture();inp=world.prepared(capture)
    # Same numeric window ID/PID/target digest as :99, but claims a :77 observation.
    inp['focusGuard']['observation']['display']['display']=':77'
    before=len(world.calls)
    code,out=invoke(world,inp,':99')
    assert code==25 and out['error']['code']=='FOCUS_GUARD_DISPLAY_UNSUPPORTED'
    assert len(world.calls)==before and world.keys==0

@pytest.mark.parametrize('display',[':99',':77'])
@pytest.mark.parametrize('capture',[False,True])
def test_real_key_function_environment_matches_guard_or_no_dispatch(display,capture):
    world=F.Fixture();inp=world.prepared(capture)
    path=Path(D.__file__).parent/'engine'/'lib'/'human_input.py'
    spec=importlib.util.spec_from_file_location('real_human_input_binding',path)
    human=importlib.util.module_from_spec(spec)
    with patch.dict(os.environ,{'DISPLAY':display,'DESKTOP_FAST_INPUT':'1'}):spec.loader.exec_module(human)
    original=world.run;delivered=[];reads=[]
    def nested(argv,**kwargs):
        if argv[0]=='xdotool':reads.append(kwargs['env']['DISPLAY'])
        result=original(argv,**kwargs)
        if argv[-2:]==['key','Return']:
            def sink(args,**kw):
                delivered.append((args,kw['env']['DISPLAY']))
                return subprocess.CompletedProcess(args,0,'','')
            with patch.object(human.subprocess,'run',sink),patch.dict(os.environ,{'DESKTOP_FAST_INPUT':'1'}):human.press_key('Return')
        return result
    world.run=nested;before=len(world.calls)
    code,out=invoke(world,inp,display)
    if display==':99':
        assert code==0 and world.keys==1 and set(reads)=={':99'}
        assert delivered==[(['xdotool','key','--clearmodifiers','Return'],':99')]
    else:
        assert code==25 and world.keys==0 and len(world.calls)==before and delivered==[] and reads==[]

@pytest.mark.parametrize('display',[None,':77',':99.0'])
def test_legacy_unguarded_return_is_not_silently_converted_to_guard(display):
    world=F.Fixture()
    # Legacy backend behavior is deliberately unchanged, not recommended safe.
    with patch.object(D,'display_metrics',return_value=F.DISPLAY):
        code,out=invoke(world,{'args':['Return']},display)
    assert code==0 and world.keys==1
    assert not any(len(a)>1 and a[1] in ('observe','getactivewindow') for a in world.calls)

def test_runtime_snapshot_other_display_fails_even_with_supported_environment():
    world=F.Fixture();inp=world.prepared()
    with patch.object(D,'display_metrics',return_value={**F.DISPLAY,'display':':77'}):
        code,out=invoke(world,inp,':99')
    assert code==25 and out['error']['code']=='FOCUS_GUARD_DISPLAY_UNSUPPORTED' and world.keys==0
