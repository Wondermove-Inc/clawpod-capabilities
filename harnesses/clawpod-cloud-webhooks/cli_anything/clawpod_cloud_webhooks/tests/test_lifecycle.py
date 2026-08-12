import json, os
import pytest
from click.testing import CliRunner
from cli_anything.clawpod_cloud_webhooks.clawpod_cloud_webhooks_cli import cli
from cli_anything.clawpod_cloud_webhooks.core.contracts import create_preview
from cli_anything.clawpod_cloud_webhooks.core.lifecycle import execute_plan, validate_plan
from cli_anything.clawpod_cloud_webhooks.utils.backend import BackendError

class Fake:
    def __init__(self,fail=None): self.calls=[]; self.fail=fail; self.next=10
    def request(self,m,p,body=None,idempotency=None,deadline=None):
        self.calls.append((m,p,body,idempotency))
        if self.fail and len(self.calls)==self.fail: raise BackendError('backend_error','redacted backend failure',False,500)
        if m=='POST' and p.endswith('sources'): self.next+=1; return {'source':{'id':self.next}}
        if m=='GET' and '/webhook-sources/' in p: return {'id':self.next,'name':'x','tenant_id':1}
        return {'items':[]}

def create_step(name='make'):
    payload={'name':'x','tenant_id':1}; key='stable-create'; d=create_preview('source',payload,1,key)['effect_digest']
    return {'name':name,'operation':'source.create','tenant_id':1,'payload':{'name':'x'},'idempotency_key':key,'effect_digest':d,'approve':True}

def test_one_backend_plan_and_reference():
    f=Fake(); plan={'steps':[create_step(),{'name':'read','operation':'source.get','tenant_id':1,'resource_id':'$steps.make.readback.id'}]}
    out=execute_plan(f,plan)
    assert out['ok'] and out['login_count']==1 and '/11?' in f.calls[-1][1]
    assert out['cleanup_required']==[{'kind':'source','id':11,'step':'make'}]

def test_bounds_reference_and_digest_validation():
    try: validate_plan({'steps':[{'name':str(i),'operation':'source.list'} for i in range(31)]})
    except ValueError: pass
    else: assert False
    f=Fake(); bad=create_step(); bad['effect_digest']='sha256:bad'
    out=execute_plan(f,{'steps':[bad]}); assert not out['ok'] and not f.calls
    out=execute_plan(f,{'steps':[{'name':'x','operation':'source.get','tenant_id':1,'resource_id':'$steps.future.readback.id'}]})
    assert not out['ok']

def test_unknown_fields_and_referenced_safety_controls_fail_before_backend():
    base=create_step()
    cases=[]
    for field in ('approve','idempotency_key','effect_digest'):
        value=dict(base); value[field]='$steps.prior.readback.id'; cases.append(value)
    value=dict(base); value['surprise']=True; cases.append(value)
    value=dict(base); value['payload']={'name':'x','unknown':1}; cases.append(value)
    for value in cases:
        f=Fake()
        try: out=execute_plan(f,{'steps':[value]})
        except ValueError: pass
        else: assert not out['ok']
        assert f.calls==[]

def test_resolved_empty_or_nonscalar_ids_fail_before_backend():
    class Seed(Fake):
        pass
    for resolved in ('',None,False,{}):
        # Seed completed output without backend access by invoking resolver path
        # through a prior list whose result supplies the candidate value.
        class Values(Fake):
            def request(self,m,p,**kw):
                self.calls.append((m,p,None,None)); return {'candidate':resolved}
        f=Values(); plan={'steps':[{'name':'seed','operation':'source.list','tenant_id':1},{'name':'read','operation':'source.get','tenant_id':1,'resource_id':'$steps.seed.result.candidate'}]}
        out=execute_plan(f,plan)
        assert not out['ok'] and len(f.calls)==1

def test_resolved_invalid_update_payload_fails_before_target_backend_call():
    class Values(Fake):
        def request(self,m,p,**kw): self.calls.append((m,p,None,None)); return {'candidate':''}
    key='literal'; step={'name':'update','operation':'source.update','tenant_id':1,'resource_id':'$steps.seed.result.candidate','changes':{'name':'x'},'approve':True,'idempotency_key':key,'effect_digest':'sha256:literal'}
    f=Values(); out=execute_plan(f,{'steps':[{'name':'seed','operation':'source.list','tenant_id':1},step]})
    assert not out['ok'] and len(f.calls)==1

def test_partial_failure_redaction_and_cleanup_only_created():
    f=Fake(fail=3); plan={'steps':[create_step(),{'name':'existing','operation':'source.get','tenant_id':1,'resource_id':99}]}
    out=execute_plan(f,plan)
    assert not out['ok'] and out['failed_step']=='existing' and out['cleanup_required'][0]['id']==11
    assert 'password' not in json.dumps(out).lower()

