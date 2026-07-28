from copy import deepcopy
from .safety import digest, validate_features, guard_agent_targets
MUTABLE_SOURCE=("name","description","provider","auth_type","auth_config","rate_limit_per_minute","is_active","playbook_id","tenant_id")
def require_idempotency(v):
    if not isinstance(v,str) or not v.strip(): raise ValueError("stable idempotency key is required")
    return v.strip()
def source_merge(current, changes):
    unknown=set(changes)-set(MUTABLE_SOURCE)
    if unknown: raise ValueError("unknown Source fields: "+",".join(sorted(unknown)))
    out={k:deepcopy(current.get(k)) for k in MUTABLE_SOURCE if k in current}
    out.update(deepcopy(changes)); return out
def preflight(payload, tenant_id):
    if not tenant_id: raise ValueError("tenant_id is required")
    if payload.get("tenant_id") not in (None,tenant_id): raise ValueError("tenant isolation mismatch")
    for t in payload.get("targets",[]) or []:
        if isinstance(t,dict) and t.get("tenant_id") not in (None,tenant_id): raise ValueError("target tenant isolation mismatch")
    validate_features(payload); guard_agent_targets(payload)
def preview(kind, resource_id, before, after, tenant_id, idempotency_key):
    require_idempotency(idempotency_key); preflight(after,tenant_id)
    effect={"kind":kind,"resource_id":resource_id,"tenant_id":tenant_id,"before":before,"after":after}
    return {"operation":"mutation.preview","effect":effect,"effect_digest":digest(effect),"idempotency_key":idempotency_key,"requires_approval":True}
def verify_event(e, require_destination=False):
    status=e.get("status"); err=(e.get("error_message") or "").strip()
    terminal=status in {"delivered","rejected","failed","timeout"}
    ok=status=="delivered" and not err and (not require_destination or bool(e.get("destination_evidence")))
    return {"ok":ok,"terminal":terminal,"status":status,"error_present":bool(err),"destination_evidence":bool(e.get("destination_evidence")),"reason":None if ok else ("non_empty_error_message" if err else "delivery_not_proven")}
def secret_warning(data, action):
    return {"action":action,"previous_secret_may_remain_valid":True,"previous_secret_expires_at":data.get("previous_secret_expires_at"),"warning":"Rotation overlap can remain valid for 24 hours; regeneration may not clear an older overlap credential. Verify expiry metadata."}
