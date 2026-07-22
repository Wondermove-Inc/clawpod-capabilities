"""Declarative Google Workspace operation catalog and checked REST mapping."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import quote

MANIFEST = Path(__file__).resolve().parents[1] / "harness.json"
CONTRACTS = Path(__file__).resolve().parents[1] / "command_contracts.json"
class OperationError(ValueError): pass

def catalog() -> dict:
 """Return canonical provider command names, independent of manifest aliases."""
 commands=json.loads(MANIFEST.read_text(encoding="utf-8"))["commands"]
 contracts=json.loads(CONTRACTS.read_text(encoding="utf-8"))
 out={}
 for alias,meta in commands.items():
  command=meta.get("baseArgv",[alias])[0]
  item=dict(meta)
  # Rich recursive contracts and exact scopes stay outside the lifecycle
  # manifest, whose argv bridge supports scalar values only.
  item.update(contracts[command])
  out[command]=item
 return out
def service_for(command: str) -> tuple[str,str]:
 if command.startswith("gmail."): return "gmail","v1"
 if command.startswith("calendar."): return "calendar","v3"
 if command.startswith("drive."): return "drive","v3"
 return "oauth","v2"
def _q(value): return quote(str(value),safe="")
def _need(params,*keys):
 missing=[k for k in keys if not params.get(k)]
 if missing: raise OperationError("missing required identifier(s): "+", ".join(missing))
 return [_q(params[k]) for k in keys]

def operation(command:str, params:dict) -> dict:
 """Return a fully resolved provider request. Raises rather than emitting placeholder URLs."""
 service,version=service_for(command)
 if service=="oauth": return {"service":service,"version":version,"action":command.split(".",1)[1],"method":"LOCAL","url":"","query":{},"pathParams":set()}
 p=dict(params or {}); query={}; used=set(); parts=command.split("."); action=parts[-1]
 if service=="gmail":
  base="https://gmail.googleapis.com/gmail/v1/users/"+_q(p.get("userId","me")); resource=parts[1]
  if resource=="profile": path="profile"
  elif resource in ("messages","threads","labels","drafts","history"):
   path=resource; ids={"messages":"messageId","threads":"threadId","labels":"labelId","drafts":"draftId"}
   if action in ("get","modify","trash","untrash","delete","patch","update") or (action=="send" and resource=="drafts"):
    vals=_need(p,ids[resource]); used.add(ids[resource]); path+="/"+vals[0]
   suffix={"modify":"modify","trash":"trash","untrash":"untrash","send":"send"}.get(action)
   if suffix:path+="/"+suffix
   if action in ("batchModify","batchDelete"):path=resource+"/"+action
   if action in ("import","insert","send") and resource=="messages":path=resource+"/"+action
  elif resource=="attachments":
   m,a=_need(p,"messageId","attachmentId");used|={"messageId","attachmentId"};path=f"messages/{m}/attachments/{a}"
  elif resource=="watch": path="watch" if action=="start" else "stop"
  elif resource=="settings":
   if len(parts)==3:
    kind=p.get("kind"); allowed={"autoForwarding":"autoForwarding","imap":"imap","language":"language","pop":"pop","vacation":"vacation"}
    if kind not in allowed: raise OperationError("params.kind is required and must name a supported Gmail setting")
    used.add("kind");path="settings/"+allowed[kind]
   else:
    sub=parts[2]; path="settings/"+{"filters":"filters","forwardingAddresses":"forwardingAddresses","sendAs":"sendAs","delegates":"delegates","smime":"sendAs"}[sub]
    key={"filters":"filterId","forwardingAddresses":"forwardingEmail","sendAs":"sendAsEmail","delegates":"delegateEmail"}.get(sub)
    if sub=="smime":
     sendas,=_need(p,"sendAsEmail");used.add("sendAsEmail");path+=f"/{sendas}/smimeInfo"
     if action in ("get","setDefault","delete"):
      cert,=_need(p,"smimeInfoId");used.add("smimeInfoId");path+="/"+cert
      if action=="setDefault":path+="/setDefault"
    elif action in ("get","patch","update","verify","delete"):
     val,=_need(p,key);used.add(key);path+="/"+val
     if action=="verify":path+="/verify"
  methods={"list":"GET","get":"GET","create":"POST","insert":"POST","import":"POST","send":"POST","start":"POST","stop":"POST","modify":"POST","batchModify":"POST","batchDelete":"POST","trash":"POST","untrash":"POST","verify":"POST","setDefault":"POST","patch":"PATCH","update":"PUT","delete":"DELETE"}
  method=methods[action]
 elif service=="calendar":
  base="https://www.googleapis.com/calendar/v3";resource=parts[1]
  if resource=="colors":path="colors"
  elif resource=="settings":
   path="users/me/settings"
   if action=="get": val,=_need(p,"settingId");used.add("settingId");path+="/"+val
  elif resource=="calendarList":
   path="users/me/calendarList"
   if action in ("get","patch","update","delete"): val,=_need(p,"calendarId");used.add("calendarId");path+="/"+val
   if action=="watch":path+="/watch"
  elif resource=="calendars":
   path="calendars"
   if action not in ("insert",): val,=_need(p,"calendarId");used.add("calendarId");path+="/"+val
   if action in ("clear","transferOwnership"):path+="/"+action
  elif resource=="events":
   cal,=_need(p,"calendarId");used.add("calendarId");path=f"calendars/{cal}/events"
   if action in ("get","instances","patch","update","move","delete"):
    ev,=_need(p,"eventId");used.add("eventId");path+="/"+ev
   if action in ("instances","move"):path+="/"+action
   if action in ("quickAdd","watch"):path+="/"+action
  elif resource=="freebusy":path="freeBusy"
  elif resource=="acl":
   cal,=_need(p,"calendarId");used.add("calendarId");path=f"calendars/{cal}/acl"
   if action in ("get","patch","update","delete"):
    rule,=_need(p,"ruleId");used.add("ruleId");path+="/"+rule
   if action=="watch":path+="/watch"
  elif resource=="channels":path="channels/stop"
  methods={"list":"GET","get":"GET","instances":"GET","insert":"POST","import":"POST","quickAdd":"POST","watch":"POST","query":"POST","stop":"POST","clear":"POST","transferOwnership":"POST","move":"POST","patch":"PATCH","update":"PUT","delete":"DELETE"};method=methods[action]
 elif service=="drive":
  base="https://www.googleapis.com/drive/v3";resource=parts[1]
  if resource=="about":path="about"
  elif resource in ("files","folders"):
   path="files"
   if action in ("get","copy","update","move","trash","untrash","delete","download","export","watch"):
    fid,=_need(p,"fileId");used.add("fileId");path+="/"+fid
   if action in ("copy","watch"):path+="/"+action
   if action=="export":path+="/export"
   if action in ("emptyTrash","generateIds"):path="files/"+action
   if action=="download": query["alt"]="media"
   if action=="export":
    mime,=_need(p,"mimeType");used.add("mimeType");query["mimeType"]=p["mimeType"]
  elif resource in ("permissions","comments","revisions"):
   fid,=_need(p,"fileId");used.add("fileId");path=f"files/{fid}/{resource}"
   key={"permissions":"permissionId","comments":"commentId","revisions":"revisionId"}[resource]
   if resource=="comments" and len(parts)>3 and parts[2]=="replies":
    cid,=_need(p,"commentId");used.add("commentId");path+=f"/{cid}/replies"
    if action in ("get","update","delete"):rid,=_need(p,"replyId");used.add("replyId");path+="/"+rid
   elif action in ("get","update","delete"):
    val,=_need(p,key);used.add(key);path+="/"+val
  elif resource=="sharedDrives":
   path="drives"
   if action in ("get","update","hide","unhide","delete"):
    did,=_need(p,"driveId");used.add("driveId");path+="/"+did
   if action in ("hide","unhide"):path+="/"+action
  elif resource=="changes":
   path="changes/startPageToken" if action=="startPageToken" else "changes"
   if action=="watch":path+="/watch"
  elif resource=="channels":path="channels/stop"
  methods={"list":"GET","search":"GET","get":"GET","startPageToken":"GET","generateIds":"GET","download":"GET","export":"GET","create":"POST","copy":"POST","watch":"POST","stop":"POST","hide":"POST","unhide":"POST","patch":"PATCH","update":"PATCH","move":"PATCH","trash":"PATCH","untrash":"PATCH","delete":"DELETE","emptyTrash":"DELETE","upload":"POST"};method=methods[action]
  if command=="drive.sharedDrives.create":
   if not p.get("requestId"): raise OperationError("params.requestId is required by Drive shared-drive creation")
  if command=="drive.files.upload" or (command in ("drive.files.create","drive.files.update") and p.get("uploadType")):
   upload_type=p.get("uploadType","resumable");query["uploadType"]=upload_type
   base="https://www.googleapis.com/upload/drive/v3"
   path="files"+("/"+_need(p,"fileId")[0] if command=="drive.files.update" else "")
 else: raise OperationError("unsupported service")
 url=base+"/"+path
 return {"service":service,"version":version,"action":action,"method":method,"url":url,"query":query,"pathParams":used}

def preflight(command:str, params:dict) -> dict:
 """Return a provider-valid, non-mutating check for a mutation.

 The mapping is deliberately independent of the mutation URL.  ``etag`` says
 whether the returned resource is the object whose version guards execution.
 A null URL is an explicit local-only precondition for operations for which the
 provider exposes no useful read (notably channel stop and mailbox actions).
 """
 op=operation(command,params); url=op["url"]
 action=command.rsplit(".",1)[-1]
 # Existing-resource mutations can be checked through the canonical resource.
 suffixes=("/modify","/trash","/untrash","/send","/verify","/setDefault","/clear","/transferOwnership","/move","/copy","/watch","/hide","/unhide")
 if action in ("patch","update","delete","move","trash","untrash","hide","unhide","setDefault"):
  read=url
  for suffix in suffixes:
   if read.endswith(suffix):read=read[:-len(suffix)]
  # Do not request a synthetic `etag` field. Several Google resource families
  # expose version tags only as HTTP headers, and others have no such field.
  # An unfiltered GET remains valid across these resource endpoints.
  return {"method":"GET","url":read,"query":{},"etag":True,"strategy":"resource"}
 # Creates validate a readable parent/identity, without pretending it has an ETag.
 if action in ("create","insert","import","send","quickAdd","start","watch","batchModify","batchDelete","stop","clear","transferOwnership","copy") or command.endswith(".emptyTrash"):
  if command.startswith("gmail."):
   return {"method":"GET","url":"https://gmail.googleapis.com/gmail/v1/users/me/profile","query":{},"etag":False,"strategy":"identity"}
  if command.startswith("calendar."):
   if command=="calendar.channels.stop":return {"method":None,"url":None,"query":{},"etag":False,"strategy":"validated-body"}
   cal=params.get("calendarId")
   check=("https://www.googleapis.com/calendar/v3/calendars/"+_q(cal)) if cal else "https://www.googleapis.com/calendar/v3/users/me/calendarList"
   return {"method":"GET","url":check,"query":{},"etag":False,"strategy":"parent"}
  if command.startswith("drive."):
   if command=="drive.channels.stop":return {"method":None,"url":None,"query":{},"etag":False,"strategy":"validated-body"}
   fid=params.get("fileId")
   check=("https://www.googleapis.com/drive/v3/files/"+_q(fid)) if fid else "https://www.googleapis.com/drive/v3/about"
   return {"method":"GET","url":check,"query":{"fields":"id"} if fid else {"fields":"user"},"etag":False,"strategy":"parent-or-identity"}
 return {"method":None,"url":None,"query":{},"etag":False,"strategy":"validated-input"}
