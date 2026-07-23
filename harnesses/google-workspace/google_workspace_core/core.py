from __future__ import annotations
import base64, hashlib, json, os, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from .auth import CredentialProvider,AuthError
from .catalog import catalog,operation,preflight,service_for,OperationError
from .mime import compose_message
from .security import atomic_write,digest,redact,safe_path,append_audit,canonical
from .transport import Transport,ScriptedTransport,HTTPError,retry_request
from .validation import validate,ValidationError
from .scopes import enforce,required_scopes
from .state import issue_preview,consume_preview,idempotency_lookup,idempotency_store,bind_token,unbind_token,transfer_load,transfer_store

EXIT={"INVALID_ARGUMENT":2,"INVALID_MIME":2,"INVALID_TIME_ZONE":2,"INVALID_RECURRENCE":2,"AUTH_REQUIRED":3,"AUTH_EXPIRED":3,"ACCOUNT_NOT_FOUND":3,"INSUFFICIENT_SCOPE":4,"PERMISSION_DENIED":4,"APPROVAL_REQUIRED":4,"NOT_FOUND":5,"CONFLICT":6,"PRECONDITION_FAILED":6,"SYNC_TOKEN_EXPIRED":6,"IDEMPOTENCY_CONFLICT":6,"QUOTA_EXCEEDED":7,"RATE_LIMITED":7,"TRANSIENT":8,"TIMEOUT":8,"NETWORK_ERROR":8,"PARTIAL_FAILURE":9,"AMBIGUOUS_COMMIT":9,"LOCAL_IO_ERROR":10,"CHECKSUM_MISMATCH":10,"PROVIDER_ERROR":11,"UNSUPPORTED_BY_PROVIDER":11,"UNSUPPORTED_BY_CONTRACT":11,"INTERNAL_ERROR":12}
SCOPES={"identity":["openid","email"],"workspace-max":["https://mail.google.com/","https://www.googleapis.com/auth/calendar","https://www.googleapis.com/auth/drive"],"gmail-read":["https://www.googleapis.com/auth/gmail.readonly"],"gmail-compose":["https://www.googleapis.com/auth/gmail.compose"],"gmail-modify":["https://www.googleapis.com/auth/gmail.modify"],"gmail-settings":["https://www.googleapis.com/auth/gmail.settings.basic"],"calendar-read":["https://www.googleapis.com/auth/calendar.readonly"],"calendar-events":["https://www.googleapis.com/auth/calendar.events"],"drive-file":["https://www.googleapis.com/auth/drive.file"],"drive-read":["https://www.googleapis.com/auth/drive.readonly"],"drive-manage":["https://www.googleapis.com/auth/drive"]}

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
 if action=="login":
  from .oauth_desktop import desktop_login,LoginError
  body=payload.get("body",{})
  try:
   result=desktop_login(transfer_root=payload.get("transferRoot"),client_path=body.get("clientPath"),output_path=payload.get("outputPath"),alias=payload.get("account"),profiles=body.get("profiles",[]),timeout=payload.get("timeoutMs",600000)/1000,overwrite=payload.get("overwrite",False),managed_browser_devtools_url=body.get("managedBrowserDevtoolsUrl"),smoke_tests=body.get("smokeTests",[]))
  except LoginError as e:return fail(command,payload,"AUTH_REQUIRED",str(e),account=payload.get("account"))
  out["data"]={"resource":result};return out,0
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
 # Validate batch items independently so one malformed item produces a per-item
 # PARTIAL_FAILURE instead of rejecting the entire batch before any work starts.
 if payload.get("batch") is not None:
  if not isinstance(payload["batch"],list) or not payload["batch"]:return fail(command,payload,"INVALID_ARGUMENT","batch must be a non-empty array",account=account)
  base={k:v for k,v in payload.items() if k!="batch"};results=[];failed=0;halted=None
  for i,item in enumerate(payload["batch"]):
   if halted:
    child,code=fail(command,base,"PARTIAL_FAILURE",f"not launched after systemic {halted}",account=account,details={"halted":True,"systemicCode":halted})
   elif not isinstance(item,dict):child,code=fail(command,base,"INVALID_ARGUMENT","batch item must be an object",account=account)
   else:child,code=run(command,{**base,**item})
   results.append({"index":i,"ok":code==0,"launched":halted is None,"result":child});failed+=code!=0
   if code and child.get("error",{}).get("code") in ("AUTH_REQUIRED","AUTH_EXPIRED","INSUFFICIENT_SCOPE","QUOTA_EXCEEDED","RATE_LIMITED"):halted=child["error"]["code"]
  out["data"]={"items":results,"succeeded":len(results)-failed,"failed":failed,"haltedOn":halted}
  if failed:out["ok"]=False;out["error"]={"code":"PARTIAL_FAILURE","message":f"{failed} of {len(results)} batch items failed","retryable":False,"details":{},"remediation":"Inspect each item result and retry only failed safe items"};return out,9
  return out,0
 try: validate(payload,catalog()[command]["inputSchema"],command,semantic=False)
 except ValidationError as e:return fail(command,payload,e.code,str(e),account=account)
 except (ValueError,TypeError) as e:return fail(command,payload,"INVALID_ARGUMENT",str(e),account=account)
 if command.startswith("auth."): return local_auth(command,payload,out)
 try: op=operation(command,payload.get("params",{}))
 except OperationError as e:
  code="UNSUPPORTED_BY_CONTRACT" if "not implemented" in str(e) else "INVALID_ARGUMENT"
  return fail(command,payload,code,str(e),account=account)
 safety=catalog()[command]["safetyClasses"]
 mutating=any(x in safety for x in ("writeSafe","externalSideEffect","destructive"))
 # MIME compose
 if command.startswith("gmail.") and command.split(".")[-1] in ("send","create","update","insert","import") and payload.get("body",{}).get("compose"):
  try: raw,atts=compose_message(payload["body"]["compose"],payload.get("transferRoot"));payload={**payload,"body":{"raw":raw,**{k:v for k,v in payload["body"].items() if k!="compose"}}};out["provenance"]["attachments"] = atts
  except Exception as e:return fail(command,payload,"INVALID_MIME",str(e),account=account)
 mock=os.environ.get("GOOGLE_WORKSPACE_MOCK_HTTP"); transport=ScriptedTransport(mock) if mock else Transport()
 try:
  if mock: token="synthetic-test-token";meta={"email":"fake@example.invalid","subject_hash":"fake","scopes":sum(SCOPES.values(),[])+["https://www.googleapis.com/auth/gmail.settings.basic","https://www.googleapis.com/auth/gmail.settings.sharing","https://www.googleapis.com/auth/calendar","https://www.googleapis.com/auth/calendar.acl"]}
  else: token,meta=CredentialProvider().token(account)
  needed=enforce(command,meta.get("scopes",[]),safety)
 except AuthError as e:return fail(command,payload,"AUTH_REQUIRED",str(e),account=account)
 except PermissionError as e:return fail(command,payload,"INSUFFICIENT_SCOPE",str(e),account=account)
 try:validate(payload,None,command,semantic=True)
 except ValidationError as e:return fail(command,payload,e.code,str(e),account=account)
 headers={"Authorization":"Bearer "+token}
 target=op["url"];observed_etag=None
 # Receiver configuration is an explicit capability boundary, never inferred.
 if command=='gmail.watch.start':
  configured=os.environ.get('GOOGLE_WORKSPACE_PUBSUB_TOPIC')
  if not configured:return fail(command,payload,'UNSUPPORTED_BY_CONTRACT','Pub/Sub receiver is not configured (GOOGLE_WORKSPACE_PUBSUB_TOPIC)',account=account)
  if payload.get('body',{}).get('topicName')!=configured:return fail(command,payload,'INVALID_ARGUMENT','watch topicName does not match configured Pub/Sub receiver',account=account)
 if command.endswith('.watch') and command.startswith(('calendar.','drive.')):
  configured=os.environ.get('GOOGLE_WORKSPACE_HTTPS_RECEIVER');address=payload.get('body',{}).get('address')
  if not configured:return fail(command,payload,'UNSUPPORTED_BY_CONTRACT','HTTPS watch receiver is not configured (GOOGLE_WORKSPACE_HTTPS_RECEIVER)',account=account)
  if not configured.startswith('https://') or address!=configured:return fail(command,payload,'INVALID_ARGUMENT','watch address must exactly match the configured HTTPS receiver',account=account)
 # Idempotent replay must happen before consuming a one-use confirmation.
 if payload.get("idempotencyKey"):
  prior,fp=idempotency_lookup(payload["idempotencyKey"],command,account,payload)

  if prior:
   if prior["fingerprint"]!=fp:return fail(command,payload,"IDEMPOTENCY_CONFLICT","idempotency key was used with different input",account=account)
   return prior["result"],0
 effect=digest(command,account,payload)
 if mutating:
  check=preflight(command,payload.get("params",{}))
  if payload.get("preview") or payload.get("dryRun"):
   if payload.get("dryRun"):
    try:
     if check["method"]:
      _,probe_headers,probe,_=retry_request(transport,check["method"],check["url"],headers=headers,query=check["query"],timeout=payload.get("timeoutMs",30000)/1000,safe=True)
      if check["etag"]:observed_etag=(probe.get("etag") if isinstance(probe,dict) else None) or probe_headers.get("ETag")
     if payload.get("ifMatch") and observed_etag and payload["ifMatch"]!=observed_etag:return fail(command,payload,"PRECONDITION_FAILED","dry-run observed a different target ETag",account=account)
    except HTTPError as e:return fail(command,payload,provider_error(e),str(e),status=e.status,reason=e.reason,account=account)
   preview_token=issue_preview(command,account,payload,target,observed_etag)
   out["effects"]=[{"kind":"planned","targets":redact(payload.get("params",{})),"before":None,"after":redact(payload.get("body",{})),"recoverability":"permanent" if "destructive" in safety else "provider-dependent","effectDigest":preview_token}]
   out["data"]={"preview":True,"dryRun":bool(payload.get("dryRun")),"effectDigest":preview_token,"duplicateFingerprint":effect,"requiredScopes":needed,"target":target,"etag":observed_etag};return out,0
  if not payload.get('confirm'):return fail(command,payload,'APPROVAL_REQUIRED','all mutations require a successful dry-run preview and --confirm',account=account)
  try:
   if check["method"] and check["etag"]:
    _,probe_headers,probe,_=retry_request(transport,check["method"],check["url"],headers=headers,query=check["query"],timeout=payload.get("timeoutMs",30000)/1000,safe=True)
    observed_etag=(probe.get("etag") if isinstance(probe,dict) else None) or probe_headers.get("ETag")
  except HTTPError as e:return fail(command,payload,provider_error(e),str(e),status=e.status,reason=e.reason,account=account)
  ok,reason=consume_preview(payload.get("confirm",""),command,account,payload,target,observed_etag)
  if not ok:return fail(command,payload,"APPROVAL_REQUIRED",reason,account=account)
  effect=payload['confirm']
 if payload.get("idempotencyKey"):
  prior,fp=idempotency_lookup(payload["idempotencyKey"],command,account,payload)
 if payload.get("ifMatch"):headers["If-Match"]=payload["ifMatch"]
 resume_prefix=b""
 if command in ("drive.files.download","drive.files.export") and payload.get("resume") and payload.get("outputPath"):
  try:
   existing=safe_path(payload.get("transferRoot") or ".",payload["outputPath"],output=True)
   if existing.exists():resume_prefix=existing.read_bytes();headers["Range"]=f"bytes={len(resume_prefix)}-"
  except Exception as e:return fail(command,payload,"LOCAL_IO_ERROR",str(e),account=account)
 params={k:v for k,v in payload.get("params",{}).items() if k not in op.get("pathParams",set()) and k not in ("userId","kind")}
 params.update(op.get("query",{}))
 if payload.get("fields"):params["fields"]=",".join(payload["fields"])
 if payload.get("pageSize"):params["pageSize"]=payload["pageSize"]
 if payload.get("allPages") and payload.get("maxItems") is not None:
  params["pageSize"]=min(params.get("pageSize",500),payload["maxItems"])
 if payload.get("pageToken"):
  try:params["pageToken"]=unbind_token(payload["pageToken"],command,account,{k:v for k,v in params.items() if k!="pageToken"})
  except ValueError as e:return fail(command,payload,"INVALID_ARGUMENT",str(e),account=account)
 safe_retry=not (command in ("gmail.messages.send","gmail.drafts.send") or "destructive" in safety)
 try:
  request_body=payload.get("body") or None
  if command in ("drive.files.trash","drive.files.untrash"):
   request_body={"trashed":command.endswith(".trash")}
  if command=="drive.folders.create":
   request_body={**(request_body or {}),"mimeType":"application/vnd.google-apps.folder"}
  if command in ("drive.files.upload","drive.files.create","drive.files.update") and payload.get("inputPath"):
   source=safe_path(payload.get("transferRoot") or ".",payload["inputPath"]);content=source.read_bytes();upload_type=(payload.get("params") or {}).get("uploadType","resumable")
   if upload_type=="multipart":
    boundary="clawpod-"+uuid.uuid4().hex;meta=json.dumps(payload.get("body") or {"name":source.name},separators=(",",":")).encode();request_body=b"--"+boundary.encode()+b"\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"+meta+b"\r\n--"+boundary.encode()+b"\r\nContent-Type: application/octet-stream\r\n\r\n"+content+b"\r\n--"+boundary.encode()+b"--\r\n";headers["Content-Type"]="multipart/related; boundary="+boundary
    status,rh,data,retries=retry_request(transport,op["method"],op["url"],headers=headers,query=params,body=request_body,timeout=payload.get("timeoutMs",30000)/1000,safe=safe_retry)
   elif upload_type in ("simple","media"):
    params['uploadType']='media'
    status,rh,data,retries=retry_request(transport,op["method"],op["url"],headers=headers,query=params,body=content,timeout=payload.get("timeoutMs",30000)/1000,safe=safe_retry)
   elif upload_type=="resumable":
    stat=source.stat();source_fp=hashlib.sha256(content).hexdigest();transfer_key=hashlib.sha256(canonical({"account":account,"command":command,"path":str(source),"size":len(content),"mtime":stat.st_mtime_ns,"sha256":source_fp,"target":op['url'],"metadata":payload.get('body') or {}}).encode()).hexdigest();saved=transfer_load(transfer_key);location=saved.get('location') if saved else None;offset=int(saved.get('offset',0)) if saved else 0;retries=0
    if not location:
     init_headers={**headers,"X-Upload-Content-Length":str(len(content)),"X-Upload-Content-Type":"application/octet-stream"};status,rh,init,retries=retry_request(transport,"POST",op["url"],headers=init_headers,query=params,body=payload.get("body") or {"name":source.name},timeout=payload.get("timeoutMs",30000)/1000,safe=True)
     location=rh.get("Location") or rh.get("location")
     if not location:raise HTTPError(502,"missingResumableLocation")
     transfer_store(transfer_key,{"location":location,"offset":0,"size":len(content),"sha256":source_fp,"createdAt":time.time()})
    if offset<0 or offset>len(content):raise HTTPError(409,"invalidResumableOffset")
    chunk_size=8*1024*1024 # multiple of Google's required 256 KiB
    data={};status=308;rh={}
    while offset<len(content):
     end=min(offset+chunk_size,len(content));chunk=content[offset:end];put_headers={**headers,"Content-Length":str(len(chunk)),"Content-Range":f"bytes {offset}-{end-1}/{len(content)}"};status,rh,data,n=retry_request(transport,"PUT",location,headers=put_headers,body=chunk,timeout=payload.get("timeoutMs",30000)/1000,safe=True);retries+=n
     if status==308:
      reported=rh.get('Range') or rh.get('range');confirmed=(int(reported.rsplit('-',1)[1])+1) if reported and '-' in reported else end
      if confirmed<offset or confirmed>end:raise HTTPError(409,"invalidResumableOffset")
      offset=confirmed;transfer_store(transfer_key,{"location":location,"offset":offset,"size":len(content),"sha256":source_fp,"updatedAt":time.time()});continue
     if status not in (200,201):raise HTTPError(status,"unexpectedResumableStatus")
     offset=end;transfer_store(transfer_key,{"location":location,"offset":offset,"size":len(content),"sha256":source_fp,"completed":True,"updatedAt":time.time()})
   else:return fail(command,payload,"INVALID_ARGUMENT","uploadType must be simple, media, multipart, or resumable",account=account)
  else:status,rh,data,retries=retry_request(transport,op["method"],op["url"],headers=headers,query=params,body=request_body,timeout=payload.get("timeoutMs",30000)/1000,safe=safe_retry)
  pages=1
  if payload.get("allPages"):
   max_pages=payload.get("maxPages",100);max_items=payload.get("maxItems",10000);key=next((k for k,v in data.items() if isinstance(v,list)),None)
   if key:data[key]=data[key][:max_items]
   while key and isinstance(data,dict) and data.get("nextPageToken") and pages<max_pages and len(data[key])<max_items:
    remaining=max_items-len(data[key]);q={**params,"pageToken":data["nextPageToken"],"pageSize":min(remaining,payload.get('pageSize') or 500)};_,_,nxt,nr=retry_request(transport,op["method"],op["url"],headers=headers,query=q,body=None,timeout=payload.get("timeoutMs",30000)/1000,safe=True);retries+=nr;pages+=1
    if isinstance(nxt.get(key),list):data[key].extend(nxt[key][:remaining]);data["nextPageToken"]=nxt.get("nextPageToken")
    else:break
 except HTTPError as e:
  code=provider_error(e)
  if command in ("gmail.messages.send","gmail.drafts.send") and e.status>=500:code="AMBIGUOUS_COMMIT"
  return fail(command,payload,code,str(e),status=e.status,reason=e.reason,account=account)
 out["account"].update({"email":meta.get("email"),"subject":meta.get("subject_hash")})
 if resume_prefix:
  content_range=rh.get('Content-Range') or rh.get('content-range');expected_prefix=f'bytes {len(resume_prefix)}-'
  if status!=206 or not content_range or not content_range.startswith(expected_prefix):
   return fail(command,payload,'PRECONDITION_FAILED','resumed download requires 206 with matching Content-Range',status=status,account=account,details={'expectedStart':len(resume_prefix),'contentRange':content_range})
 if isinstance(data,bytes):
  try:
   raw=resume_prefix+data;actual=hashlib.sha256(raw).hexdigest();expected=payload.get("expectedSha256")
   if expected and actual != expected:return fail(command,payload,"CHECKSUM_MISMATCH","download checksum did not match expectedSha256",account=account,details={"expected":expected,"actual":actual})
   target_path=safe_path(payload.get("transferRoot") or ".",payload["outputPath"],output=True);atomic_write(target_path,raw,payload.get("overwrite",False) or bool(resume_prefix));data={"transfer":{"path":str(target_path),"bytes":len(raw),"sha256":actual,"mimeType":rh.get("Content-Type"),"resumed":bool(resume_prefix),"remoteId":payload.get("params",{}).get("fileId")}}
  except Exception as e:return fail(command,payload,"LOCAL_IO_ERROR",str(e),account=account)
 out["provenance"].update({"providerStatus":status,"retryCount":retries,"etag":data.get("etag"),"effectiveFields":payload.get("fields",[]),"requiredScopes":needed})
 items=next((data[k] for k in ("messages","threads","labels","drafts","history","items","files","permissions","comments","replies","revisions","drives","changes","events","calendars","rules") if isinstance(data.get(k),list)),None)
 if items is not None:
  raw_next=data.get("nextPageToken");bound=bind_token(raw_next,command,account,{k:v for k,v in params.items() if k!="pageToken"}) if raw_next else None
  out["data"]={"items":items};out["page"]={"nextPageToken":bound,"itemsReturned":len(items),"pagesFetched":locals().get("pages",1),"truncated":bool(raw_next)}
 else:out["data"]={"resource":data};out.pop("page",None)
 if mutating:out["effects"]=[{"kind":"confirmed","resourceIds":[data.get("id")] if data.get("id") else [],"effectDigest":effect,"recoverability":"permanent" if "destructive" in safety else "provider-dependent"}]
 if payload.get("outputPath") and isinstance(data.get("data"),str):
  try:
   target=safe_path(payload.get("transferRoot") or ".",payload["outputPath"],output=True);raw=base64.urlsafe_b64decode(data["data"]+"="*(-len(data["data"])%4));atomic_write(target,raw,payload.get("overwrite",False));out["data"]={"transfer":{"path":str(target),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"mimeType":data.get("mimeType"),"resumed":False,"remoteId":payload.get("params",{}).get("fileId")}}
  except Exception as e:return fail(command,payload,"LOCAL_IO_ERROR",str(e),account=account)
 if payload.get("idempotencyKey"):idempotency_store(payload["idempotencyKey"],command,account,payload,out)
 audit=os.environ.get("GOOGLE_WORKSPACE_AUDIT_FILE")
 if audit:append_audit(audit,{"timestamp":now(),"command":command,"requestId":out["requestId"],"account":account,"inputHash":hashlib.sha256(canonical(redact(payload)).encode()).hexdigest(),"safetyClasses":safety,"result":"ok","effects":out["effects"]})
 return out,0
