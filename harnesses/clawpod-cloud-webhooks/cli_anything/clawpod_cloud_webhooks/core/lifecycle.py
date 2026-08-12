"""Bounded, single-session lifecycle plan execution."""
from copy import deepcopy
import re, time
from .contracts import MUTABLE_FIELDS, create_preview, delete_preview, preview, readback_mismatches, resource_merge, validate_payload, verify_event
from .safety import redact

MAX_STEPS=30
MAX_PLAN_BYTES=131072
MAX_TOTAL_SECONDS=25.0
READ_PATHS={"source":"/api/proxy/webhook-sources","playbook":"/api/proxy/webhook-playbooks","rule":"/api/proxy/webhook-rules","event":"/api/proxy/webhook-events"}
READ_ACTIONS={f"{k}.{a}" for k in READ_PATHS for a in ("list","get")} | {"event.inspect","event.verify"}
MUTATIONS={f"{k}.{a}" for k in ("source","playbook","rule") for a in ("create","update","delete")} | {"source.enable","source.disable","rule.enable","rule.disable","rule.reorder","source.rotate","source.regenerate"}
ALLOWED=READ_ACTIONS|MUTATIONS
REF=re.compile(r"^\$steps\.([A-Za-z][A-Za-z0-9_-]{0,63})\.(result|readback)(?:\.([A-Za-z0-9_-]+))+$")
COMMON_FIELDS={"name","operation","tenant_id"}
CONTROL_FIELDS={"approve","idempotency_key","effect_digest"}
OPERATION_FIELDS={
    **{f"{kind}.list":COMMON_FIELDS for kind in READ_PATHS},
    **{f"{kind}.get":COMMON_FIELDS|{"resource_id"} for kind in READ_PATHS},
    "event.inspect":COMMON_FIELDS|{"resource_id"},
    "event.verify":COMMON_FIELDS|{"resource_id","require_destination_evidence"},
    **{f"{kind}.create":COMMON_FIELDS|CONTROL_FIELDS|{"payload"} for kind in ("source","playbook","rule")},
    **{f"{kind}.update":COMMON_FIELDS|CONTROL_FIELDS|{"resource_id","changes"} for kind in ("source","playbook","rule")},
    **{f"{kind}.delete":COMMON_FIELDS|CONTROL_FIELDS|{"resource_id"} for kind in ("source","playbook","rule")},
    **{f"{kind}.{action}":COMMON_FIELDS|CONTROL_FIELDS|{"resource_id"} for kind in ("source","rule") for action in ("enable","disable")},
    "rule.reorder":COMMON_FIELDS|CONTROL_FIELDS|{"resource_id","priority"},
    "source.rotate":COMMON_FIELDS|CONTROL_FIELDS|{"resource_id"},
    "source.regenerate":COMMON_FIELDS|CONTROL_FIELDS|{"resource_id"},
}

def _path_id(v):
    from urllib.parse import quote
    return quote(str(v),safe="")
def _query(t): return "?tenant_id="+_path_id(t)
def _resolve(value, completed):
    if isinstance(value,str) and value.startswith("$steps."):
        match=REF.fullmatch(value)
        if not match: raise ValueError("invalid lifecycle reference")
        parts=value.split("."); name=parts[1]
        if name not in completed: raise ValueError("reference must target an earlier completed step")
        cur=completed[name]
        for part in parts[2:]:
            if not isinstance(cur,dict) or part not in cur: raise ValueError("lifecycle reference path does not exist")
            cur=cur[part]
        if isinstance(cur,(dict,list)): raise ValueError("lifecycle reference must resolve to a scalar")
        return cur
    if isinstance(value,dict): return {k:_resolve(v,completed) for k,v in value.items()}
    if isinstance(value,list): return [_resolve(v,completed) for v in value]
    return value

def _validate_step(step,resolved=False):
    if not isinstance(step,dict): raise ValueError("each step must be an object")
    name=step.get("name"); op=step.get("operation")
    if not isinstance(name,str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}",name): raise ValueError("step names must be stable identifiers")
    if op not in ALLOWED: raise ValueError("operation is not allowlisted")
    unknown=set(step)-OPERATION_FIELDS[op]
    if unknown: raise ValueError("unknown lifecycle step fields: "+",".join(sorted(unknown)))
    if not isinstance(step.get("tenant_id"),(str,int)) or isinstance(step.get("tenant_id"),bool) or not str(step["tenant_id"]).strip(): raise ValueError("tenant_id must resolve to a nonempty string or integer")
    if "resource_id" in OPERATION_FIELDS[op] and (not isinstance(step.get("resource_id"),(str,int)) or isinstance(step.get("resource_id"),bool) or not str(step["resource_id"]).strip()): raise ValueError("resource_id must resolve to a nonempty string or integer")
    if op in MUTATIONS:
        if step.get("approve") is not True: raise ValueError("every mutation requires literal approve true")
        for field in ("idempotency_key","effect_digest"):
            value=step.get(field)
            if not isinstance(value,str) or not value.strip() or value.startswith("$steps."): raise ValueError(f"{field} must be a nonempty literal string")
        if not step["effect_digest"].startswith("sha256:"): raise ValueError("every mutation requires an effect digest")
    if op.endswith(".create") and not isinstance(step.get("payload"),dict): raise ValueError("create payload must be an object")
    if op.endswith(".update") and not isinstance(step.get("changes"),dict): raise ValueError("update changes must be an object")
    if op.endswith(".update"):
        kind=op.split('.')[0]; unknown=set(step["changes"])-set(MUTABLE_FIELDS[kind])
        if unknown: raise ValueError("unknown %s fields: %s" % (kind.title(),",".join(sorted(unknown))))
    if op=="rule.reorder" and (not isinstance(step.get("priority"),int) or isinstance(step.get("priority"),bool)): raise ValueError("priority must be an integer")
    if op=="event.verify" and "require_destination_evidence" in step and not isinstance(step["require_destination_evidence"],bool): raise ValueError("require_destination_evidence must be boolean")
    return step

