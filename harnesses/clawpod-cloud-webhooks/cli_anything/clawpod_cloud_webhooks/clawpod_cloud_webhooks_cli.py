import hashlib, hmac, json, shlex, sys
import click
from . import __version__
from .core.contracts import preview, require_idempotency, secret_warning, source_merge, verify_event
from .core.safety import digest, redact, validate_body
from .utils.backend import Backend, BackendError, RSA_CONTRACT

class State:
    def __init__(self, base_url, timeout, retries, json_mode):
        self.backend=Backend(base_url,timeout,retries); self.json=json_mode

def emit(obj):
    click.echo(json.dumps(redact(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False))
def parse(s,label="JSON"):
    try: return json.loads(s)
    except Exception as e: raise click.ClickException(f"malformed {label}: {e}")
def api(state, method, path, **kw): return state.backend.request(method,path,**kw)

def guarded(fn):
    def run(*a,**kw):
        try: return fn(*a,**kw)
        except BackendError as e:
            emit({"ok":False,"error":{"code":e.code,"message":str(e),"retry_safe":e.retry_safe,"status":e.status}}); raise click.exceptions.Exit(2)
        except (ValueError,click.ClickException) as e:
            emit({"ok":False,"error":{"code":"invalid_input","message":str(e),"retry_safe":False}}); raise click.exceptions.Exit(2)
    run.__name__=fn.__name__; return run

@click.group(invoke_without_command=True)
@click.option('--base-url',envvar='CLAWPOD_WEBHOOKS_BASE_URL',default='http://127.0.0.1:8765',show_default=True)
@click.option('--timeout',type=float,default=5.0,show_default=True)
@click.option('--retries',type=click.IntRange(0,3),default=2,show_default=True)
@click.option('--json','json_mode',is_flag=True,help='Emit deterministic JSON.')
@click.pass_context
def cli(ctx,base_url,timeout,retries,json_mode):
    """ClawPod Cloud Webhooks, safe portal/API CLI."""
    ctx.obj=State(base_url,timeout,retries,json_mode)
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
        "onboarding":{
            "required_account":"ClawPod Cloud TA account or an account with Webhook Manager permission",
            "installation_is_connection":False,
            "pre_login_check":"Confirm the account type or Webhook Manager permission before starting login or creating credential state.",
            "post_login_check":"Read back the authenticated identity, selected tenant, and Webhooks permissions before declaring the capability connected.",
            "missing_permission_behavior":"Stop without mutation and report the missing TA/Webhook Manager access as a blocker."
        }
    })
@auth.command('status')
@click.pass_obj
@guarded
def auth_status(state):
    remote=api(state,'GET','/api/proxy/auth/me'); local=state.backend.session_status()
    emit({"ok":True,"remote":remote,"local":{"connected":local["connected"],"protected_session":True,"sensitive_values_exposed":False}})

READS={'permissions':'/api/proxy/auth/permissions','presets':'/api/proxy/webhook-presets','source':'/api/proxy/webhook-sources','playbook':'/api/proxy/webhook-playbooks','rule':'/api/proxy/webhook-rules','event':'/api/proxy/webhook-events'}
def add_read_group(name,path):
    g=click.Group(name=name)
    @click.command('list')
    @click.option('--tenant-id',required=True)
    @click.pass_obj
    @guarded
    def list_cmd(state,tenant_id): emit({"ok":True,"kind":name,"items":api(state,'GET',path+'?tenant_id='+tenant_id)})
    @click.command('get')
    @click.argument('resource_id')
    @click.option('--tenant-id',required=True)
    @click.pass_obj
    @guarded
    def get_cmd(state,resource_id,tenant_id): emit({"ok":True,"kind":name,"item":api(state,'GET',path+'/'+resource_id+'?tenant_id='+tenant_id)})
    g.add_command(list_cmd); g.add_command(get_cmd); cli.add_command(g)
for _n,_p in READS.items(): add_read_group(_n,_p)

@cli.command('event-inspect-redacted')
@click.argument('event_id')
@click.option('--tenant-id',required=True)
@click.pass_obj
@guarded
def event_inspect(state,event_id,tenant_id): emit({"ok":True,"event":redact(api(state,'GET',f'/api/proxy/webhook-events/{event_id}?tenant_id={tenant_id}'))})

@cli.command('event-verify')
@click.argument('event_id')
@click.option('--tenant-id',required=True)
@click.option('--require-destination-evidence',is_flag=True)
@click.pass_obj
@guarded
def event_verify(state,event_id,tenant_id,require_destination_evidence):
    e=api(state,'GET',f'/api/proxy/webhook-events/{event_id}?tenant_id={tenant_id}'); v=verify_event(e,require_destination_evidence); emit({"ok":v['ok'],"verification":v,"event":redact(e)})
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
@click.option('--resource-id',required=True)
@click.option('--tenant-id',required=True)
@click.option('--before-json',required=True)
@click.option('--after-json',required=True)
@click.option('--idempotency-key',required=True)
@guarded
def mutation_preview(kind,resource_id,tenant_id,before_json,after_json,idempotency_key): emit({'ok':True,'preview':preview(kind,resource_id,parse(before_json),parse(after_json),tenant_id,idempotency_key)})

@cli.command('source-update')
@click.argument('source_id')
@click.option('--tenant-id',required=True)
@click.option('--changes-json',required=True)
@click.option('--idempotency-key',required=True)
@click.option('--effect-digest',required=True)
@click.option('--approve',is_flag=True,required=True)
@click.pass_obj
@guarded
def source_update(state,source_id,tenant_id,changes_json,idempotency_key,effect_digest,approve):
    require_idempotency(idempotency_key)
    before=api(state,'GET',f'/api/proxy/webhook-sources/{source_id}?tenant_id={tenant_id}')
    after=source_merge(before,parse(changes_json)); p=preview('source',source_id,before,after,tenant_id,idempotency_key)
    if p['effect_digest']!=effect_digest: raise ValueError('effect digest mismatch; re-preview current Source')
    result=api(state,'PUT',f'/api/proxy/webhook-sources/{source_id}',body=after,idempotency=idempotency_key)
    readback=api(state,'GET',f'/api/proxy/webhook-sources/{source_id}?tenant_id={tenant_id}')
    expected={k:after.get(k) for k in after}; actual={k:readback.get(k) for k in after}; ok=expected==actual
    emit({'ok':ok,'operation':'source.update','effect_digest':effect_digest,'verified':ok,'result':result,'readback':readback,'retry_safe':False if not ok else None,'partial_failure':not ok})
    if not ok: raise click.exceptions.Exit(4)

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

def main(): cli()
if __name__=='__main__': main()
