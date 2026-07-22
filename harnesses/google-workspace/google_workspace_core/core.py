from __future__ import annotations
import base64, hashlib, json, os, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from .auth import CredentialProvider,AuthError
from .catalog import catalog,operation,service_for
from .mime import compose_message
from .security import atomic_write,digest,redact,safe_path,append_audit,canonical
from .transport import Transport,ScriptedTransport,HTTPError,retry_request
from .validation import validate,ValidationError

EXIT={"INVALID_ARGUMENT":2,"INVALID_MIME":2,"INVALID_TIME_ZONE":2,"INVALID_RECURRENCE":2,"AUTH_REQUIRED":3,"AUTH_EXPIRED":3,"ACCOUNT_NOT_FOUND":3,"INSUFFICIENT_SCOPE":4,"PERMISSION_DENIED":4,"APPROVAL_REQUIRED":4,"NOT_FOUND":5,"CONFLICT":6,"PRECONDITION_FAILED":6,"SYNC_TOKEN_EXPIRED":6,"IDEMPOTENCY_CONFLICT":6,"QUOTA_EXCEEDED":7,"RATE_LIMITED":7,"TRANSIENT":8,"TIMEOUT":8,"NETWORK_ERROR":8,"PARTIAL_FAILURE":9,"AMBIGUOUS_COMMIT":9,"LOCAL_IO_ERROR":10,"CHECKSUM_MISMATCH":10,"PROVIDER_ERROR":11,"UNSUPPORTED_BY_PROVIDER":11,"UNSUPPORTED_BY_CONTRACT":11,"INTERNAL_ERROR":12}
SCOPES={"identity":["openid","email"],"gmail-read":["https://www.googleapis.com/auth/gmail.readonly"],"gmail-compose":["https://www.googleapis.com/auth/gmail.compose"],"gmail-modify":["https://www.googleapis.com/auth/gmail.modify"],"calendar-read":["https://www.googleapis.com/auth/calendar.readonly"],"calendar-events":["https://www.googleapis.com/auth/calendar.events"],"drive-file":["https://www.googleapis.com/auth/drive.file"],"drive-read":["https://www.googleapis.com/auth/drive.readonly"],"drive-manage":["https://www.googleapis.com/auth/drive"]}

def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def envelope(command,payload,account=None):
 service,version=service_for(command)
 return {"ok":True,"schemaVersion":1,"command":command,"requestId":payload.get("requestId") or str(uuid.uuid4()),"account":{"alias":account} if account else None,"data":{},"page":{"nextPageToken":None,"itemsReturned":0,"pagesFetched":0,"truncated":False},"effects":[],"provenance":{"provider":"google","api":service,"apiVersion":version,"operation":".".join(command.split('.')[1:]),"receivedAt":now(),"resourceIds":[],"etag":None},"warnings":[]}
def fail(command,payload,code,message,status=None,reason=None,account=None,details=None):
 out=envelope(command,payload,account);out["ok"]=False;out.pop("data",None);out.pop("page",None);out["error"]={"code":code,"message":message,"retryable":code in ("RATE_LIMITED","TRANSIENT","TIMEOUT","NETWORK_ERROR"),"providerStatus":status,"providerReason":reason,"details":redact(details or {}),"remediation":remediation(code)};return out,EXIT.get(code,12)
def remediation(code):
 return {"APPROVAL_REQUIRED":"Run --preview, obtain approval for the effect digest, then pass --confirm","AUTH_REQUIRED":"Inject an approved mode-0600 OAuth credential file/provider","SYNC_TOKEN_EXPIRED":"Perform a fresh full synchronization","AMBIGUOUS_COMMIT":"Reconcile using the returned request fingerprint before retrying"}.get(code,"Review the sanitized error and correct the request")
def provider_error(e):
 if e.status==401:return "AUTH_EXPIRED"
 if e.status==404:return "NOT_FOUND"
 if e.status==409:return "CONFLICT"
 if e.status==410:return "SYNC_TOKEN_EXPIRED"
 if e.status==412:return "PRECONDITION_FAILED"
 if e.status==429:return "RATE_LIMITED"
 if e.status in (408,500,502,503,504):return "TRANSIENT"
 if e.status==403:
  if e.reason in ("insufficientPermissions","accessNotConfigured"):return "INSUFFICIENT_SCOPE"
  if "quota" in e.reason.lower():return "QUOTA_EXCEEDED"
  return "PERMISSION_DENIED"
 return "PROVIDER_ERROR"
def local_auth(command,payload,out):
 provider=CredentialProvider(); action=command.split(".",1)[1]
 if action=="scopes.list": out["data"]={"profiles":SCOPES}; return out,0
 if action=="login": return fail(command,payload,"UNSUPPORTED_BY_PROVIDER","OAuth callback requires a supervising PKCE receiver and protected token writer; configure those interfaces before login",account=payload.get("account"))
 if action=="accounts.list":
  if not provider.path: out["data"]={"items":[]};return out,0
  doc=json.loads(Path(provider.path).read_text()); items=doc.get("accounts",doc);out["data"]={"items":[{"alias":a,"email":v.get("email"),"subject":v.get("subject_hash"),"scopes":v.get("scopes",[])} for a,v in items.items()]};return out,0
 try:item=provider.load(payload.get("account"))
 except AuthError as e:return fail(command,payload,"AUTH_REQUIRED",str(e),account=payload.get("account"))
 safe={k:item.get(k) for k in ("email","subject_hash","scopes","expires_at")}
 if action=="scopes.check":
  required=set(sum((SCOPES.get(x,[]) for x in payload.get("body",{}).get("profiles",[])),[]));safe["missing"]=sorted(required-set(item.get("scopes",[])))
 out["data"]={"resource":safe};return out,0

