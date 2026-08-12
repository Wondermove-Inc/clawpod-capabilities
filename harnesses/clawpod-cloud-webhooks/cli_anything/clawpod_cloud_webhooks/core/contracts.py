from copy import deepcopy
from .safety import digest, redact, validate_features, guard_agent_targets

MUTABLE_FIELDS = {
    "source": ("name", "description", "provider", "source_type", "preset_id", "organization_id", "auth_type", "auth_config", "config", "signature_config", "rate_limit_per_minute", "is_active", "playbook_id", "tenant_id"),
    "playbook": ("name", "description", "content", "is_active", "tenant_id"),
    "rule": ("name", "description", "source_id", "playbook_id", "conditions", "targets", "target_type", "target_agent_ids", "target_room_ids", "round_robin", "message_template", "priority", "cooldown_seconds", "max_per_hour", "is_active", "destination_evidence_required", "tenant_id"),
}
def require_idempotency(v):
    if not isinstance(v,str) or not v.strip(): raise ValueError("stable idempotency key is required")
    return v.strip()
def resource_merge(kind, current, changes):
    if kind not in MUTABLE_FIELDS: raise ValueError("unsupported resource kind")
    if not isinstance(current,dict) or not isinstance(changes,dict): raise ValueError("resource and changes must be JSON objects")
    unknown=set(changes)-set(MUTABLE_FIELDS[kind])
    if unknown: raise ValueError("unknown %s fields: %s" % (kind.title(), ",".join(sorted(unknown))))
    # PUT contracts are full-object: preserve every server field and overlay only
    # the allow-listed mutable fields supplied by the caller.
    out=deepcopy(current)
    out.update(deepcopy(changes)); return out
def source_merge(current, changes): return resource_merge("source",current,changes)
def validate_payload(kind, payload, tenant_id):
    if kind not in MUTABLE_FIELDS: raise ValueError("unsupported resource kind")
    if not isinstance(payload,dict): raise ValueError("payload must be a JSON object")
    unknown=set(payload)-set(MUTABLE_FIELDS[kind])
    if unknown: raise ValueError("unknown %s fields: %s" % (kind.title(), ",".join(sorted(unknown))))
    # Check an explicitly supplied tenant before binding the authoritative CLI
    # tenant.  Silently overwriting a conflict could cross a tenant boundary.
    preflight(payload,tenant_id)
    out=deepcopy(payload); out["tenant_id"]=tenant_id
    preflight(out,tenant_id)
    if not isinstance(out.get("name"),str) or not out["name"].strip(): raise ValueError("name is required")
    if kind=="playbook" and len((out.get("content") or "").encode())>50*1024: raise ValueError("Playbook content exceeds 50 KiB")
    return out
def preflight(payload, tenant_id):
    if not tenant_id: raise ValueError("tenant_id is required")
    if not isinstance(payload,dict): raise ValueError("payload must be a JSON object")
    if payload.get("tenant_id") not in (None,tenant_id): raise ValueError("tenant isolation mismatch")
    for t in payload.get("targets",[]) or []:
        if isinstance(t,dict) and t.get("tenant_id") not in (None,tenant_id): raise ValueError("target tenant isolation mismatch")
    validate_features(payload); guard_agent_targets(payload)
def preview(kind, resource_id, before, after, tenant_id, idempotency_key):
    idempotency_key=require_idempotency(idempotency_key); preflight(after,tenant_id)
    effect={"kind":kind,"resource_id":resource_id,"tenant_id":tenant_id,"idempotency_key":idempotency_key,"before":redact(before),"after":redact(after)}
    return {"operation":"mutation.preview","effect":effect,"effect_digest":digest(effect),"idempotency_key":idempotency_key,"requires_approval":True}

def create_preview(kind, payload, tenant_id, idempotency_key):
    return preview(kind,"(new)",{},payload,tenant_id,idempotency_key)

def delete_preview(kind, resource_id, current, tenant_id, idempotency_key):
    idempotency_key=require_idempotency(idempotency_key); preflight(current,tenant_id)
    effect={"kind":kind,"resource_id":resource_id,"tenant_id":tenant_id,"idempotency_key":idempotency_key,"before":redact(current),"after":None,"irreversible":True}
    return {"operation":"mutation.preview","effect":effect,"effect_digest":digest(effect),"idempotency_key":idempotency_key,"requires_approval":True}
def verify_event(e, require_destination=False):
    status=e.get("status"); err=(e.get("error_message") or "").strip()
    terminal=status in {"delivered","rejected","failed","timeout"}
    ok=status=="delivered" and not err and (not require_destination or bool(e.get("destination_evidence")))
    return {"ok":ok,"terminal":terminal,"status":status,"error_present":bool(err),"destination_evidence":bool(e.get("destination_evidence")),"reason":None if ok else ("non_empty_error_message" if err else "delivery_not_proven")}
def secret_warning(data, action):
    return {"action":action,"previous_secret_may_remain_valid":True,"previous_secret_expires_at":data.get("previous_secret_expires_at"),"warning":"Rotation overlap can remain valid for 24 hours; regeneration may not clear an older overlap credential. Verify expiry metadata."}
