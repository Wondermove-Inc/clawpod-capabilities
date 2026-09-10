"""Independent review reproductions promoted to source-only regression gates.
No desktop/display interaction: backend, focus, geometry and effects are mocks.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch
import pytest

SPEC=importlib.util.spec_from_file_location('correction_desktop',Path(__file__).parents[1]/'desktop.py')
D=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(D)
OBS={'active_window':{'window_id':7},'nodes':[{'id':'a','name':'Field A','bbox':[0,0,10,10],'role':'entry'}, {'id':'b','name':'Field B','bbox':[20,0,10,10],'role':'entry','focused':True}]}
VISUAL={'windowId':'7','revision':7,'targetDigest':'fresh','focused':True}
TARGET={'kind':'coordinate','windowId':'7','observedRevision':7,'targetDigest':'fresh','x':3,'y':4,'visualRegion':[0,0,10,10],'screenshotDigest':'region','monitor':0,'scale':1}

def body():return {'args':['SYNTHETIC-TEXT'],'target':dict(TARGET),'postcondition':{'activeWindowMatch':True}}

def invoke(inp,key='same',scope=None,cmd='keyboard.type',observation=VISUAL,mode='ok',stderr='',dry=False,log=None,receipt=None,exitcode=0):
    calls=[]
    def backend(argv,ms):
        calls.append(argv)
        if argv[1]=='observe':
            if mode=='screenshots':
                from PIL import Image
                Image.new('RGB',(12,12),'white').save(argv[argv.index('--screenshot')+1])
            return subprocess.CompletedProcess(argv,exitcode,json.dumps(observation),stderr),None
        if argv[1]=='screenshot' and mode=='screenshots':
            from PIL import Image
            Image.new('RGB',(12,12),'black').save(argv[-1])
            return subprocess.CompletedProcess(argv,0,'',''),None
        if log:
            with open(log,'a') as f:f.write('dispatch\n');f.flush();os.fsync(f.fileno())
        if mode=='crash':os._exit(77)
        if mode=='slow':time.sleep(.12)
        if mode=='timeout':return None,'timeout'
        return subprocess.CompletedProcess(argv,0,'SYNTHETIC-TEXT',stderr),None
    request={'command':cmd,'input':D.redact({k:v for k,v in inp.items() if k!='outputMode'}),'idempotencyKey':key,'expectedRevision':None,'scope':str(Path(scope).resolve()) if scope else 'default'}
    args=['desktop',cmd,'--input',json.dumps(inp),'--idempotency-key',key]
    if scope:args+=['--run-root',str(scope)]
    if dry:args+=['--dry-run']
    else:args+=['--approval',json.dumps(receipt or {'requestDigest':D.digest(request),'expiresAt':'2099-01-01T00:00:00Z'})]
    out=io.StringIO()
    with patch.object(sys,'argv',args),patch.object(D,'backend_call',backend),patch.object(D,'xwindow_geometry',lambda _:{}),patch.object(D,'verify_effect',lambda *args:(True,{'activeWindowMatch':True})),contextlib.redirect_stdout(out):
        code=D.main()
    return code,json.loads(out.getvalue()),calls,out.getvalue()

@pytest.mark.parametrize('cmd,args',[('keyboard.type',['SYNTHETIC']),('pointer.click',['Field B']),('pointer.double-click',[]),('pointer.right-click',[]),('pointer.drag-drop',[])])
def test_review_accessibility_identity_never_dispatches_to_focus_or_selector(cmd,args):
    target={'kind':'accessibility','nodeId':'a'};target.update({k:v for k,v in D.target_identity(OBS,target).items() if k in ('windowId','observedRevision','targetDigest')})
    for dry in (False,True):
        code,out,calls,_=invoke({'target':target,'args':args,'postcondition':{'exists':'Field A'}},cmd=cmd,observation=OBS,dry=dry)
        assert code==31 and out['error']['code']=='ACCESSIBILITY_DISPATCH_UNSUPPORTED' and calls==[]
    assert D.target_identity(OBS,target)['focused'] is False

@pytest.mark.parametrize('scope_kind',['default','fixed'])
@pytest.mark.parametrize('outcome',['timeout','ok'])
def test_review_default_and_fixed_scope_exactly_once(tmp_path,scope_kind,outcome):
    scope=tmp_path/'desktop-runs'/'fixed' if scope_kind=='fixed' else None
    first=invoke(body(),scope=scope,mode=outcome);second=invoke(body(),scope=scope,mode=outcome)
    assert first[0]==second[0]==(40 if outcome=='timeout' else 0)
    assert len(first[2])==2 and second[2]==[]
    assert first[1]['retry']['retryable'] is False and second[1]['retry']['retryable'] is False
    assert 'SYNTHETIC-TEXT' not in first[3]
    states=list((tmp_path/'desktop-runs'/'.journal').glob('*.json'))
    assert len(states)==1

@pytest.mark.parametrize('mode',['ok','timeout'])
def test_same_key_changed_payload_conflicts(tmp_path,mode):
    invoke(body(),mode=mode)
    changed=body();changed['args']=['OTHER']
    code,out,calls,_=invoke(changed,mode=mode)
    assert code==41 and out['error']['code']=='IDEMPOTENCY_CONFLICT' and not calls

def test_explicit_scopes_are_separate_and_receipts_bind_scope(tmp_path):
    root=tmp_path/'desktop-runs'
    a,b=root/'a',root/'b'
    preview=invoke(body(),scope=a,dry=True)[1]
    receipt={'requestDigest':preview['result']['requestDigest'],'expiresAt':'2099-01-01T00:00:00Z'}
    code,out,calls,_=invoke(body(),scope=b,receipt=receipt)
    assert code==30 and out['error']['code']=='APPROVAL_REQUIRED' and not calls
    assert invoke(body(),scope=a,mode='timeout')[0]==40
    assert len(invoke(body(),scope=b,mode='timeout')[2])==2
    assert invoke(body(),scope=a)[2]==[]

def child(root,log,mode,queue):
    os.environ['DESKTOP_RUNS_ROOT']=root
    result=invoke(body(),mode=mode,log=log)
    queue.put((result[0],len(result[2])))

def test_crash_marker_survives_process_exit(tmp_path):
    root=str(tmp_path/'desktop-runs');log=str(tmp_path/'dispatches');ctx=multiprocessing.get_context('fork');q=ctx.Queue()
    p=ctx.Process(target=child,args=(root,log,'crash',q));p.start();p.join(5)
    assert not p.is_alive() and p.exitcode==77
    code,out,calls,_=invoke(body())
    assert code==40 and out['error']['code']=='OUTCOME_UNKNOWN' and calls==[]
    assert Path(log).read_text().splitlines()==['dispatch']

@pytest.mark.parametrize('outcome',['slow','timeout'])
def test_concurrent_same_key_dispatches_at_most_once(tmp_path,outcome):
    root=str(tmp_path/'desktop-runs');log=str(tmp_path/'dispatches');ctx=multiprocessing.get_context('fork');q=ctx.Queue()
    jobs=[ctx.Process(target=child,args=(root,log,outcome,q)) for _ in range(2)]
    for p in jobs:p.start()
    for p in jobs:p.join(5);assert not p.is_alive() and p.exitcode==0
    code=40 if outcome=='timeout' else 0
    assert sorted(q.get(timeout=1) for _ in jobs)==[(code,0),(code,2)]
    assert Path(log).read_text().splitlines()==['dispatch']

@pytest.mark.parametrize('count',[0,1,50,1000])
def test_compact_full_target_equivalence_and_bounded_output(count):
    obs={'active_window':{'window_id':7},'nodes':[{'id':str(i),'name':'한글-'+str(i),'bbox':[0,0,10,10],'role':'entry'} for i in range(count)]}
    compact=invoke({'target':{'kind':'accessibility','nodeId':'0'}},cmd='ui.observe',observation=obs)
    full=invoke({'target':{'kind':'accessibility','nodeId':'0'},'outputMode':'full'},cmd='ui.observe',observation=obs)
    assert compact[0]==full[0]
    if count==0:
        assert compact[1]['error']==full[1]['error'];return
    out=compact[1];assert out['result']['target']==full[1]['result']['target']
    assert len(compact[3].strip())<=1800 and compact[3].index('"target":')<400
    assert 'stdout' not in out['result'] and 'observation' not in out['result']
    meta=out['result']['details'];data=Path(meta['path']).read_bytes()
    assert len(data)==meta['bytes'] and hashlib.sha256(data).hexdigest()==meta['sha256']
    assert len(json.loads(data)['observation']['nodes'])==count

@pytest.mark.parametrize('long_field',['name','stderr'])
def test_long_fields_are_complete_with_explicit_exception(long_field):
    text='한글'*2000
    obs={'active_window':{'window_id':7},'nodes':[{'id':42,'name':text if long_field=='name' else 'entry','bbox':[0,0,10,10]}]}
    inp={'target':{'kind':'accessibility','name':obs['nodes'][0]['name']}}
    code,out,_,raw=invoke(inp,cmd='ui.observe',observation=obs,stderr=text if long_field=='stderr' else '')
    assert code==0 and out['retry']['detailsRequired'] is True
    assert out['result']['target']['nodeId']=='42'
    assert (out['result']['target']['name'] if long_field=='name' else out['result']['stderr'])==text

@pytest.mark.parametrize('exitcode',[3,4])
def test_compact_full_errors_and_stderr_unchanged(exitcode):
    for mode in ('compact','full'):
        code,out,_,_=invoke({'target':{'kind':'accessibility','nodeId':'a'},'outputMode':mode},cmd='ui.observe',stderr='warning'*1000,exitcode=exitcode)
        assert code in (20,24) and out['status']=='failed' and out['error']
        assert out['result']['stderr']=='warning'*1000 and out['retry']['detailsRequired'] is True

@pytest.mark.parametrize('change',[{'args':'text'},{'target':None},{'target':{**TARGET,'visualRegion':{'x':0,'y':0,'width':10,'height':10}}},{'postcondition':{'searchFieldText':'literal'}},{'target':{**TARGET,'scale':float('nan')}}])
def test_invalid_precision_shapes_fail_in_preview_without_backend(change):
    inp=body();inp.update(change)
    code,out,calls,_=invoke(inp,dry=True)
    assert code in (10,31) and out['error'] and not calls
    assert 'wouldExecute' not in out['result']

def test_formatting_does_not_change_receipt_identity_or_unknown_semantics():
    a=invoke(body(),dry=True)[1]
    full=body();full['outputMode']='full'
    b=invoke(full,dry=True)[1]
    assert a['result']['requestDigest']==b['result']['requestDigest']
    assert a['result']['shapeValidated'] is True and a['result']['liveTargetValidated'] is False
    invoke(body(),mode='timeout')
    code,out,calls,_=invoke(full)
    assert code==40 and out['error']['code']=='OUTCOME_UNKNOWN' and not calls


def test_after_screenshot_reference_reuses_the_verification_capture():
    inp=body();inp['postcondition']={'visualRegionChanged':True}
    code,out,calls,_=invoke(inp,mode='screenshots')
    assert code==0 and sum(argv[1]=='screenshot' for argv in calls)==1
    meta=out['result']['afterScreenshot'];data=Path(meta['path']).read_bytes()
    assert hashlib.sha256(data).hexdigest()==meta['sha256'] and len(data)==meta['bytes']
    assert 'literalTextVerified' not in out['result']['verification']

def test_observation_artifact_is_private_and_redacts_structured_fields():
    observation={**OBS,'password':'synthetic-not-a-real-secret'}
    code,out,_,_=invoke({'target':{'kind':'accessibility','nodeId':'a'}},cmd='ui.observe',observation=observation)
    path=Path(out['result']['details']['path'])
    assert code==0 and path.stat().st_mode & 0o777==0o600
    assert 'synthetic-not-a-real-secret' not in path.read_text()
    assert '[REDACTED]' in path.read_text()

@pytest.mark.parametrize('content',['invalid-json','[]','{"revision":0,"idempotency":{"same":{"status":"other"}}}'])
def test_corrupt_journal_fails_closed(tmp_path,content):
    directory=tmp_path/'desktop-runs'/'.journal';directory.mkdir(parents=True)
    (directory/(D.digest('default')+'.json')).write_text(content)
    code,out,calls,_=invoke(body())
    assert code==31 and out['error']['code']=='CHECKPOINT_UNAVAILABLE' and not calls

def test_legacy_unknown_checkpoint_is_never_ignored(tmp_path):
    root=tmp_path/'desktop-runs'/'legacy';root.mkdir(parents=True)
    (root/'state.json').write_text(json.dumps({'revision':0,'idempotency':{'same':{'digest':'legacy-digest','status':'outcome_unknown','result':{}}}}))
    code,out,calls,_=invoke(body(),scope=root)
    assert code==41 and out['error']['code']=='IDEMPOTENCY_CONFLICT' and not calls

def test_visual_target_cannot_be_overridden_by_positional_selector():
    inp=body();inp['args']=['Field B']
    code,out,calls,_=invoke(inp,cmd='pointer.click',dry=True)
    assert code==31 and out['error']['code']=='INVALID_INPUT' and not calls

def test_observation_binding_errors_do_not_hide_stderr():
    code,out,_,_=invoke({'target':{'kind':'accessibility','nodeId':'missing'}},cmd='ui.observe',observation=OBS,stderr='important warning')
    assert code==20 and out['error']['code']=='TARGET_NOT_FOUND'
    assert out['result']['stderr']=='important warning'


@pytest.mark.parametrize('node_id',[0,'0',42,'42'])
def test_node_ids_are_canonical_strings(node_id):
    observation={'active_window':{'window_id':7},'nodes':[{'id':node_id,'name':'Entry','bbox':[0,0,10,10]}]}
    identity=D.target_identity(observation,{'nodeId':node_id})
    assert identity['nodeId']==str(node_id)
    assert D.observation_index(observation)['targets'][0]['nodeId']==str(node_id)

@pytest.mark.parametrize('field,value',[('observedRevision',None),('targetDigest',''),('windowId',None),('screenshotDigest',None)])
def test_invalid_identity_values_fail_in_preview(field,value):
    inp=body();inp['target'][field]=value
    code,out,calls,_=invoke(inp,dry=True)
    assert code==31 and out['error'] and not calls