def run(command,payload):
 account=payload.get("account") or os.environ.get("GOOGLE_WORKSPACE_ACCOUNT"); out=envelope(command,payload,account)
 if command not in catalog(): return fail(command,payload,"INVALID_ARGUMENT","unknown command",account=account)
 try: validate(payload)
 except ValidationError as e:return fail(command,payload,e.code,str(e),account=account)
 except (ValueError,TypeError) as e:return fail(command,payload,"INVALID_ARGUMENT",str(e),account=account)
 if command.startswith("auth."): return local_auth(command,payload,out)
 safety=catalog()[command]["safetyClasses"]; effect=digest(command,account,payload)
 mutating=any(x in safety for x in ("writeSafe","externallyVisible","destructive"))
 if mutating:
  out["effects"]=[{"kind":"planned","targets":redact(payload.get("params",{})),"before":None,"after":redact(payload.get("body",{})),"recoverability":"permanent" if "destructive" in safety else "provider-dependent","effectDigest":effect}]
  if payload.get("preview") or payload.get("dryRun"): out["data"]={"preview":True,"effectDigest":effect,"duplicateFingerprint":effect};return out,0
  if any(x in safety for x in ("externallyVisible","destructive")) and payload.get("confirm")!=effect:return fail(command,payload,"APPROVAL_REQUIRED","fresh matching effect confirmation required",account=account,details={"effectDigest":effect})
 # MIME compose
 if command.startswith("gmail.") and command.split(".")[-1] in ("send","create","update","insert","import") and payload.get("body",{}).get("compose"):
  try: raw,atts=compose_message(payload["body"]["compose"],payload.get("transferRoot"));payload={**payload,"body":{"raw":raw,**{k:v for k,v in payload["body"].items() if k!="compose"}}};out["provenance"]["attachments"] = atts
  except Exception as e:return fail(command,payload,"INVALID_MIME",str(e),account=account)
 op=operation(command,payload.get("params",{})); mock=os.environ.get("GOOGLE_WORKSPACE_MOCK_HTTP"); transport=ScriptedTransport(mock) if mock else Transport()
 try:
  if mock: token="synthetic-test-token";meta={"email":"fake@example.invalid","subject_hash":"fake","scopes":[]}
  else: token,meta=CredentialProvider().token(account)
 except AuthError as e:return fail(command,payload,"AUTH_REQUIRED",str(e),account=account)
 headers={"Authorization":"Bearer "+token}
 if payload.get("ifMatch"):headers["If-Match"]=payload["ifMatch"]
 params=dict(payload.get("params",{})); params.pop("userId",None)
 if payload.get("fields"):params["fields"]=",".join(payload["fields"])
 if payload.get("pageSize"):params["pageSize"]=payload["pageSize"]
 if payload.get("pageToken"):params["pageToken"]=payload["pageToken"]
 safe_retry=not (command in ("gmail.messages.send","gmail.drafts.send") or "destructive" in safety)
 try:
  status,rh,data,retries=retry_request(transport,op["method"],op["url"],headers=headers,query=params,body=payload.get("body") or None,timeout=payload.get("timeoutMs",30000)/1000,safe=safe_retry)
 except HTTPError as e:
  code=provider_error(e)
  if command in ("gmail.messages.send","gmail.drafts.send") and e.status>=500:code="AMBIGUOUS_COMMIT"
  return fail(command,payload,code,str(e),status=e.status,reason=e.reason,account=account)
 out["account"].update({"email":meta.get("email"),"subject":meta.get("subject_hash")})
 out["provenance"].update({"providerStatus":status,"retryCount":retries,"etag":data.get("etag"),"effectiveFields":payload.get("fields",[])})
 items=next((data[k] for k in ("messages","threads","labels","drafts","history","items","files","permissions","comments","replies","revisions","drives","changes","events","calendars","rules") if isinstance(data.get(k),list)),None)
 if items is not None:out["data"]={"items":items};out["page"]={"nextPageToken":data.get("nextPageToken"),"itemsReturned":len(items),"pagesFetched":1,"truncated":bool(data.get("nextPageToken"))}
 else:out["data"]={"resource":data};out.pop("page",None)
 if mutating:out["effects"]=[{"kind":"confirmed","resourceIds":[data.get("id")] if data.get("id") else [],"effectDigest":effect,"recoverability":"permanent" if "destructive" in safety else "provider-dependent"}]
 if payload.get("outputPath") and isinstance(data.get("data"),str):
  try:
   target=safe_path(payload.get("transferRoot") or ".",payload["outputPath"],output=True);raw=base64.urlsafe_b64decode(data["data"]+"="*(-len(data["data"])%4));atomic_write(target,raw,payload.get("overwrite",False));out["data"]={"transfer":{"path":str(target),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"mimeType":data.get("mimeType"),"resumed":False,"remoteId":payload.get("params",{}).get("fileId")}}
  except Exception as e:return fail(command,payload,"LOCAL_IO_ERROR",str(e),account=account)
 audit=os.environ.get("GOOGLE_WORKSPACE_AUDIT_FILE")
 if audit:append_audit(audit,{"timestamp":now(),"command":command,"requestId":out["requestId"],"account":account,"inputHash":hashlib.sha256(canonical(redact(payload)).encode()).hexdigest(),"safetyClasses":safety,"result":"ok","effects":out["effects"]})
 return out,0
