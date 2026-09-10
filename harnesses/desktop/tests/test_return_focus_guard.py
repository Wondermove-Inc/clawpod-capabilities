"""Real main/run_main/backend_call/target/journal branches; all X/backend I/O mocked.
No live GUI, wrapper lifecycle, sleep, or subprocess escapes this fixture.
"""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import pytest

SPEC=importlib.util.spec_from_file_location('return_guard_desktop',Path(__file__).parents[1]/'desktop.py')
D=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(D)
DISPLAY={'display':':99','width':100,'height':100,'dpiX':96,'dpiY':96}
TARGET={'kind':'coordinate','windowId':'7','x':3,'y':4,'visualRegion':[0,0,10,10],'monitor':0,'scale':1}
POST={'activeWindowMatch':True,'windowBoundsUnchanged':True}

class Fixture:
    def __init__(self):
        self.mode='ok';self.calls=[];self.keys=0;self.clock=10.;self.active_reads=0;self.metric_reads=0
        self.budgets=[]; self.checkpoint_at_key=False
    def run(self,argv,**kw):
        self.calls.append(argv); self.budgets.append(kw['timeout'])
        assert 0<kw['timeout']<=30
        self.clock+=.001
        action=argv[1] if len(argv)>1 else 'metrics'
        if argv==['xdpyinfo']:
            self.metric_reads+=1
            if self.mode=='metrics-timeout':raise subprocess.TimeoutExpired(argv,kw['timeout'])
            width=200 if self.mode=='drift' or (self.mode=='final-drift' and self.metric_reads>=6) else 100
            return subprocess.CompletedProcess(argv,0,f'dimensions: {width}x100 pixels\nresolution: 96x96 dots per inch','')
        if action=='getwindowpid':
            value='' if self.mode=='missing-pid' else '43' if self.mode=='pid-reuse' or (self.mode=='final-pid' and self.active_reads>=2) else '42'
        elif action=='getactivewindow':
            self.active_reads+=1
            value='8' if self.mode=='wrong-focus' or (self.mode=='final-focus' and self.active_reads>=3) else '7'
            if self.mode=='expire-final' and self.active_reads>=3:self.clock+=31
        elif action=='getwindowgeometry':value='X=0\nY=0\nWIDTH=100\nHEIGHT=100'
        elif action=='observe':
            if self.mode=='observe-timeout':raise subprocess.TimeoutExpired(argv,kw['timeout'])
            from PIL import Image
            Image.new('RGB',(100,100),'black' if self.mode=='stale' else 'white').save(argv[-1])
            value=json.dumps({'active_window':{'window_id':7},'screen':{'width':100,'height':100},'screenshot':argv[-1],**({'accessibilityMatch':True} if self.mode=='accessible' else {})})
        elif action=='key':
            assert argv[-1]=='Return'
            self.keys+=1
            root=Path(D.os.environ['DESKTOP_RUNS_ROOT'])
            states=list((root/'.journal').glob('*.json'))
            self.checkpoint_at_key=any(v['status']=='outcome_unknown' for v in json.loads(states[0].read_text())['idempotency'].values())
            if self.mode=='dispatch-timeout':raise subprocess.TimeoutExpired(argv,kw['timeout'])
            if self.mode=='dispatch-crash':raise RuntimeError('simulated crash')
            if self.mode=='post-dispatch-expiry':self.clock+=31
            value=''
        elif action=='screenshot':
            if self.mode=='capture-fail':return subprocess.CompletedProcess(argv,1,'','capture failed')
            from PIL import Image
            Image.new('RGB',(100,100),'white').save(argv[-1]);value=''
        else:raise AssertionError(('UNMOCKED I/O',argv))
        return subprocess.CompletedProcess(argv,0,value,'')
    def invoke(self,inp,cmd='keyboard.key',key='same',dry=False,timeout=30000):
        self.active_reads=0;self.metric_reads=0
        argv=['desktop',cmd,'--input',json.dumps(inp),'--idempotency-key',key,'--timeout-ms',str(timeout)]
        if dry:argv+=['--dry-run']
        out=io.StringIO()
        with patch.object(sys,'argv',argv),patch.object(D.subprocess,'run',self.run),patch.object(D.shutil,'which',lambda tool:tool),patch.dict(D.os.environ,{'DISPLAY':':99','DESKTOP_DISPOSABLE_DISPLAY':'0','DESKTOP_SYSTEM_CLI':str(Path(D.__file__).parent/'engine'/'desktop')}),patch.object(D.time,'monotonic',lambda:self.clock),contextlib.redirect_stdout(out):
            code=D.main()
        return code,json.loads(out.getvalue())
    def prepared(self,capture=False):
        code,out=self.invoke({'target':TARGET,'prepareFocusGuard':True},cmd='ui.observe')
        assert code==0,out
        return {'args':['Return'],'target':out['result']['target'],'focusGuard':out['result']['focusGuard'],'postcondition':POST,**({'postCapture':True} if capture else {})}