def test_missing_create_id_and_readback_failure_are_uncertain_cleanup():
    class Missing(Fake):
        def request(self,m,p,**kw): return {} if m=='POST' else super().request(m,p,**kw)
    out=execute_plan(Missing(),{'steps':[create_step()]})
    assert out['error']['code']=='verification_failed' and out['partial_state']['uncertain'] and out['cleanup_required'][0]['reconciliation_required']
    create=create_step(); out=execute_plan(Fake(fail=2),{'steps':[create]})
    assert_reconciliation(out,create,'source',11)

def test_deadline_is_forwarded_and_stops_plan(monkeypatch):
    seen=[]
    class DeadlineFake(Fake):
        def request(self,*a,deadline=None,**kw): seen.append(deadline); return super().request(*a,deadline=deadline,**kw)
    out=execute_plan(DeadlineFake(),{'steps':[{'name':'a','operation':'source.list','tenant_id':1}]},deadline=10**12)
    assert out['ok'] and seen==[10**12]
    import time
    out=execute_plan(DeadlineFake(),{'steps':[{'name':'a','operation':'source.list','tenant_id':1}]},deadline=time.monotonic()-1)
    assert out['error']['code']=='plan_timeout' and out['partial_state']['uncertain']

def test_secret_action_missing_ack_is_uncertain():
    from cli_anything.clawpod_cloud_webhooks.core.contracts import preview
    class Secret(Fake):
        def request(self,m,p,**kw):
            if m=='GET': return {'id':7,'name':'x','tenant_id':1,'previous_secret_expires_at':None}
            return {}
    before={'id':7,'name':'x','tenant_id':1,'previous_secret_expires_at':None}; key='rotate-key'
    d=preview('source',7,before,{**before,'secret_action':'rotate'},1,key)['effect_digest']
    step={'name':'r','operation':'source.rotate','tenant_id':1,'resource_id':7,'idempotency_key':key,'effect_digest':d,'approve':True}
    out=execute_plan(Secret(),{'steps':[step]}); assert out['error']['code']=='verification_failed' and out['partial_state']['uncertain']
    assert_reconciliation(out,step,'source',7)

def assert_reconciliation(out,step,kind,rid):
    assert out['error']['code']=='verification_failed' and out['error']['retry_safe'] is False and out['partial_state']['uncertain'] is True
    assert out['cleanup_required']==[{'operation':step['operation'],'kind':kind,'resource_id':rid,'idempotency_key':step['idempotency_key'],'effect_digest':step['effect_digest'],'reconciliation_required':True,'uncertain':True,'retry_safe':False}]

def test_mutation_transport_failures_require_structured_reconciliation():
    from cli_anything.clawpod_cloud_webhooks.core.contracts import delete_preview, preview
    before={'id':7,'name':'x','tenant_id':1}; cases=[]
    create=create_step(); cases.append((create,'source',None))
    for action,after in [('update',{**before,'name':'y'}),('delete',None),('rotate',{**before,'secret_action':'rotate'})]:
        key='key-'+action
        digest=(delete_preview('source',7,before,1,key) if action=='delete' else preview('source',7,before,after,1,key))['effect_digest']
        step={'name':action,'operation':'source.'+action,'tenant_id':1,'resource_id':7,'idempotency_key':key,'effect_digest':digest,'approve':True}
        if action=='update': step['changes']={'name':'y'}
        cases.append((step,'source',7))
    class Transport:
        def request(self,m,p,**kw):
            if m=='GET': return before
            raise BackendError('timeout','transport timeout',False)
    for step,kind,rid in cases:
        out=execute_plan(Transport(),{'steps':[step]}); rec=out['cleanup_required'][0]
        assert out['partial_state']['uncertain'] and out['error']['retry_safe'] is False
        assert rec=={'operation':step['operation'],'kind':kind,'resource_id':rid,'idempotency_key':step['idempotency_key'],'effect_digest':step['effect_digest'],'reconciliation_required':True,'uncertain':True,'retry_safe':False}