def validate_plan(plan):
    if not isinstance(plan,dict) or set(plan)-{"steps"}: raise ValueError("plan must be an object containing only steps")
    steps=plan.get("steps")
    if not isinstance(steps,list) or not steps or len(steps)>MAX_STEPS: raise ValueError("plan must contain 1..30 steps")
    names=set()
    for step in steps:
        _validate_step(step); name=step["name"]
        if name in names: raise ValueError("step names must be unique stable identifiers")
        names.add(name)
    return steps

class _DeadlineBackend:
    def __init__(self,backend,deadline): self.backend=backend; self.deadline=deadline
    def request(self,*args,**kwargs): kwargs["deadline"]=self.deadline; return self.backend.request(*args,**kwargs)

class LifecycleFailure(ValueError):
    def __init__(self,message,uncertain=False,cleanup=None):
        super().__init__(message); self.code="verification_failed" if uncertain else "invalid_input"; self.retry_safe=False; self.uncertain=uncertain; self.cleanup=cleanup

def _reconciliation(step,kind,rid=None):
    return {"operation":step["operation"],"kind":kind,"resource_id":rid,"idempotency_key":step["idempotency_key"],"effect_digest":step["effect_digest"],"reconciliation_required":True,"uncertain":True,"retry_safe":False}

def _post_dispatch_failure(message,step,kind,rid=None,cause=None):
    failure=LifecycleFailure(message,True,_reconciliation(step,kind,rid))
    if cause is not None: raise failure from cause
    raise failure

def _mutate(b,method,path,step,kind,rid=None,body=None):
    try: return b.request(method,path,body=body,idempotency=step["idempotency_key"])
    except Exception as exc: _post_dispatch_failure("mutation transport failed after request initiation; reconcile before retry",step,kind,rid,exc)

def execute_plan(backend,plan,deadline=None):
    steps=validate_plan(plan); deadline=deadline or time.monotonic()+MAX_TOTAL_SECONDS; b=_DeadlineBackend(backend,deadline); completed={}; created=[]
    for raw in steps:
        if time.monotonic()>=deadline: return _failure(completed,created,raw,"plan_timeout","total lifecycle timeout exceeded",False,True)
        try:
            step=_resolve(deepcopy(raw),completed); _validate_step(step,resolved=True); out=_execute(b,step); safe=redact(out); completed[step["name"]]=safe
            if step["operation"].endswith(".create") and isinstance(out.get("readback"),dict) and out["readback"].get("id") is not None: created.append({"kind":step["operation"].split('.')[0],"id":out["readback"]["id"],"step":step["name"]})
            if step["operation"].endswith(".delete") and isinstance(out.get("readback"),dict) and out["readback"].get("absent") is True:
                deleted_kind=step["operation"].split('.')[0]; deleted_id=out["readback"].get("id")
                created[:]=[item for item in created if not (item.get("kind")==deleted_kind and str(item.get("id"))==str(deleted_id))]
        except Exception as exc:
            if getattr(exc,"cleanup",None): created.append(exc.cleanup)
            return _failure(completed,created,raw,getattr(exc,"code","invalid_input"),str(exc),getattr(exc,"retry_safe",False),getattr(exc,"uncertain",False))
    return {"ok":True,"login_count":1,"completed_steps":list(completed.values()),"cleanup_required":created,"session":{"persistent":False,"storage":"in-memory CookieJar"}}

def _failure(completed,created,step,code,message,retry,uncertain=False):
    return {"ok":False,"login_count":1,"completed_steps":list(completed.values()),"failed_step":step.get("name") if isinstance(step,dict) else None,"error":{"code":code,"message":message,"retry_safe":retry},"partial_state":{"uncertain":uncertain or code in {"timeout","plan_timeout","backend_error","verification_failed"},"mutations_completed":sum(1 for x in completed.values() if x.get("mutation"))},"cleanup_required":created,"session":{"persistent":False,"storage":"in-memory CookieJar"}}

def _created_id(kind,result):
    if isinstance(result,dict):
        for value in (result,result.get(kind),result.get("data")):
            if isinstance(value,dict) and value.get("id") is not None:return value["id"]
    return None

