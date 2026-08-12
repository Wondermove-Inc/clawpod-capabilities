import hashlib, hmac, json, re, shlex, sys
from urllib.parse import quote
import click
from . import __version__
from .core.contracts import create_preview, delete_preview, preview, readback_mismatches, require_idempotency, resource_merge, secret_warning, validate_payload, verify_event
from .core.safety import digest, redact, validate_body
from .core.lifecycle import MAX_PLAN_BYTES, execute_plan
from .utils.backend import Backend, BackendError, RSA_CONTRACT

class State:
    def __init__(self, base_url, timeout, retries, json_mode, ca_cert_path, insecure_skip_tls_verify, insecure_risk_approved):
        self.backend=Backend(base_url,timeout,retries,ca_cert_path,insecure_skip_tls_verify,insecure_risk_approved); self.json=json_mode

_ACTIVE_TLS_MODE = "strict"
def emit(obj):
    if isinstance(obj,dict) and "tls_verification_mode" not in obj: obj={**obj,"tls_verification_mode":_ACTIVE_TLS_MODE}
    click.echo(json.dumps(redact(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False))
def parse(s,label="JSON"):
    try: return json.loads(s)
    except Exception as e: raise click.ClickException(f"malformed {label}: {e}")
def api(state, method, path, **kw): return state.backend.request(method,path,**kw)
def path_id(value): return quote(str(value),safe='')
def tenant_query(value): return '?tenant_id='+quote(str(value),safe='')

def guarded(fn):
    def run(*a,**kw):
        try: return fn(*a,**kw)
        except BackendError as e:
            emit({"ok":False,"error":{"code":e.code,"message":str(e),"retry_safe":e.retry_safe,"status":e.status}}); raise click.exceptions.Exit(2)
        except (ValueError,click.ClickException) as e:
            emit({"ok":False,"error":{"code":"invalid_input","message":str(e),"retry_safe":False}}); raise click.exceptions.Exit(2)
    run.__name__=fn.__name__; return run

@click.group(invoke_without_command=True)
@click.option('--base-url',envvar='CLAWPOD_WEBHOOKS_BASE_URL',default='https://127.0.0.1:8765',show_default=True)
@click.option('--timeout',type=float,default=5.0,show_default=True)
@click.option('--retries',type=click.IntRange(0,3),default=2,show_default=True)
@click.option('--ca-cert','ca_cert_path',type=click.Path(path_type=str),help='Readable PEM CA file for this process only.')
@click.option('--insecure-skip-tls-verify',is_flag=True,help='Disable certificate verification for an approved internal network only.')
@click.option('--i-understand-insecure-tls-risk','insecure_risk_approved',is_flag=True,help='Required second affirmation accepting insecure TLS risk.')
@click.option('--json','json_mode',is_flag=True,help='Emit deterministic JSON.')
@click.pass_context
def cli(ctx,base_url,timeout,retries,ca_cert_path,insecure_skip_tls_verify,insecure_risk_approved,json_mode):
    """ClawPod Cloud Webhooks, safe portal/API CLI."""
    global _ACTIVE_TLS_MODE
    try:
        ctx.obj=State(base_url,timeout,retries,json_mode,ca_cert_path,insecure_skip_tls_verify,insecure_risk_approved)
        _ACTIVE_TLS_MODE=ctx.obj.backend.tls_verification_mode
    except ValueError as e:
        emit({"ok":False,"error":{"code":"invalid_input","message":str(e),"retry_safe":False}}); raise click.exceptions.Exit(2)
    if ctx.invoked_subcommand is None: ctx.invoke(repl)

@cli.command()
@click.pass_context
def repl(ctx):
    """Stateful in-memory session REPL; cookies never persist to disk."""
    if not sys.stdin.isatty(): emit({"ok":False,"error":{"code":"tty_required","message":"REPL requires a TTY"}}); return
    click.echo('ClawPod Cloud Webhooks REPL. Use one-shot commands for automation; type exit.')
    while True:
        try: line=click.prompt('webhooks',prompt_suffix='> ')
        except (EOFError,KeyboardInterrupt): break
        if line.strip() in ('exit','quit'): break
        click.echo('REPL accepts status only; use one-shot commands for mutation safety.' if line.strip()!='status' else json.dumps(ctx.obj.backend.session_status(),sort_keys=True))

@cli.group()
def system(): pass
@system.command('version')
@guarded
def system_version(): emit({"ok":True,"capability":{"name":"clawpod-cloud-webhooks","title":"ClawPod Cloud Webhooks","version":__version__},"backend":"real HTTP client"})

@cli.group()
def auth(): pass
@auth.command('contract')
def auth_contract():
    emit({
        "ok":True,
        "login":RSA_CONTRACT,
        "onboarding_requires_explicit_approval":True,
        "onboarding_prompts":{"base_url":{"ask_proactively":True,"chat_safe":True,"required":True},"account_identifier_and_prerequisite":{"ask_proactively":True,"chat_safe":True,"required":True},"protected_credential":{"ask_in_chat":False,"accept_from_chat":False,"channel":"protected secret input/storage only","search_existing_pointers_first":True},"user_runs_commands":False,"user_configures_environment":False},
        "user_actions":["Supply the ClawPod Cloud base URL and non-secret account identifier/prerequisite when asked.","Provide password or token only through a protected secret channel.","Approve credential use and login.","Choose or approve a tenant only when more than one is available.","Complete unavoidable MFA or provider UI."],
        "agent_actions":["Search protected secret pointers before requesting credentials.","Store newly supplied credentials in protected secret storage.","Validate the HTTPS base URL and account prerequisite.","Inject secrets only into the approved onboarding process.","Perform RSA-OAEP login, identity, tenant, and permission readback.","Auto-select the sole tenant and stop before every mutation."],
        "protected_credential_contract":{"required_environment":["CLAWPOD_CLOUD_EMAIL","CLAWPOD_CLOUD_PASSWORD"],"plaintext_chat":False,"process_only":True,"gateway_harness_run_injection_supported":True,"gateway_parameter":"secretRefs","per_run_binding":True,"prepare_run_binding_must_match":True,"manifest_stores_pointer":False,"approved_execution_lane":"Gateway prepare and run with identical owner-scoped secretRefs","session_persistence":False},
        "tls":{"default":"strict","custom_ca":"preferred for internal CA trust; readable PEM used only by this process and never persisted","insecure":"internal networks only; requires both --insecure-skip-tls-verify and --i-understand-insecure-tls-risk","http_rejected":True,"modes":["strict","custom_ca","insecure_approved"]},
        "approval_boundaries":{"credential_storage":"explicit approval","credential_use_and_login":"explicit approval","insecure_tls":"separate explicit risk acceptance","tenant_selection":"user approval only when ambiguous","mutation":"separate preview and execution approvals"},
        "success_criteria":["authenticated identity read back","exactly one tenant selected or approved","Webhook Manager permission verified","session remains process-memory-only","no mutation attempted"],
        "blockers":{"missing_credential":"Search protected credential pointers, then request protected-channel provision.","ambiguous_tenant":"Return redacted tenant choices and wait for target approval.","mfa_required":"Return mfa_required and wait for unavoidable provider interaction.","missing_permission":"Stop and request TA/Webhook Manager access.","auth_failed":"Stop; verify account or revoke/replace the protected secret.","backend_error":"Stop with retry safety and preserve no session."},
        "onboarding":{
            "required_account":"ClawPod Cloud TA account or an account with Webhook Manager permission",
            "installation_is_connection":False,
            "post_install_handoff":{
                "timing":"Immediately after installation, before waiting for first use.",
                "required":True,
                "installation_complete_without_handoff":False,
                "contents":[
                    "State that installation succeeded but the capability is not connected.",
                    "Explain the required TA account or Webhook Manager permission.",
                    "Explain the approval-gated onboarding sequence and user-versus-agent actions.",
                    "Explain protected credential and session handling and how access can be revoked.",
                    "Ask whether to start onboarding now."
                ]
            },
            "pre_login_check":"Confirm the account type or Webhook Manager permission before starting login or creating credential state.",
            "post_login_check":"Read back the authenticated identity, selected tenant, and Webhooks permissions before declaring the capability connected.",
            "missing_permission_behavior":"Stop without mutation and report the missing TA/Webhook Manager access as a blocker."
        }
    })
def _permission_name(value):
    if isinstance(value,dict): value=value.get('name') or value.get('code') or value.get('action') or ''
    return str(value)

def _normalized_permission(value): return re.sub(r'[^a-z0-9]+','_',_permission_name(value).lower()).strip('_')
def _is_tenant_admin(value): return _normalized_permission(value) in ('ta','tenant_admin','tenantadmin')
def _policy_allows_webhook_management(actions):
    names=[_normalized_permission(action) for action in actions if _permission_name(action)]
    has_manage=any('webhook' in name and any(word in name for word in ('manage','manager','write','admin','create','update','delete')) for name in names)
    has_read=any('webhook' in name and any(word in name for word in ('read','view','list')) for name in names)
    return has_manage and has_read

def _legacy_permission_allows(values):
    names=[_permission_name(value) for value in values]
    return names, any(('webhook' in name.lower() and ('manage' in name.lower() or 'manager' in name.lower())) or _is_tenant_admin(name) for name in names)

@auth.command('onboard')
@click.option('--tenant-id')
@click.option('--approve-login',is_flag=True)
@click.pass_obj
@guarded
def auth_onboard(state,tenant_id,approve_login):
    """Login, verify identity/tenant/permission, then stop before mutation."""
    if not approve_login: raise ValueError('explicit credential-use and login approval is required')
    identity=api(state,'GET','/api/proxy/auth/me')
    if not isinstance(identity,dict): identity={}
    tenants=identity.get('tenants',[])
    if not isinstance(tenants,list): tenants=[]
    normalized=[{"id":str(t.get('id')),"name":t.get('name')} for t in tenants if isinstance(t,dict) and t.get('id')]
    active_tenant_id=identity.get('activeTenantId')
    active_tenant_id=str(active_tenant_id).strip() if isinstance(active_tenant_id,(str,int)) and not isinstance(active_tenant_id,bool) and str(active_tenant_id).strip() else None
    if tenant_id:
        selected=next((t for t in normalized if t['id']==tenant_id),None)
        if not selected and active_tenant_id==tenant_id: selected={"id":active_tenant_id,"name":None}
        if not selected: raise BackendError('tenant_not_available','approved tenant is not available to this account',False)
    elif len(normalized)==1: selected=normalized[0]
    elif len(normalized)>1:
        emit({'ok':False,'error':{'code':'ambiguous_tenant','message':'multiple tenants are available; approve one tenant id','retry_safe':True},'tenants':normalized,'mutation_attempted':False})
        raise click.exceptions.Exit(2)
    elif active_tenant_id: selected={"id":active_tenant_id,"name":None}
    else: raise BackendError('tenant_not_available','authenticated identity returned no available tenant',False)

    role_allowed=any(_is_tenant_admin(identity.get(field,'')) for field in ('role','tenantRole'))
    policy_actions=identity.get('policyActions',[])
    policy_allowed=_policy_allows_webhook_management(policy_actions if isinstance(policy_actions,list) else [])
    names=[]
    permission_source='identity_role' if role_allowed else 'identity_policy_actions' if policy_allowed else 'permissions_endpoint'
    if not (role_allowed or policy_allowed):
        permissions=api(state,'GET','/api/proxy/auth/permissions?tenant_id='+selected['id'])
        raw=permissions.get('items',permissions.get('permissions',[])) if isinstance(permissions,dict) else permissions
        names,allowed=_legacy_permission_allows(raw if isinstance(raw,list) else [])
        if not allowed: raise BackendError('missing_permission','TA or Webhook Manager permission is required',False,403)
    else:
        names=[_permission_name(action) for action in policy_actions] if policy_allowed else [str(identity.get('tenantRole') or identity.get('role'))]
    local=state.backend.session_status()
    emit({'ok':True,'connected':True,'identity':identity,'tenant':selected,'permissions':names,'permission_source':permission_source,'session':{'storage':local['session_storage'],'persistent':False,'sensitive_values_exposed':False},'mutation_attempted':False,'next':'separate approval is required before any mutation','revocation':{'portal':'Revoke account access or change the account password.','local':'End the process; no session is persisted. Run portal logout when available.'}})
@auth.command('status')
@click.pass_obj
@guarded
def auth_status(state):
    remote=api(state,'GET','/api/proxy/auth/me'); local=state.backend.session_status()
    emit({"ok":True,"remote":remote,"local":{"connected":local["connected"],"protected_session":True,"sensitive_values_exposed":False}})

READS={'permissions':'/api/proxy/auth/permissions','presets':'/api/proxy/webhook-presets','source':'/api/proxy/webhook-sources','playbook':'/api/proxy/webhook-playbooks','rule':'/api/proxy/webhook-rules','event':'/api/proxy/webhook-events'}
RESOURCE_PATHS={k:READS[k] for k in ('source','playbook','rule')}
def _items(value):
    if isinstance(value,list): return value
    if isinstance(value,dict) and isinstance(value.get('items'),list): return value['items']
    raise ValueError('list response must be an array or an object containing items')
def _changed_fields(kind, expected, actual):
    return readback_mismatches(kind, expected, actual)
def _created_id(kind,result):
    if not isinstance(result,dict): return None
    for value in (result,result.get(kind),result.get('data')):
        if isinstance(value,dict) and value.get('id') is not None: return str(value['id'])
    return None
def _mutation_output(operation,effect_digest,result,readback,mismatches=None):
    ok=not mismatches
    emit({'ok':ok,'operation':operation,'effect_digest':effect_digest,'verified':ok,'result':result,'readback':readback,'verification_mismatches':mismatches or {},'retry_safe':None if ok else False,'partial_failure':not ok})
    if not ok: raise click.exceptions.Exit(4)
def _approved(approve):
    if not approve: raise ValueError('explicit execution approval is required')

def add_read_group(name,path):
    g=click.Group(name=name)
    @click.command('list')
    @click.option('--tenant-id',required=True)
    @click.pass_obj
    @guarded
    def list_cmd(state,tenant_id): emit({"ok":True,"kind":name,"items":api(state,'GET',path+tenant_query(tenant_id))})
    @click.command('get')
    @click.argument('resource_id')
    @click.option('--tenant-id',required=True)
    @click.pass_obj
    @guarded
    def get_cmd(state,resource_id,tenant_id): emit({"ok":True,"kind":name,"item":api(state,'GET',path+'/'+path_id(resource_id)+tenant_query(tenant_id))})
    g.add_command(list_cmd); g.add_command(get_cmd)
    if name in RESOURCE_PATHS:
        @click.command('create')
        @click.option('--tenant-id',required=True)
        @click.option('--payload-json',required=True)
        @click.option('--idempotency-key',required=True)
        @click.option('--effect-digest',required=True)
        @click.option('--approve',is_flag=True)
        @click.pass_obj
        @guarded
        def create_cmd(state,tenant_id,payload_json,idempotency_key,effect_digest,approve,_name=name,_path=path):
            _approved(approve); payload=validate_payload(_name,parse(payload_json),tenant_id)
            p=create_preview(_name,payload,tenant_id,idempotency_key)
            if p['effect_digest']!=effect_digest: raise ValueError('effect digest mismatch; re-preview create payload')
            result=api(state,'POST',_path,body=payload,idempotency=idempotency_key)
            resource_id=_created_id(_name,result)
            if not resource_id: raise BackendError('verification_failed','create response omitted resource id; reconcile before retry',False)
            readback=api(state,'GET',f'{_path}/{path_id(resource_id)}{tenant_query(tenant_id)}')
            _mutation_output(f'{_name}.create',effect_digest,result,readback,_changed_fields(_name,payload,readback))
        @click.command('update')
        @click.argument('resource_id')
        @click.option('--tenant-id',required=True)
        @click.option('--changes-json',required=True)
        @click.option('--idempotency-key',required=True)
        @click.option('--effect-digest',required=True)
        @click.option('--approve',is_flag=True)
        @click.pass_obj
        @guarded
        def update_cmd(state,resource_id,tenant_id,changes_json,idempotency_key,effect_digest,approve,_name=name,_path=path):
            _approved(approve); before=api(state,'GET',f'{_path}/{path_id(resource_id)}{tenant_query(tenant_id)}')
            after=resource_merge(_name,before,parse(changes_json)); p=preview(_name,resource_id,before,after,tenant_id,idempotency_key)
            if p['effect_digest']!=effect_digest: raise ValueError(f'effect digest mismatch; re-preview current {_name.title()}')
            result=api(state,'PUT',f'{_path}/{path_id(resource_id)}',body=after,idempotency=idempotency_key)
            readback=api(state,'GET',f'{_path}/{path_id(resource_id)}{tenant_query(tenant_id)}')
            _mutation_output(f'{_name}.update',effect_digest,result,readback,_changed_fields(_name,after,readback))
        @click.command('delete')
        @click.argument('resource_id')
        @click.option('--tenant-id',required=True)
        @click.option('--idempotency-key',required=True)
        @click.option('--effect-digest',required=True)
        @click.option('--approve',is_flag=True)
        @click.pass_obj
        @guarded
        def delete_cmd(state,resource_id,tenant_id,idempotency_key,effect_digest,approve,_name=name,_path=path):
            _approved(approve); before=api(state,'GET',f'{_path}/{path_id(resource_id)}{tenant_query(tenant_id)}')
            p=delete_preview(_name,resource_id,before,tenant_id,idempotency_key)
            if p['effect_digest']!=effect_digest: raise ValueError(f'effect digest mismatch; re-preview current {_name.title()}')
            result=api(state,'DELETE',f'{_path}/{path_id(resource_id)}',idempotency=idempotency_key)
            # Verify the exact item, not a possibly paginated collection page.
            try:
                api(state,'GET',f'{_path}/{path_id(resource_id)}{tenant_query(tenant_id)}')
                present=True
            except BackendError as exc:
                if exc.status==404 or exc.code=='not_found': present=False
                else: raise
            _mutation_output(f'{_name}.delete',effect_digest,result,{'absent':not present},{'resource_id':{'expected':'absent','actual':'present'}} if present else {})
        g.add_command(create_cmd); g.add_command(update_cmd); g.add_command(delete_cmd)
    cli.add_command(g)
for _n,_p in READS.items(): add_read_group(_n,_p)

@cli.command('event-inspect-redacted')
@click.argument('event_id')
@click.option('--tenant-id',required=True)
@click.pass_obj
@guarded
def event_inspect(state,event_id,tenant_id): emit({"ok":True,"event":redact(api(state,'GET','/api/proxy/webhook-events/'+path_id(event_id)+tenant_query(tenant_id)))})

@cli.command('event-verify')
@click.argument('event_id')
@click.option('--tenant-id',required=True)
@click.option('--require-destination-evidence',is_flag=True)
@click.pass_obj
@guarded
def event_verify(state,event_id,tenant_id,require_destination_evidence):
    e=api(state,'GET','/api/proxy/webhook-events/'+path_id(event_id)+tenant_query(tenant_id)); v=verify_event(e,require_destination_evidence); emit({"ok":v['ok'],"verification":v,"event":redact(e)})
    if not v['ok']: raise click.exceptions.Exit(3)

@cli.command('audit-config')
@click.option('--tenant-id',required=True)
@click.pass_obj
@guarded
def audit_config(state,tenant_id):
    sources=api(state,'GET','/api/proxy/webhook-sources?tenant_id='+tenant_id); rules=api(state,'GET','/api/proxy/webhook-rules?tenant_id='+tenant_id)
    findings=[]
    for r in rules if isinstance(rules,list) else rules.get('items',[]):
        if r.get('message_template'): findings.append({'severity':'error','rule_id':r.get('id'),'code':'broken_message_template'})
        for c in r.get('conditions',[]) or []:
            if c.get('operator') in {'in','not_in','gt','lt','gte','lte'}: findings.append({'severity':'error','rule_id':r.get('id'),'code':'broken_operator','operator':c.get('operator')})
        if any(t.get('type')=='agent' for t in r.get('targets',[]) if isinstance(t,dict)): findings.append({'severity':'error','rule_id':r.get('id'),'code':'agent_delivery_unproven'})
    emit({'ok':not any(f['severity']=='error' for f in findings),'tenant_id':tenant_id,'source_count':len(sources if isinstance(sources,list) else sources.get('items',[])),'findings':findings})

@cli.command('mutation-preview')
@click.option('--kind',type=click.Choice(['source','playbook','rule']),required=True)
@click.option('--action',type=click.Choice(['create','update','delete','action']),default='update',show_default=True)
@click.option('--resource-id',default='(new)',show_default=True)
@click.option('--tenant-id',required=True)
@click.option('--before-json',default='{}')
@click.option('--after-json',default='{}')
@click.option('--idempotency-key',required=True)
@guarded
def mutation_preview(kind,action,resource_id,tenant_id,before_json,after_json,idempotency_key):
    before=parse(before_json); after=parse(after_json)
    if action=='create': value=create_preview(kind,validate_payload(kind,after,tenant_id),tenant_id,idempotency_key)
    elif action=='delete': value=delete_preview(kind,resource_id,before,tenant_id,idempotency_key)
    else: value=preview(kind,resource_id,before,after,tenant_id,idempotency_key)
    emit({'ok':True,'preview':value})

@cli.command('source-update',hidden=True)
@click.argument('source_id')
@click.option('--tenant-id',required=True)
@click.option('--changes-json',required=True)
@click.option('--idempotency-key',required=True)
@click.option('--effect-digest',required=True)
@click.option('--approve',is_flag=True,required=True)
@click.pass_obj
@guarded
def source_update(state,source_id,tenant_id,changes_json,idempotency_key,effect_digest,approve):
    ctx=click.get_current_context(); return ctx.invoke(cli.commands['source'].commands['update'],resource_id=source_id,tenant_id=tenant_id,changes_json=changes_json,idempotency_key=idempotency_key,effect_digest=effect_digest,approve=approve)

def _state_action(state,kind,resource_id,tenant_id,enabled,idempotency_key,effect_digest,approve):
    _approved(approve); path=RESOURCE_PATHS[kind]; before=api(state,'GET',f'{path}/{path_id(resource_id)}{tenant_query(tenant_id)}')
    after=resource_merge(kind,before,{'is_active':enabled}); p=preview(kind,resource_id,before,after,tenant_id,idempotency_key)
    if p['effect_digest']!=effect_digest: raise ValueError(f'effect digest mismatch; re-preview current {kind.title()}')
    result=api(state,'PUT',f'{path}/{path_id(resource_id)}',body=after,idempotency=idempotency_key)
    readback=api(state,'GET',f'{path}/{path_id(resource_id)}{tenant_query(tenant_id)}')
    _mutation_output(f'{kind}.{"enable" if enabled else "disable"}',effect_digest,result,readback,_changed_fields(kind,after,readback))

def _add_state_command(kind,enabled):
    command_name=f'{kind}-{"enable" if enabled else "disable"}'
    @click.command(command_name)
    @click.argument('resource_id')
    @click.option('--tenant-id',required=True)
    @click.option('--idempotency-key',required=True)
    @click.option('--effect-digest',required=True)
    @click.option('--approve',is_flag=True)
    @click.pass_obj
    @guarded
    def command(state,resource_id,tenant_id,idempotency_key,effect_digest,approve):
        return _state_action(state,kind,resource_id,tenant_id,enabled,idempotency_key,effect_digest,approve)
    cli.add_command(command)
for _kind in ('source','rule'):
    _add_state_command(_kind,True); _add_state_command(_kind,False)

@cli.command('rule-reorder')
@click.argument('rule_id')
@click.option('--tenant-id',required=True)
@click.option('--priority',type=int,required=True)
@click.option('--idempotency-key',required=True)
@click.option('--effect-digest',required=True)
@click.option('--approve',is_flag=True)
@click.pass_obj
@guarded
def rule_reorder(state,rule_id,tenant_id,priority,idempotency_key,effect_digest,approve):
    _approved(approve); path=RESOURCE_PATHS['rule']; before=api(state,'GET',f'{path}/{path_id(rule_id)}{tenant_query(tenant_id)}')
    after=resource_merge('rule',before,{'priority':priority}); p=preview('rule',rule_id,before,after,tenant_id,idempotency_key)
    if p['effect_digest']!=effect_digest: raise ValueError('effect digest mismatch; re-preview current Rule')
    result=api(state,'PUT',f'{path}/{path_id(rule_id)}',body=after,idempotency=idempotency_key)
    readback=api(state,'GET',f'{path}/{path_id(rule_id)}{tenant_query(tenant_id)}')
    _mutation_output('rule.reorder',effect_digest,result,readback,_changed_fields('rule',after,readback))

def _add_secret_command(action,route):
    @click.command('source-'+action)
    @click.argument('source_id')
    @click.option('--tenant-id',required=True)
    @click.option('--idempotency-key',required=True)
    @click.option('--effect-digest',required=True)
    @click.option('--approve',is_flag=True)
    @click.pass_obj
    @guarded
    def command(state,source_id,tenant_id,idempotency_key,effect_digest,approve):
        _approved(approve); path=RESOURCE_PATHS['source']; before=api(state,'GET',f'{path}/{path_id(source_id)}{tenant_query(tenant_id)}')
        after={**before,'secret_action':action}; p=preview('source',source_id,before,after,tenant_id,idempotency_key)
        if p['effect_digest']!=effect_digest: raise ValueError('effect digest mismatch; re-preview current Source secret action')
        result=api(state,'POST',f'{path}/{path_id(source_id)}/{route}',idempotency=idempotency_key)
        readback=api(state,'GET',f'{path}/{path_id(source_id)}{tenant_query(tenant_id)}')
        candidates=(result,result.get('source'),result.get('data')) if isinstance(result,dict) else ()
        acknowledged=any(isinstance(value,dict) and any(key in value for key in ('signing_secret','signingSecret','secret')) for value in candidates)
        lifecycle=secret_warning(readback,'rotate' if action=='rotate-secret' else action)
        mismatches={} if acknowledged else {'action_response':{'expected':'new secret acknowledgement','actual':'missing'}}
        emit({'ok':acknowledged,'operation':f'source.{action}','effect_digest':effect_digest,'verified':acknowledged,'result':result,'readback':readback,'verification_mismatches':mismatches,'credential_lifecycle':lifecycle,'secret_exposed':False,'retry_safe':None if acknowledged else False,'partial_failure':not acknowledged})
        if not acknowledged: raise click.exceptions.Exit(4)
    cli.add_command(command)
_add_secret_command('rotate-secret','rotate-secret')
_add_secret_command('regenerate','regenerate')

@cli.command('source-test-local')
@click.option('--body-file',type=click.Path(exists=True,dir_okay=False),required=True)
@click.option('--idempotency-key',required=True)
@click.option('--signing-secret-env',default='CLAWPOD_WEBHOOK_SIGNING_SECRET',show_default=True)
@guarded
def source_test_local(body_file,idempotency_key,signing_secret_env):
    import os
    require_idempotency(idempotency_key); body=open(body_file,'rb').read(); validate_body(body); secret=os.environ.get(signing_secret_env)
    if not secret: raise ValueError('signing secret must be injected through the protected environment')
    hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    emit({'ok':True,'body_bytes':len(body),'body_digest':'sha256:'+hashlib.sha256(body).hexdigest(),'signature_generated':True,'signature_exposed':False,'idempotency_key':idempotency_key})

@cli.command('secret-action-warning')
@click.option('--action',type=click.Choice(['rotate','regenerate']),required=True)
@click.option('--metadata-json',default='{}')
@guarded
def secret_action_warning(action,metadata_json): emit({'ok':True,'credential_lifecycle':secret_warning(parse(metadata_json),action)})

@cli.group()
def lifecycle():
    """Execute a bounded plan in one authenticated in-memory session."""

@lifecycle.command('execute')
@click.option('--plan-json',required=True)
@click.pass_obj
@guarded
def lifecycle_execute(state,plan_json):
    if len(plan_json.encode())>MAX_PLAN_BYTES: raise ValueError('lifecycle plan exceeds 131072 bytes')
    plan=parse(plan_json,'plan JSON')
    # Authenticate once before any plan work. Backend.request then reuses this
    # Backend's in-memory CookieJar for every step and never writes it to disk.
    import time
    deadline=time.monotonic()+25.0
    state.backend.login_from_env(deadline=deadline)
    result=execute_plan(state.backend,plan,deadline=deadline)
    emit(result)
    if not result['ok']: raise click.exceptions.Exit(4)

def main(): cli()
if __name__=='__main__': main()