@pytest.mark.parametrize('mutation',[lambda x:x.pop('focusGuard'),lambda x:x.update(focusGuard=False),lambda x:x.update(focusGuard=None),lambda x:x.update(focusGuard={}),lambda x:x['focusGuard'].update(pid=True),lambda x:x['focusGuard'].update(windowId='8'),lambda x:x['focusGuard']['observation'].update(revision=True)])
@pytest.mark.parametrize('dry',[False,True])
def test_invalid_guard_zero_dispatch(mutation,dry):
    f=Fixture();inp=f.prepared(True);mutation(inp);before=len(f.calls)
    code,out=f.invoke(inp,dry=dry)
    assert code!=0 and f.keys==0 and len(f.calls)==before

@pytest.mark.parametrize('mode',['wrong-focus','pid-reuse','missing-pid','stale','drift','observe-timeout','final-focus','expire-final','accessible','final-pid','final-drift','metrics-timeout'])
def test_real_run_main_guard_rejects_before_key(mode):
    f=Fixture();inp=f.prepared();f.mode=mode
    code,out=f.invoke(inp)
    assert code!=0 and f.keys==0,out
    assert not any('focus'==a[1] for a in f.calls if len(a)>1)
    before=len(f.calls);f.mode='ok'
    assert f.invoke(inp)[1]['error']['code']=='OUTCOME_UNKNOWN'
    assert len(f.calls)==before and f.keys==0

@pytest.mark.parametrize('capture',[False,True])
def test_normal_once_cached_success_and_payload_binding(capture):
    f=Fixture();inp=f.prepared(capture)
    code,out=f.invoke(inp)
    assert code==0 and f.keys==1 and f.checkpoint_at_key,out
    assert out['result']['postconditionConfirmed'] is True
    before=len(f.calls)
    assert f.invoke({**inp,'outputMode':'full'})[0]==0
    assert f.keys==1 and len(f.calls)==before
    altered=copy.deepcopy(inp);altered['focusGuard']['pid']=43
    assert f.invoke(altered)[1]['error']['code']=='IDEMPOTENCY_CONFLICT'
    assert f.keys==1 and len(f.calls)==before

@pytest.mark.parametrize('mode',['dispatch-timeout','dispatch-crash','capture-fail','post-dispatch-expiry'])
def test_unknown_and_capture_failure_never_replay(mode):
    f=Fixture();inp=f.prepared(True);f.mode=mode
    if mode=='dispatch-crash':
        with pytest.raises(RuntimeError):f.invoke(inp)
    else:
        code,out=f.invoke(inp)
        assert code==(0 if mode=='capture-fail' else 25 if mode=='post-dispatch-expiry' else 40),out
    before=len(f.calls);f.mode='ok';code,out=f.invoke(inp)
    assert code==(0 if mode=='capture-fail' else 40)
    assert f.keys==1 and len(f.calls)==before

@pytest.mark.parametrize('cmd,args',[('keyboard.key',['Tab']),('keyboard.shortcut',['Return'])])
def test_unsupported_key_guard(cmd,args):
    f=Fixture();inp=f.prepared();inp['args']=args;before=len(f.calls)
    assert f.invoke(inp,cmd=cmd)[1]['error']['code']=='FOCUS_GUARD_UNSUPPORTED'
    assert len(f.calls)==before and f.keys==0

def test_expired_budget_no_subprocess_or_clamp():
    f=Fixture();inp=f.prepared();before=len(f.calls)
    assert f.invoke(inp,timeout=0)[1]['error']['code']=='TIMEOUT'
    assert len(f.calls)==before and f.keys==0

def test_legacy_plain_return_is_explicitly_unguarded():
    f=Fixture()
    assert f.invoke({'args':['Return']})[0]==0 and f.keys==1
    assert not any('observe' in a or 'getactivewindow' in a for a in f.calls)

def test_guard_preparation_binding_and_dry_preview():
    f=Fixture();inp=f.prepared();guard=inp['focusGuard'];target=inp['target']
    assert guard=={'windowId':target['windowId'],'pid':42,'observation':{'revision':target['observedRevision'],'digest':target['targetDigest'],'display':DISPLAY}}
    before=len(f.calls);code,out=f.invoke(inp,dry=True)
    assert code==0 and out['result']['liveTargetValidated'] is False
    assert out['result']['preview']['input']==inp and len(f.calls)==before

