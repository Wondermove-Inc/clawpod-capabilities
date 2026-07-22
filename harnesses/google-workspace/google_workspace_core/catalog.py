"""Declarative Google Workspace operation catalog and REST mapping."""
from __future__ import annotations
import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "harness.json"

def catalog() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["commands"]

def service_for(command: str) -> tuple[str, str]:
    if command.startswith("gmail."): return "gmail", "v1"
    if command.startswith("calendar."): return "calendar", "v3"
    if command.startswith("drive."): return "drive", "v3"
    return "oauth", "v2"

COLLECTIONS={
 "gmail":{"profile":"profile","messages":"messages","threads":"threads","attachments":"messages/{messageId}/attachments","labels":"labels","drafts":"drafts","history":"history","watch":"watch","settings":"settings"},
 "calendar":{"colors":"colors","settings":"users/me/settings","calendarList":"users/me/calendarList","calendars":"calendars","events":"calendars/{calendarId}/events","freebusy":"freeBusy","acl":"calendars/{calendarId}/acl","channels":"channels"},
 "drive":{"about":"about","files":"files","folders":"files","permissions":"files/{fileId}/permissions","comments":"files/{fileId}/comments","revisions":"files/{fileId}/revisions","sharedDrives":"drives","changes":"changes","channels":"channels"}}

def operation(command:str, params:dict) -> dict:
    service,version=service_for(command); parts=command.split("."); resource=parts[1]; action=".".join(parts[2:])
    if service=="drive" and resource=="comments" and len(parts)>3 and parts[2]=="replies": resource="replies"; action=".".join(parts[3:])
    base={"gmail":"https://gmail.googleapis.com/gmail/v1/users/{userId}","calendar":"https://www.googleapis.com/calendar/v3","drive":"https://www.googleapis.com/drive/v3"}.get(service,"")
    if service=="oauth": return {"service":service,"version":version,"action":action,"method":"LOCAL","url":""}
    path="files/{fileId}/comments/{commentId}/replies" if resource=="replies" else COLLECTIONS[service][resource]
    p={"userId":"me",**params}
    # nested Gmail settings resources
    if service=="gmail" and resource=="settings" and len(parts)>3:
        sub=parts[2]; action=".".join(parts[3:]); path="settings/"+{"forwardingAddresses":"forwardingAddresses","sendAs":"sendAs","delegates":"delegates","smime":"sendAs/{sendAsEmail}/smimeInfo","filters":"filters"}.get(sub,sub)
        resource=sub
    idkeys={"messages":"messageId","threads":"threadId","labels":"labelId","drafts":"draftId","attachments":"attachmentId","calendarList":"calendarId","calendars":"calendarId","events":"eventId","acl":"ruleId","files":"fileId","permissions":"permissionId","comments":"commentId","revisions":"revisionId","sharedDrives":"driveId","settings":"settingId"}
    if resource=="replies": path="files/{fileId}/comments/{commentId}/replies"; idkeys[resource]="replyId"
    if action in ("get","update","patch","delete","trash","untrash","send","verify","setDefault","move","watch") and resource in idkeys:
        key=idkeys[resource]
        if key in p and ("{"+key+"}") not in path: path += "/{"+key+"}"
    suffix={"trash":":trash","untrash":":untrash","modify":":modify","batchModify":"/batchModify","batchDelete":"/batchDelete","send":":send","import":"/import","insert":"","quickAdd":"/quickAdd","instances":"/instances","move":"/move","watch":"/watch","emptyTrash":"/trash","generateIds":"/generateIds","startPageToken":"/startPageToken","hide":"/hide","unhide":"/unhide","clear":"/clear","transferOwnership":"/transferOwnership","stop":"/stop"}.get(action,"")
    if suffix.startswith(":"): path+=suffix
    elif suffix and not path.endswith(suffix): path+=suffix
    for k,v in p.items(): path=path.replace("{"+k+"}",str(v))
    methods={"list":"GET","get":"GET","search":"GET","instances":"GET","startPageToken":"GET","generateIds":"GET","create":"POST","insert":"POST","import":"POST","send":"POST","quickAdd":"POST","copy":"POST","move":"POST","watch":"POST","stop":"POST","query":"POST","transferOwnership":"POST","patch":"PATCH","update":"PUT","modify":"POST","batchModify":"POST","trash":"POST","untrash":"POST","hide":"POST","unhide":"POST","setDefault":"POST","verify":"POST","delete":"DELETE","batchDelete":"POST","clear":"POST","emptyTrash":"DELETE","upload":"POST","download":"GET","export":"GET"}
    return {"service":service,"version":version,"resource":resource,"action":action,"method":methods.get(action,"GET"),"url":base.format(**p)+"/"+path.lstrip("/")}
