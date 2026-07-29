import datetime, ipaddress, json, os, shutil, ssl, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from cli_anything.clawpod_cloud_webhooks.utils.backend import Backend, BackendError
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

PRIVATE_KEY=rsa.generate_private_key(public_exponent=65537,key_size=2048)
PUBLIC_PEM=PRIVATE_KEY.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
STATE={'source':{'id':'s1','name':'n','description':None,'provider':'custom','auth_type':'none','auth_config':{},'rate_limit_per_minute':10,'is_active':True,'playbook_id':'p1','tenant_id':'t'},'retry':0,'partial':False,'paths':[],'logins':0,'tenants':[{'id':'t','name':'Tenant'}],'identity_extra':{},'permissions':['webhook_manager'],'ca':None}
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
        if self.path.startswith('/api/proxy/auth/me'): return self.out({'authenticated':True,'email':'synthetic@example.invalid','tenants':STATE['tenants'],**STATE['identity_extra']})
        if '/webhook-sources/s1' in self.path: return self.out(dict(STATE['source']))
        if '/webhook-events/e1' in self.path: return self.out({'id':'e1','status':'delivered','error_message':'','headers':{'Authorization':'Bearer hidden','Cookie':'sid=hidden'},'request_url':'https://x/incoming/urlTOKEN12345','destination_evidence':{'message_id':'m'}})
        if '/webhook-events/e2' in self.path: return self.out({'id':'e2','status':'delivered','error_message':'tenant isolation violation'})
        if self.path.startswith('/api/proxy/webhook-sources'): return self.out([STATE['source']])
        if self.path.startswith('/api/proxy/webhook-'): return self.out({'items':[]})
        if self.path.startswith('/api/proxy/auth/permissions'): return self.out({'items':STATE['permissions']})
        return self.out({'error':'not found'},404)
    def do_POST(self):
        STATE['paths'].append(self.path); n=int(self.headers.get('Content-Length','0')); obj=json.loads(self.rfile.read(n))
        if self.path=='/api/auth/login':
            import base64
            assert set(obj)=={'email','password','rememberMe'} and obj['rememberMe'] is False
            assert 'encrypted_password' not in obj
            raw=PRIVATE_KEY.decrypt(base64.b64decode(obj['password']),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
            payload=json.loads(raw); assert payload['password']=='synthetic-password' and isinstance(payload['timestamp'],int) and obj['email']=='synthetic@example.invalid'
            STATE['logins']+=1; return self.out({'ok':True},headers={'Set-Cookie':'session=synthetic; HttpOnly'})
        return self.out({'error':'not found'},404)
    def do_PUT(self):
        STATE['paths'].append(self.path)
        n=int(self.headers.get('Content-Length','0')); obj=json.loads(self.rfile.read(n));
        if STATE['partial']: obj['playbook_id']=None
        STATE['source'].update(obj); self.out({'updated':True})
@pytest.fixture(scope='module')
def server(tmp_path_factory):
    root=tmp_path_factory.mktemp('tls'); key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'127.0.0.1')]); now=datetime.datetime.now(datetime.timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True).sign(key,hashes.SHA256()))
    ca=root/'ca.pem'; cert_file=root/'server.pem'; key_file=root/'server.key'
    pem=cert.public_bytes(serialization.Encoding.PEM); ca.write_bytes(pem); cert_file.write_bytes(pem); key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.TraditionalOpenSSL,serialization.NoEncryption()))
    STATE['ca']=str(ca); srv=ThreadingHTTPServer(('127.0.0.1',0),H); context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(cert_file,key_file); srv.socket=context.wrap_socket(srv.socket,server_side=True)
    th=threading.Thread(target=srv.serve_forever,daemon=True); th.start(); yield f'https://127.0.0.1:{srv.server_port}'; srv.shutdown()
@pytest.fixture(autouse=True)
def synthetic_auth(monkeypatch):
    monkeypatch.setenv('CLAWPOD_CLOUD_EMAIL','synthetic@example.invalid'); monkeypatch.setenv('CLAWPOD_CLOUD_PASSWORD','synthetic-password')
    STATE['tenants']=[{'id':'t','name':'Tenant'}]; STATE['identity_extra']={}; STATE['permissions']=['webhook_manager']; STATE['paths'].clear()