def test_every_post_dispatch_verification_failure_has_identical_reconciliation():
    from cli_anything.clawpod_cloud_webhooks.core.contracts import delete_preview, preview
    before={'id':7,'name':'x','tenant_id':1,'previous_secret_expires_at':None}
    def step(action,after=None):
        key='verify-'+action
        d=(delete_preview('source',7,before,1,key) if action=='delete' else preview('source',7,before,after,1,key))['effect_digest']
        value={'name':action,'operation':'source.'+action,'tenant_id':1,'resource_id':7,'idempotency_key':key,'effect_digest':d,'approve':True}
        if action=='update': value['changes']={'name':'y'}
        return value
    update=step('update',{**before,'name':'y'}); delete=step('delete'); rotate=step('rotate',{**before,'secret_action':'rotate'})
    class Scenario:
        def __init__(self,mode): self.mode=mode; self.gets=0
        def request(self,m,p,**kw):
            if m=='GET':
                self.gets+=1
                if self.gets==1: return before
                if self.mode in ('readback_error','delete_error'): raise BackendError('backend_error','verification failed',False,500)
                if self.mode=='update_mismatch': return {**before,'name':'wrong'}
                if self.mode=='delete_present': return before
                if self.mode=='rotate_lifecycle_missing': return {k:v for k,v in before.items() if k!='previous_secret_expires_at'}
                return before
            if self.mode=='rotate_ack_missing': return {}
            return {'secret':'redacted'} if 'rotate-secret' in p else {'ok':True}
    for mutation,mode in [(update,'readback_error'),(update,'update_mismatch'),(delete,'delete_error'),(delete,'delete_present'),(rotate,'rotate_ack_missing'),(rotate,'readback_error'),(rotate,'rotate_lifecycle_missing')]:
        out=execute_plan(Scenario(mode),{'steps':[mutation]})
        assert_reconciliation(out,mutation,'source',7)

def test_full_successful_lifecycle_returns_results_and_clears_cleanup():
    from copy import deepcopy
    from cli_anything.clawpod_cloud_webhooks.core.contracts import delete_preview, preview
    class Stateful:
        def __init__(self): self.item=None; self.calls=[]
        def request(self,m,p,body=None,idempotency=None,deadline=None):
            self.calls.append((m,p,deepcopy(body),idempotency))
            if m=='POST': self.item={**body,'id':41}; return {'rule':{'id':41},'accepted':True}
            if m=='PUT': self.item=deepcopy(body); return {'updated':True,'id':41}
            if m=='DELETE': self.item=None; return {'deleted':True,'id':41}
            if m=='GET' and '/webhook-rules/41' in p:
                if self.item is None: raise BackendError('not_found','backend HTTP 404',True,404)
                return deepcopy(self.item)
            return {'items':[]}
    tenant=1; rid='$steps.create.readback.id'; states=[]
    current={'name':'rule','tenant_id':tenant}; states.append(deepcopy(current))
    create_key='full-create'; steps=[{'name':'create','operation':'rule.create','tenant_id':tenant,'payload':{'name':'rule'},'idempotency_key':create_key,'effect_digest':create_preview('rule',current,tenant,create_key)['effect_digest'],'approve':True}]
    for name,changes in [('update',{'description':'changed'}),('disable',{'is_active':False}),('enable',{'is_active':True}),('reorder',{'priority':9})]:
        before={**states[-1],'id':41} if 'id' not in states[-1] else states[-1]; after={**before,**changes}; key='full-'+name
        step={'name':name,'operation':'rule.'+name,'tenant_id':tenant,'resource_id':rid,'idempotency_key':key,'effect_digest':preview('rule',41,before,after,tenant,key)['effect_digest'],'approve':True}
        if name=='update': step['changes']=changes
        if name=='reorder': step['priority']=9
        steps.append(step); states.append(after)
    before=states[-1]; key='full-delete'
    steps.append({'name':'delete','operation':'rule.delete','tenant_id':tenant,'resource_id':rid,'idempotency_key':key,'effect_digest':delete_preview('rule',41,before,tenant,key)['effect_digest'],'approve':True})
    out=execute_plan(Stateful(),{'steps':steps})
    assert out['ok'] and len(out['completed_steps'])==6 and out['cleanup_required']==[]
    assert all(step.get('result') is not None for step in out['completed_steps'] if step['operation']!='rule.delete')

def test_cli_login_exactly_once_and_no_persistence(monkeypatch):
    counts={'login':0}; calls=[]
    def login(self,deadline=None): counts['login']+=1; self.authenticated=True
    def request(self,m,p,**kw): calls.append((m,p)); return {'items':[]}
    monkeypatch.setattr('cli_anything.clawpod_cloud_webhooks.utils.backend.Backend.login_from_env',login)
    monkeypatch.setattr('cli_anything.clawpod_cloud_webhooks.utils.backend.Backend.request',request)
    result=CliRunner().invoke(cli,['--json','lifecycle','execute','--plan-json',json.dumps({'steps':[{'name':'a','operation':'source.list','tenant_id':1},{'name':'b','operation':'event.list','tenant_id':1}]})])
    assert result.exit_code==0 and counts['login']==1 and len(calls)==2
    data=json.loads(result.output); assert data['login_count']==1 and data['session']['persistent'] is False