def _execute(b,step):
    op=step["operation"]; kind,action=op.split("."); tenant=step.get("tenant_id")
    if not tenant: raise ValueError("tenant_id is required")
    path=READ_PATHS[kind]
    if action=="list": return {"name":step["name"],"operation":op,"result":b.request("GET",path+_query(tenant)),"mutation":False}
    rid=step.get("resource_id")
    if action in ("get","inspect","verify"):
        if rid is None: raise ValueError("resource_id is required")
        item=b.request("GET",path+"/"+_path_id(rid)+_query(tenant)); out={"name":step["name"],"operation":op,"readback":item,"mutation":False}
        if action=="verify":
            out["verification"]=verify_event(item,bool(step.get("require_destination_evidence")))
            if not out["verification"]["ok"]: raise ValueError("event delivery verification failed")
        return out
    idem=step["idempotency_key"]; expected=step["effect_digest"]
    if action=="create":
        payload=validate_payload(kind,step.get("payload"),tenant); p=create_preview(kind,payload,tenant,idem)
        if p["effect_digest"]!=expected: raise ValueError("effect digest mismatch")
        result=_mutate(b,"POST",path,step,kind,body=payload); rid=_created_id(kind,result)
        if rid is None: _post_dispatch_failure("create completed but response omitted resource id; reconcile before retry",step,kind)
        try: readback=b.request("GET",path+"/"+_path_id(rid)+_query(tenant))
        except Exception as exc: _post_dispatch_failure("create completed but readback failed; reconcile before retry",step,kind,rid,exc)
        try: mismatches=readback_mismatches(kind,payload,readback)
        except Exception as exc: _post_dispatch_failure("create completed but local readback verification failed",step,kind,rid,exc)
    else:
        if rid is None: raise ValueError("resource_id is required")
        before=b.request("GET",path+"/"+_path_id(rid)+_query(tenant))
        if action=="delete":
            p=delete_preview(kind,rid,before,tenant,idem)
            if p["effect_digest"]!=expected: raise ValueError("effect digest mismatch")
            _mutate(b,"DELETE",path+"/"+_path_id(rid),step,kind,rid)
            try: b.request("GET",path+"/"+_path_id(rid)+_query(tenant))
            except Exception as exc:
                if getattr(exc,"status",None)!=404 and getattr(exc,"code",None)!="not_found": _post_dispatch_failure("delete may have completed but exact-item verification failed",step,kind,rid,exc)
            else: _post_dispatch_failure("delete verification found resource still present",step,kind,rid)
            return {"name":step["name"],"operation":op,"readback":{"id":rid,"absent":True},"effect_digest":expected,"mutation":True}
        if action in ("enable","disable"): changes={"is_active":action=="enable"}
        elif action=="reorder": changes={"priority":step.get("priority")}
        elif action in ("rotate","regenerate"):
            after={**before,"secret_action":action}; p=preview("source",rid,before,after,tenant,idem)
            if p["effect_digest"]!=expected: raise ValueError("effect digest mismatch")
            result=_mutate(b,"POST",path+"/"+_path_id(rid)+"/"+("rotate-secret" if action=="rotate" else "regenerate"),step,kind,rid)
            candidates=(result,result.get("source"),result.get("data")) if isinstance(result,dict) else ()
            if not any(isinstance(v,dict) and any(k in v for k in ("signing_secret","signingSecret","secret")) for v in candidates): _post_dispatch_failure("secret action response omitted new-secret acknowledgement",step,kind,rid)
            try: readback=b.request("GET",path+"/"+_path_id(rid)+_query(tenant))
            except Exception as exc: _post_dispatch_failure("secret action completed but lifecycle readback failed",step,kind,rid,exc)
            if not isinstance(readback,dict) or "previous_secret_expires_at" not in readback: _post_dispatch_failure("secret action lifecycle readback omitted previous_secret_expires_at",step,kind,rid)
            return {"name":step["name"],"operation":op,"result":result,"readback":readback,"credential_lifecycle":{"previous_secret_expires_at":readback.get("previous_secret_expires_at")},"effect_digest":expected,"mutation":True}
        else: changes=step.get("changes")
        after=resource_merge(kind,before,changes); p=preview(kind,rid,before,after,tenant,idem)
        if p["effect_digest"]!=expected: raise ValueError("effect digest mismatch")
        result=_mutate(b,"PUT",path+"/"+_path_id(rid),step,kind,rid,after)
        try: readback=b.request("GET",path+"/"+_path_id(rid)+_query(tenant))
        except Exception as exc: _post_dispatch_failure("mutation may have completed but readback failed",step,kind,rid,exc)
        try: mismatches=readback_mismatches(kind,after,readback)
        except Exception as exc: _post_dispatch_failure("mutation completed but local readback verification failed",step,kind,rid,exc)
    if mismatches: _post_dispatch_failure("mutation readback mismatch",step,kind,rid)
    return {"name":step["name"],"operation":op,"result":result,"readback":readback,"effect_digest":expected,"mutation":True}