def cli_base():
    if os.getenv('CLI_ANYTHING_FORCE_INSTALLED')=='1':
        p=shutil.which('cli-anything-clawpod-cloud-webhooks')
        if p:return [p]
        raise RuntimeError('installed CLI missing')
    return [sys.executable,'-m','cli_anything.clawpod_cloud_webhooks.clawpod_cloud_webhooks_cli']
def run(server,args): return subprocess.run(cli_base()+['--base-url',server,'--ca-cert',STATE['ca'],'--json']+args,text=True,capture_output=True)

def test_tls_strict_default_rejects_untrusted_self_signed(server):
    STATE['paths'].clear()
    with pytest.raises(BackendError) as e: Backend(server,retries=0).request('GET','/retry',authenticated=False)
    assert e.value.code=='tls_verification_failed' and STATE['paths']==[]
def test_tls_custom_ca_and_insecure_approved_succeed(server):
    STATE['retry']=2; assert Backend(server,retries=0,ca_cert_path=STATE['ca']).request('GET','/retry',authenticated=False)['ok']
    assert Backend(server,retries=0,insecure_skip_tls_verify=True,insecure_risk_approved=True).request('GET','/retry',authenticated=False)['ok']
def test_tls_invalid_modes_fail_before_network(server,tmp_path):
    STATE['paths'].clear()
    with pytest.raises(ValueError): Backend(server,insecure_skip_tls_verify=True)
    with pytest.raises(ValueError): Backend(server,ca_cert_path=STATE['ca'],insecure_skip_tls_verify=True,insecure_risk_approved=True)
    with pytest.raises(ValueError): Backend('http://127.0.0.1:1',insecure_skip_tls_verify=True,insecure_risk_approved=True)
    bad=tmp_path/'bad.pem'; bad.write_text('not pem')
    with pytest.raises(ValueError) as e: Backend(server,ca_cert_path=str(bad))
    assert str(bad) not in str(e.value) and STATE['paths']==[]
def test_tls_cli_modes_and_no_path_leak(server,tmp_path):
    p=run(server,['system','version']); assert json.loads(p.stdout)['tls_verification_mode']=='custom_ca' and STATE['ca'] not in p.stdout
    p=subprocess.run(cli_base()+['--base-url',server,'--insecure-skip-tls-verify','--json','system','version'],text=True,capture_output=True); assert p.returncode==2 and STATE['paths']==[]
    p=subprocess.run(cli_base()+['--base-url',server,'--insecure-skip-tls-verify','--i-understand-insecure-tls-risk','--json','system','version'],text=True,capture_output=True); assert p.returncode==0 and json.loads(p.stdout)['tls_verification_mode']=='insecure_approved'

def test_backend_retries_get(server): STATE['retry']=0; assert Backend(server,retries=2,ca_cert_path=STATE['ca']).request('GET','/retry',authenticated=False)['ok'] and STATE['retry']==3
def test_auth_failure_typed_and_no_body_leak(server):
    with pytest.raises(BackendError) as e: Backend(server,retries=0,ca_cert_path=STATE['ca']).request('GET','/authfail',authenticated=False)
    assert e.value.code=='auth_failed' and 'should-never-emit' not in str(e.value)
def test_bounded_timeout_and_retry_safety(server):
    with pytest.raises(BackendError) as e: Backend(server,timeout=.03,retries=0,ca_cert_path=STATE['ca']).request('GET','/slow',authenticated=False)
    assert e.value.code=='timeout' and e.value.retry_safe
def test_subprocess_version_from_outside(server,tmp_path):
    p=run(server,['system','version']); d=json.loads(p.stdout); assert p.returncode==0 and d['capability']['name']=='clawpod-cloud-webhooks'
def test_typed_reads(server):
    for args in (['permissions','list','--tenant-id','t'],['presets','list','--tenant-id','t'],['source','get','s1','--tenant-id','t'],['playbook','list','--tenant-id','t'],['rule','list','--tenant-id','t'],['event','list','--tenant-id','t']):
        p=run(server,args); assert p.returncode==0, p.stderr
