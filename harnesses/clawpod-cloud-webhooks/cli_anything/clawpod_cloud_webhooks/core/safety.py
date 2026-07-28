import hashlib, json, re
MAX_BODY=1_048_576
SENSITIVE={"authorization","cookie","set-cookie","x-webhook-signature","signature","signing_secret","secret","token","url_token","password","private_key"}
BROKEN_OPS={"in","not_in","gt","lt","gte","lte"}
TOKEN_PATH=re.compile(r"(?i)(/incoming/|/webhooks?/)([A-Za-z0-9._~-]{8,})")
BEARER=re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+")
def _sensitive(k):
    n=str(k).lower().replace('-','_')
    return n in SENSITIVE or any(x in n for x in ("secret","password","private_key","authorization","cookie","signature","url_token"))
def redact(v, key=""):
    if _sensitive(key): return "[REDACTED]"
    if isinstance(v,dict): return {str(k):redact(x,str(k)) for k,x in sorted(v.items(), key=lambda i:str(i[0]))}
    if isinstance(v,list): return [redact(x,key) for x in v]
    if isinstance(v,str): return BEARER.sub("Bearer [REDACTED]",TOKEN_PATH.sub(lambda m:m.group(1)+"[REDACTED]",v))
    return v
def canonical(v): return json.dumps(redact(v),sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(v): return "sha256:"+hashlib.sha256(canonical(v).encode()).hexdigest()
def validate_body(b):
    if len(b)>MAX_BODY: raise ValueError("payload exceeds 1 MiB inbound cap")
def validate_features(obj):
    if obj.get("message_template") not in (None,""): raise ValueError("message_template is currently nonfunctional and is rejected")
    for c in obj.get("conditions",[]) or []:
        if c.get("operator") in BROKEN_OPS: raise ValueError("unsupported condition operator: "+str(c.get("operator")))
def guard_agent_targets(obj):
    ts=obj.get("targets",[]) or []
    agents=[t for t in ts if isinstance(t,dict) and t.get("type")=="agent"]
    if agents and not obj.get("destination_evidence_required",False): raise ValueError("agent delivery blocked without destination evidence proof")
