import json, os, shutil, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from cli_anything.clawpod_cloud_webhooks.utils.backend import Backend, BackendError
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

PRIVATE_KEY=rsa.generate_private_key(public_exponent=65537,key_size=2048)
PUBLIC_PEM=PRIVATE_KEY.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
STATE={'source':{'id':'s1','name':'n','description':None,'provider':'custom','auth_type':'none','auth_config':{},'rate_limit_per_minute':10,'is_active':True,'playbook_id':'p1','tenant_id':'t'},'retry':0,'partial':False,'paths':[],'logins':0}
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def out(self,obj,status=200,headers=None):
        b=json.dumps(obj).encode(); self.send_response(status)
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        STATE['paths'].append(self.path)
        if self.path=='/api/auth/public-key': return self.out({'public_key':PUBLIC_PEM})
        if self.path=='/slow':
            time.sleep(.2); return self.out({'ok':True})
        if self.path=='/retry':
            STATE['retry']+=1
            return self.out({'error':'later'},503) if STATE['retry']<3 else self.out({'ok':True})
        if self.path=='/authfail': return self.out({'authorization':'Bearer should-never-emit'},401)
        if self.path.startswith('/api/proxy/auth/me'): return self.out({'authenticated':True})
        if '/webhook-sources/s1' in self.path: return self.out(dict(STATE['source']))
        if '/webhook-events/e1' in self.path: return self.out({'id':'e1','status':'delivered','error_message':'','headers':{'Authorization':'Bearer hidden','Cookie':'sid=hidden'},'request_url':'https://x/incoming/urlTOKEN12345','destination_evidence':{'message_id':'m'}})
        if '/webhook-events/e2' in self.path: return self.out({'id':'e2','status':'delivered','error_message':'tenant isolation violation'})
        if self.path.startswith('/api/proxy/webhook-sources'): return self.out([STATE['source']])
        if self.path.startswith('/api/proxy/webhook-'): return self.out({'items':[]})
        if self.path.startswith('/api/proxy/auth/permissions'): return self.out({'items':['read']})
        return self.out({'error':'not found'},404)
    def do_POST(self):
        STATE['paths'].append(self.path); n=int(self.headers.get('Content-Length','0')); obj=json.loads(self.rfile.read(n))
        if self.path=='/api/auth/login':
            import base64
            raw=PRIVATE_KEY.decrypt(base64.b64decode(obj['encrypted_password']),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
            payload=json.loads(raw); assert payload['password']=='synthetic-password' and isinstance(payload['timestamp'],int) and obj['email']=='synthetic@example.invalid'
            STATE['logins']+=1; return self.out({'ok':True},headers={'Set-Cookie':'session=synthetic; HttpOnly'})
        return self.out({'error':'not found'},404)
    def do_PUT(self):
        STATE['paths'].append(self.path)
        n=int(self.headers.get('Content-Length','0')); obj=json.loads(self.rfile.read(n));
        if STATE['partial']: obj['playbook_id']=None
        STATE['source'].update(obj); self.out({'updated':True})
@pytest.fixture(scope='module')
def server():
    srv=ThreadingHTTPServer(('127.0.0.1',0),H); th=threading.Thread(target=srv.serve_forever,daemon=True); th.start(); yield f'http://127.0.0.1:{srv.server_port}'; srv.shutdown()
@pytest.fixture(autouse=True)
def synthetic_auth(monkeypatch):
    monkeypatch.setenv('CLAWPOD_CLOUD_EMAIL','synthetic@example.invalid'); monkeypatch.setenv('CLAWPOD_CLOUD_PASSWORD','synthetic-password')

def cli_base():
    p=shutil.which('cli-anything-clawpod-cloud-webhooks')
    if p:return [p]
    if os.getenv('CLI_ANYTHING_FORCE_INSTALLED')=='1': raise RuntimeError('installed CLI missing')
    return [sys.executable,'-m','cli_anything.clawpod_cloud_webhooks.clawpod_cloud_webhooks_cli']
def run(server,args): return subprocess.run(cli_base()+['--base-url',server,'--json']+args,text=True,capture_output=True)

def test_backend_retries_get(server): STATE['retry']=0; assert Backend(server,retries=2).request('GET','/retry',authenticated=False)['ok'] and STATE['retry']==3
def test_auth_failure_typed_and_no_body_leak(server):
    with pytest.raises(BackendError) as e: Backend(server,retries=0).request('GET','/authfail',authenticated=False)
    assert e.value.code=='auth_failed' and 'should-never-emit' not in str(e.value)
def test_bounded_timeout_and_retry_safety(server):
    with pytest.raises(BackendError) as e: Backend(server,timeout=.03,retries=0).request('GET','/slow',authenticated=False)
    assert e.value.code=='timeout' and e.value.retry_safe
def test_subprocess_version_from_outside(server,tmp_path):
    p=run(server,['system','version']); d=json.loads(p.stdout); assert p.returncode==0 and d['capability']['name']=='clawpod-cloud-webhooks'
def test_typed_reads(server):
    for args in (['permissions','list','--tenant-id','t'],['presets','list','--tenant-id','t'],['source','get','s1','--tenant-id','t'],['playbook','list','--tenant-id','t'],['rule','list','--tenant-id','t'],['event','list','--tenant-id','t']):
        p=run(server,args); assert p.returncode==0, p.stderr
def test_auth_contract(server):
    d=json.loads(run(server,['auth','contract']).stdout)
    assert d['login']['algorithm']=='RSA-OAEP' and d['onboarding_requires_explicit_approval']
    assert d['onboarding']['required_account']=='ClawPod Cloud TA account or an account with Webhook Manager permission'
    assert d['onboarding']['installation_is_connection'] is False
    assert 'blocker' in d['onboarding']['missing_permission_behavior']
def test_rsa_login_and_real_proxy_paths(server):
    STATE['paths'].clear(); STATE['logins']=0
    p=run(server,['source','list','--tenant-id','t']); assert p.returncode==0 and STATE['logins']==1
    assert STATE['paths'][:3]==['/api/auth/public-key','/api/auth/login','/api/proxy/webhook-sources?tenant_id=t']
def test_missing_protected_env_fails_but_no_auth_commands_work(server):
    env=os.environ.copy(); env.pop('CLAWPOD_CLOUD_EMAIL',None); env.pop('CLAWPOD_CLOUD_PASSWORD',None)
    p=subprocess.run(cli_base()+['--base-url',server,'--json','source','list','--tenant-id','t'],text=True,capture_output=True,env=env)
    assert p.returncode==2 and json.loads(p.stdout)['error']['code']=='auth_required'
    p=subprocess.run(cli_base()+['--json','system','version'],text=True,capture_output=True,env=env); assert p.returncode==0
    p=subprocess.run(cli_base()+['--json','auth','contract'],text=True,capture_output=True,env=env); assert p.returncode==0
def test_auth_status_cookie_safe(server):
    d=json.loads(run(server,['auth','status']).stdout); assert not d['local']['sensitive_values_exposed'] and d['local']['protected_session']
def test_event_redaction(server):
    p=run(server,['event-inspect-redacted','e1','--tenant-id','t']); assert p.returncode==0 and all(x not in p.stdout for x in ('hidden','urlTOKEN12345'))
def test_event_error_fails(server):
    p=run(server,['event-verify','e2','--tenant-id','t']); assert p.returncode==3 and json.loads(p.stdout)['verification']['reason']=='non_empty_error_message'
def test_malformed_input_json_error(server):
    p=run(server,['mutation-preview','--kind','rule','--resource-id','r','--tenant-id','t','--before-json','{','--after-json','{}','--idempotency-key','k']); assert p.returncode==2 and json.loads(p.stdout)['error']['code']=='invalid_input'
def test_broken_feature_guard(server):
    p=run(server,['mutation-preview','--kind','rule','--resource-id','r','--tenant-id','t','--before-json','{}','--after-json','{"tenant_id":"t","conditions":[{"operator":"gt"}]}','--idempotency-key','k']); assert p.returncode==2
def test_source_read_before_write_and_partial_detection(server):
    from cli_anything.clawpod_cloud_webhooks.core.contracts import preview, source_merge
    before=dict(STATE['source']); after=source_merge(before,{'is_active':False}); dg=preview('source','s1',before,after,'t','update-1')['effect_digest']
    p=run(server,['source-update','s1','--tenant-id','t','--changes-json','{"is_active":false}','--idempotency-key','update-1','--effect-digest',dg,'--approve'])
    assert p.returncode==0 and STATE['source']['playbook_id']=='p1'
    before=dict(STATE['source']); after=source_merge(before,{'is_active':True}); dg=preview('source','s1',before,after,'t','update-2')['effect_digest']; STATE['partial']=True
    p=run(server,['source-update','s1','--tenant-id','t','--changes-json','{"is_active":true}','--idempotency-key','update-2','--effect-digest',dg,'--approve']); STATE['partial']=False; STATE['source']['playbook_id']='p1'
    assert p.returncode==4 and json.loads(p.stdout)['partial_failure']
def test_secret_warning_redacted(server):
    p=run(server,['secret-action-warning','--action','regenerate','--metadata-json','{"signing_secret":"never","previous_secret_expires_at":"later"}']); assert 'never' not in p.stdout and 'may_remain_valid' in p.stdout

def test_manifest_adapter_command_parity():
    import importlib.util
    root=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','..'))
    manifest=json.load(open(os.path.join(root,'harness.json')))
    spec=importlib.util.spec_from_file_location('adapter',os.path.join(root,'clawpod_cloud_webhooks.py')); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    assert set(manifest['commands'])==set(mod.MAP)
    for name,contract in manifest['commands'].items():
        assert contract['inputSchema']['type']=='object' and isinstance(contract['argMap'],list) and contract['outputSchema']['required']==['ok']
    assert mod.MAP['secret.rotate-warning'][-1]=='rotate' and mod.MAP['secret.regenerate-warning'][-1]=='regenerate'