def test_auth_contract(server):
    d=json.loads(run(server,['auth','contract']).stdout)
    assert d['login']['algorithm']=='RSA-OAEP' and d['onboarding_requires_explicit_approval']
    assert d['login']['login_request_fields']==['email','password','rememberMe']
    assert d['login']['encrypted_field']=='password' and d['login']['remember_me'] is False
    assert d['onboarding']['required_account']=='ClawPod Cloud TA account or an account with Webhook Manager permission'
    assert d['onboarding']['installation_is_connection'] is False
    handoff=d['onboarding']['post_install_handoff']
    assert handoff['required'] and handoff['installation_complete_without_handoff'] is False
    assert 'Immediately after installation' in handoff['timing']
    assert len(handoff['contents'])==5 and 'Ask whether to start onboarding now.' in handoff['contents']
    assert 'blocker' in d['onboarding']['missing_permission_behavior']
    assert d['onboarding_prompts']['base_url']['ask_proactively']
    assert d['onboarding_prompts']['account_identifier_and_prerequisite']['ask_proactively']
    assert d['onboarding_prompts']['protected_credential']['ask_in_chat'] is False
    assert d['onboarding_prompts']['protected_credential']['accept_from_chat'] is False
    assert d['onboarding_prompts']['user_runs_commands'] is False
    assert d['protected_credential_contract']['gateway_harness_run_injection_supported'] is False
    assert 'protected credential pointers' in d['blockers']['missing_credential']
    assert d['tls']['default']=='strict' and d['tls']['http_rejected']
    assert 'both --insecure-skip-tls-verify and --i-understand-insecure-tls-risk' in d['tls']['insecure']
def test_onboard_requires_explicit_login_approval_before_network(server):
    STATE['paths'].clear()
    p=run(server,['auth','onboard']); d=json.loads(p.stdout)
    assert p.returncode==2 and d['error']['code']=='invalid_input'
    assert STATE['paths']==[]
def test_onboard_requires_protected_secret_injection(server):
    env=os.environ.copy(); env.pop('CLAWPOD_CLOUD_EMAIL',None); env.pop('CLAWPOD_CLOUD_PASSWORD',None)
    p=subprocess.run(cli_base()+['--base-url',server,'--ca-cert',STATE['ca'],'--json','auth','onboard','--approve-login'],text=True,capture_output=True,env=env)
    assert p.returncode==2 and json.loads(p.stdout)['error']['code']=='auth_required'
    assert 'synthetic-password' not in p.stdout

def test_onboard_success_auto_selects_and_never_mutates(server):
    p=run(server,['auth','onboard','--approve-login']); d=json.loads(p.stdout)
    assert p.returncode==0 and d['tenant']['id']=='t' and d['mutation_attempted'] is False
    assert d['permission_source']=='permissions_endpoint'
    assert not any(path.startswith('/api/proxy/webhook-') for path in STATE['paths'])
def test_onboard_live_identity_contract_uses_active_tenant_and_policy_actions(server):
    STATE['tenants']=[]; STATE['identity_extra']={'activeTenantId':'active-t','role':'member','tenantRole':'member','policyActions':['webhooks.read','webhooks.manage']}
    p=run(server,['auth','onboard','--approve-login']); d=json.loads(p.stdout)
    assert p.returncode==0 and d['tenant']['id']=='active-t' and d['permission_source']=='identity_policy_actions'
    assert d['mutation_attempted'] is False and not any('permissions' in path or path.startswith('/api/proxy/webhook-') for path in STATE['paths'])
def test_onboard_live_tenant_admin_role_needs_no_permissions_fallback(server):
    STATE['tenants']=[]; STATE['identity_extra']={'activeTenantId':'active-t','tenantRole':'TA','policyActions':[]}
    p=run(server,['auth','onboard','--approve-login']); d=json.loads(p.stdout)
    assert p.returncode==0 and d['permission_source']=='identity_role'
    assert not any('permissions' in path or path.startswith('/api/proxy/webhook-') for path in STATE['paths'])
def test_onboard_explicit_active_tenant_match_and_mismatch(server):
    STATE['tenants']=[]; STATE['identity_extra']={'activeTenantId':'active-t','role':'tenant_admin'}
    p=run(server,['auth','onboard','--approve-login','--tenant-id','active-t']); assert p.returncode==0
    STATE['paths'].clear(); p=run(server,['auth','onboard','--approve-login','--tenant-id','other']); d=json.loads(p.stdout)
    assert p.returncode==2 and d['error']['code']=='tenant_not_available'
    assert not any('permissions' in path or path.startswith('/api/proxy/webhook-') for path in STATE['paths'])