@pytest.mark.parametrize('mode',['wrong-focus','missing-pid','observe-timeout','accessible'])
def test_preparation_failure_never_returns_guard(mode):
    f=Fixture();f.mode=mode
    code,out=f.invoke({'target':TARGET,'prepareFocusGuard':True},cmd='ui.observe')
    assert code!=0 and 'focusGuard' not in out['result'] and f.keys==0

@pytest.mark.parametrize('original',['0x07','007',7])
def test_numeric_window_alias_preserves_original_prepared_id(original):
    f=Fixture();code,out=f.invoke({'target':{**TARGET,'windowId':original},'prepareFocusGuard':True},cmd='ui.observe')
    assert code==0,out
    result=out['result'];assert result['target']['windowId']==result['focusGuard']['windowId']==original
    inp={'args':['Return'],'target':result['target'],'focusGuard':result['focusGuard'],'postcondition':POST}
    assert f.invoke(inp)[0]==0 and f.keys==1

def test_guard_screenshot_and_details_private():
    f=Fixture();inp=f.prepared();assert f.invoke(inp)[0]==0
    for argv in f.calls:
        if len(argv)>1 and argv[1]=='observe':
            shot=Path(argv[-1]);assert shot.stat().st_mode & 0o777==0o600
            assert shot.parent.stat().st_mode & 0o777==0o700

def test_contract_schemas_accept_real_preparation_and_reject_invalid_guard():
    import jsonschema
    contracts=json.loads((Path(D.__file__).parent/'command_contracts.json').read_text())['commands']
    key_schema=contracts['keyboard.key']['innerInputSchema'];observe_schema=contracts['ui.observe']['innerInputSchema']
    jsonschema.Draft202012Validator.check_schema(key_schema);jsonschema.Draft202012Validator.check_schema(observe_schema)
    f=Fixture();inp=f.prepared(True)
    jsonschema.validate(inp,key_schema)
    jsonschema.validate({'target':TARGET,'prepareFocusGuard':True},observe_schema)
    for bad in [False,None,{}, {'windowId':'7','pid':True,'observation':inp['focusGuard']['observation']}]:
        with pytest.raises(jsonschema.ValidationError):jsonschema.validate({**inp,'focusGuard':bad},key_schema)
    no_guard=dict(inp);no_guard.pop('focusGuard')
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(no_guard,key_schema)
    jsonschema.validate({'args':['Return']},key_schema)

@pytest.mark.parametrize('change',[
    lambda x:x['focusGuard'].update(pid=0),
    lambda x:x['focusGuard'].update(pid='42'),
    lambda x:x['focusGuard']['observation']['display'].update(width=True),
    lambda x:x['focusGuard']['observation'].pop('digest'),
    lambda x:x.pop('target'),
    lambda x:x['target'].update(kind='accessibility'),
    lambda x:x.update(postcondition={'activeWindowMatch':True}),
    lambda x:x['target'].update(scale=False),
])
def test_shape_and_precision_restrictions_still_fail_closed(change):
    f=Fixture();inp=f.prepared();change(inp);before=len(f.calls)
    code,out=f.invoke(inp)
    assert code!=0 and f.keys==0 and len(f.calls)==before

def test_budget_consumed_without_resets_and_final_read_is_immediately_before_key():
    f=Fixture();inp=f.prepared();f.calls=[];f.budgets=[]
    assert f.invoke(inp)[0]==0
    key_index=next(i for i,a in enumerate(f.calls) if len(a)>1 and a[1]=='key')
    assert f.calls[key_index-1][1]=='getactivewindow'
    # All non-metrics (5-second cap) calls share the original 30-second deadline.
    bounds=[b for a,b in zip(f.calls,f.budgets) if len(a)>1]
    assert all(a>b for a,b in zip(bounds,bounds[1:]))
    assert f.checkpoint_at_key

def test_checkpoint_write_failure_never_dispatches():
    f=Fixture();inp=f.prepared()
    with patch.object(D,'atomic_state',side_effect=OSError('synthetic checkpoint failure')):
        code,out=f.invoke(inp)
    assert code==31 and out['error']['code']=='CHECKPOINT_UNAVAILABLE' and f.keys==0

def test_capture_display_restriction_still_blocks_before_dispatch():
    f=Fixture();inp=f.prepared(True)
    with patch.object(D.GuardBudget,'metrics',return_value={**DISPLAY,'display':':unverified'}):
        code,out=f.invoke(inp)
    assert code==25 and out['error']['code']=='CAPTURE_DISPLAY_UNSUPPORTED' and f.keys==0
