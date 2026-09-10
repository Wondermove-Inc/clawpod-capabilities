"""Source-only mocks: no GUI calls or live harness lifecycle changes."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import pytest

SPEC=importlib.util.spec_from_file_location('call_reduction',Path(__file__).parents[1]/'desktop.py')
D=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(D)

def guard_input():
    return {'target':{'kind':'coordinate','windowId':'7','observedRevision':7,'targetDigest':'fresh','x':3,'y':4,'visualRegion':[0,0,10,10],'screenshotDigest':'region','monitor':0,'scale':1},'postcondition':{'activeWindowMatch':True,'windowBoundsUnchanged':True},'focusGuard':{'windowId':'7','pid':42,'observation':{'revision':7,'digest':'fresh','display':{'display':':99','width':100,'height':100,'dpiX':96,'dpiY':96}}}}

def invoke(inp,cmd='keyboard.key',mode='ok',key='same'):
    inp=dict(inp)
    if cmd=='keyboard.key' and inp.get('args')==['Return'] and inp.get('postCapture') is True:
        inp.update(guard_input())
    calls=[]
    def backend(argv,ms,**kwargs):
        calls.append((argv,ms))
        if argv[1]=='screenshot':
            if mode=='timeout':return None,'timeout'
            if mode=='unavailable':return None,'display_state_unavailable'
            if mode=='backend-missing':return None,{'code':'backend_unavailable'}
            if mode=='drift':return None,{'changed':True}
            if mode=='io':raise OSError('capture failed')
            if mode=='crash':raise RuntimeError('simulated process crash')
            if mode=='bad':Path(argv[-1]).write_bytes(b'not PNG')
            elif mode!='missing':
                from PIL import Image
                Image.new('RGB',(12,12),'white').save(argv[-1])
                if mode=='no-iend':Path(argv[-1]).write_bytes(Path(argv[-1]).read_bytes()[:-12])
            return subprocess.CompletedProcess(argv,0,'',''),None
        if mode=='dispatch-timeout':return None,'timeout'
        return subprocess.CompletedProcess(argv,0,json.dumps({'windows':[{'id':'1','name':'','width':10,'height':10,'x':0,'y':0},{'id':'2','name':'long'*1000,'token':'SYNTHETIC_PRIVATE_VALUE'}]}),''),None
    argv=['desktop',cmd,'--input',json.dumps(inp),'--idempotency-key',key]
    out=io.StringIO()
    baseline={'display':':99','width':100,'height':100,'dpiX':96,'dpiY':96}
    metrics=[baseline,{**baseline,'width':200}] if mode=='between-drift' else [baseline]*3
    with patch.dict(D.os.environ,{'DISPLAY':':99'}),patch.object(sys,'argv',argv),patch.object(D,'backend_call',backend),patch.object(D,'display_metrics',side_effect=metrics),patch.object(D,'guard_observe',return_value=({'windowId':'7','revision':7,'targetDigest':'fresh','focused':True},{})),patch.object(D.GuardBudget,'identity',return_value={}),patch.object(D.GuardBudget,'geometry',return_value={}),contextlib.redirect_stdout(out):code=D.main()
    return code,json.loads(out.getvalue()),calls

@pytest.mark.parametrize('mode',['ok','timeout','io','bad','missing','no-iend','backend-missing'])
def test_capture_result_never_repeats_return(mode):
    inp={'args':['Return'],'postCapture':True}
    code,value,calls=invoke(inp,mode=mode)
    assert code==0 and len(calls)==2 and calls[1][1]<=2000
    result=value['result']
    if mode=='ok':
        shot=Path(result['afterScreenshot']['path'])
        assert shot.stat().st_mode & 0o777==0o600
        assert shot.parent.stat().st_mode & 0o777==0o700
    assert result['postCapture']['actionDispatchConfirmed'] is True
    assert result['postCapture']['semanticOutcomeVerified'] is False
    assert result['postCapture']['status']==('captured' if mode=='ok' else 'failed')
    second=invoke(inp,mode=mode)
    assert second[0]==0 and second[2]==[] and second[1]['result']==result

@pytest.mark.parametrize('mode',['drift','dispatch-timeout','between-drift','unavailable'])
def test_uncertain_or_drift_no_replay(mode):
    inp={'args':['Return'],'postCapture':True}
    first=invoke(inp,mode=mode)
    assert first[0] in (25,40)
    second=invoke(inp)
    assert second[0]==40 and second[2]==[]

def test_capture_crash_preserves_unknown():
    inp={'args':['Return'],'postCapture':True}
    with pytest.raises(RuntimeError):invoke(inp,mode='crash')
    assert invoke(inp)[0]==40 and invoke(inp)[2]==[]

@pytest.mark.parametrize('cmd,inp',[('keyboard.key',{'args':['Tab'],'postCapture':True}),('keyboard.key',{'args':['Return'],'postCapture':1}),('keyboard.shortcut',{'args':['Return'],'postCapture':True}),('window.list',{'postCapture':False})])
def test_invalid_optin_fails_before_dispatch(cmd,inp):
    code,out,calls=invoke(inp,cmd=cmd)
    assert code==10 and not calls

def test_non_optin_unchanged():
    assert len(invoke({'args':['Return']})[2])==1

def test_capture_option_binds_idempotency():
    invoke({'args':['Return']})
    code,out,calls=invoke({'args':['Return'],'postCapture':True})
    assert code==41 and not calls

def test_compact_windows_preserves_unknown_and_long_names():
    code,out,calls=invoke({},cmd='window.list')
    assert code==0 and len(calls)==1
    result=out['result']; assert result['windows'][0]['name']=='' and len(result['windows'][1]['name'])==4000
    assert result['activeWindowKnown'] is False and result['details']['truncated'] is False
    import hashlib
    data=Path(result['details']['path']).read_bytes()
    assert hashlib.sha256(data).hexdigest()==result['details']['sha256']
    full=json.loads(data); assert json.loads(full['stdout'])['windows']==result['windows']
    assert b'SYNTHETIC_PRIVATE_VALUE' not in data
    assert result['details']['omitted']==['stdout','backendArgv']
    assert Path(result['details']['path']).stat().st_mode & 0o777==0o600
    assert 'stdout' in invoke({'outputMode':'full'},cmd='window.list')[1]['result']