def test_onboard_sole_legacy_tenant_precedes_different_active_context(server):
    STATE['identity_extra']={'activeTenantId':'active-t','role':'tenant_admin'}
    p=run(server,['auth','onboard','--approve-login']); assert json.loads(p.stdout)['tenant']['id']=='t'
def test_onboard_ambiguous_legacy_tenants_stay_blocked_despite_active_context(server):
    STATE['tenants']=[{'id':'t1','name':'One'},{'id':'t2','name':'Two'}]; STATE['identity_extra']={'activeTenantId':'t1','role':'tenant_admin'}
    p=run(server,['auth','onboard','--approve-login']); d=json.loads(p.stdout)
    assert p.returncode==2 and d['error']['code']=='ambiguous_tenant' and d['mutation_attempted'] is False
    assert not any('permissions' in path or path.startswith('/api/proxy/webhook-') for path in STATE['paths'])
    STATE['paths'].clear(); p=run(server,['auth','onboard','--approve-login','--tenant-id','t2']); d=json.loads(p.stdout)
    assert p.returncode==0 and d['tenant']['id']=='t2' and d['mutation_attempted'] is False
    assert not any('permissions' in path or path.startswith('/api/proxy/webhook-') for path in STATE['paths'])
def test_onboard_missing_permission_is_typed_and_redacted(server):
    STATE['permissions']=['read']; p=run(server,['auth','onboard','--approve-login']); d=json.loads(p.stdout)
    assert p.returncode==2 and d['error']['code']=='missing_permission' and 'synthetic-password' not in p.stdout

def test_onboard_incomplete_live_policy_actions_fall_back_and_block(server):
    STATE['tenants']=[]; STATE['identity_extra']={'activeTenantId':'active-t','policyActions':['webhooks.read']}; STATE['permissions']=[]
    p=run(server,['auth','onboard','--approve-login']); d=json.loads(p.stdout)
    assert p.returncode==2 and d['error']['code']=='missing_permission'
    assert '/api/proxy/auth/permissions?tenant_id=active-t' in STATE['paths']
    assert not any(path.startswith('/api/proxy/webhook-') for path in STATE['paths'])
def test_rsa_login_and_real_proxy_paths(server):
    STATE['paths'].clear(); STATE['logins']=0
    p=run(server,['source','list','--tenant-id','t']); assert p.returncode==0 and STATE['logins']==1
    assert STATE['paths'][:3]==['/api/auth/public-key','/api/auth/login','/api/proxy/webhook-sources?tenant_id=t']
def test_missing_protected_env_fails_but_no_auth_commands_work(server):
    env=os.environ.copy(); env.pop('CLAWPOD_CLOUD_EMAIL',None); env.pop('CLAWPOD_CLOUD_PASSWORD',None)
    p=subprocess.run(cli_base()+['--base-url',server,'--ca-cert',STATE['ca'],'--json','source','list','--tenant-id','t'],text=True,capture_output=True,env=env)
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
    allowed={'readOnly','writeSafe','modifiesSource','destructive','secretUse','externalSideEffect','authReuse','humanAccountAction'}
    for name,contract in manifest['commands'].items():
        assert contract['inputSchema']['type']=='object' and isinstance(contract['argMap'],list) and contract['outputSchema']['required']==['ok']
        assert set(contract['safetyClasses']) <= allowed
        if 'baseUrl' in contract['inputSchema'].get('properties',{}):
            props=contract['inputSchema']['properties']; args={a['arg']:a for a in contract['argMap']}
            assert {'caCertPath','insecureSkipTlsVerify','insecureTlsRiskAccepted'} <= set(props)
            assert args['caCertPath']['valueType']=='path' and args['caCertPath']['pathRole']=='input'
    assert {'secretUse','humanAccountAction'} <= set(manifest['commands']['auth.onboard']['safetyClasses'])
    assert mod.MAP['secret.rotate-warning'][-1]=='rotate' and mod.MAP['secret.regenerate-warning'][-1]=='regenerate'
