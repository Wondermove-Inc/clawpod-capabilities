"""Provider-specific request contracts shared by schema generation and runtime validation."""
from __future__ import annotations

S=lambda **kw:{"type":"string","minLength":1,"maxLength":4096,**kw}
GMAIL_RAW_MAX_CHARS=50_000_000
B=lambda **kw:{"type":"boolean",**kw}
I=lambda **kw:{"type":"integer",**kw}
A=lambda item=S(),**kw:{"type":"array","items":item,**kw}
def O(props=None,required=(),**kw):
 d={"type":"object","additionalProperties":kw.pop("additionalProperties",False),"properties":props or {}}
 if required:d["required"]=list(required)
 d.update(kw);return d
EMAIL=S(format="email",maxLength=320)
COMPOSE=O({"from":EMAIL,"to":A(EMAIL,maxItems=2000),"cc":A(EMAIL,maxItems=2000),"bcc":A(EMAIL,maxItems=2000),"replyTo":EMAIL,"subject":S(maxLength=998),"text":S(maxLength=10000000),"html":S(maxLength=10000000),"headers":O({},additionalProperties=S(maxLength=10000)),"attachments":A(O({"path":S(maxLength=4096),"filename":S(maxLength=255),"mimeType":S(maxLength=255),"contentId":S(maxLength=998),"disposition":S(enum=["attachment","inline"])},("path",)),maxItems=100)},minProperties=1)
FILTER_CRITERIA=O({"from":S(),"to":S(),"subject":S(),"query":S(maxLength=20000),"negatedQuery":S(maxLength=20000),"hasAttachment":B(),"excludeChats":B(),"size":I(minimum=0),"sizeComparison":S(enum=["larger","smaller"])},minProperties=1)
FILTER_ACTION=O({"addLabelIds":A(maxItems=100),"removeLabelIds":A(maxItems=100),"forward":EMAIL},minProperties=1)
SMTP_MSA=O({"host":S(maxLength=253),"port":I(minimum=1,maximum=65535),"username":S(maxLength=320),"password":S(maxLength=4096),"securityMode":S(enum=["none","ssl","starttls"])},("host","port","securityMode"))
CONFERENCE=O({"createRequest":O({"requestId":S(maxLength=256),"conferenceSolutionKey":O({"type":S(enum=["eventHangout","eventNamedHangout","hangoutsMeet","addOn"])},("type",))},("requestId",)),"conferenceId":S(),"signature":S(),"notes":S(),"entryPoints":A(O({"entryPointType":S(enum=["video","phone","sip","more"]),"uri":S(format="uri"),"label":S(),"pin":S(),"accessCode":S(),"meetingCode":S(),"passcode":S(),"password":S()},("entryPointType","uri")),maxItems=20)},minProperties=1)
DRIVE_RESTRICTIONS=O({"adminManagedRestrictions":B(),"copyRequiresWriterPermission":B(),"domainUsersOnly":B(),"downloadRestriction":O({"itemDownloadRestriction":S(enum=["restrictedForReaders","restrictedForWriters"])}),"driveMembersOnly":B(),"sharingFoldersRequiresOrganizerPermission":B()})
CHANNEL=O({"id":S(maxLength=256),"type":S(enum=["web_hook"]),"address":S(format="uri",maxLength=2048),"token":S(maxLength=256),"params":O({"ttl":S(pattern="^[0-9]+$")}),"expiration":S(pattern="^[0-9]+$")},("id","type","address"))
STOP_CHANNEL=O({"id":S(maxLength=256),"resourceId":S(maxLength=512)},("id","resourceId"))

# Exact bodies for commands whose provider semantics require fields. Remaining bodies
# are selected by resource family below, never an unrestricted generic object.
EXACT={
 "gmail.messages.modify":O({"addLabelIds":A(maxItems=100),"removeLabelIds":A(maxItems=100)}),
 "gmail.messages.batchModify":O({"ids":A(maxItems=1000),"addLabelIds":A(maxItems=100),"removeLabelIds":A(maxItems=100)},("ids",)),
 "gmail.messages.batchDelete":O({"ids":A(maxItems=1000)},("ids",)),
 "gmail.labels.create":O({"name":S(maxLength=225),"messageListVisibility":S(enum=["show","hide"]),"labelListVisibility":S(enum=["labelShow","labelShowIfUnread","labelHide"]),"color":O({"textColor":S(),"backgroundColor":S()})},("name",)),
 "gmail.labels.patch":O({"name":S(maxLength=225),"messageListVisibility":S(enum=["show","hide"]),"labelListVisibility":S(enum=["labelShow","labelShowIfUnread","labelHide"]),"color":O({"textColor":S(),"backgroundColor":S()})},minProperties=1),
 "gmail.labels.update":O({"name":S(maxLength=225),"messageListVisibility":S(enum=["show","hide"]),"labelListVisibility":S(enum=["labelShow","labelShowIfUnread","labelHide"]),"color":O({"textColor":S(),"backgroundColor":S()})},("name",)),
 "gmail.watch.start":O({"topicName":S(pattern="^projects/[^/]+/topics/[^/]+$"),"labelIds":A(maxItems=100),"labelFilterBehavior":S(enum=["include","exclude"])},("topicName",)),
 "calendar.freebusy.query":O({"timeMin":S(format="date-time"),"timeMax":S(format="date-time"),"timeZone":S(),"groupExpansionMax":I(minimum=1,maximum=100),"calendarExpansionMax":I(minimum=1,maximum=50),"items":A(O({"id":S()},("id",)),maxItems=50)},("timeMin","timeMax","items")),
 "calendar.channels.stop":STOP_CHANNEL,"drive.channels.stop":STOP_CHANNEL,
 "calendar.calendarList.watch":CHANNEL,"calendar.events.watch":CHANNEL,"calendar.acl.watch":CHANNEL,"drive.changes.watch":CHANNEL,"drive.files.watch":CHANNEL,
 "drive.permissions.create":O({"type":S(enum=["user","group","domain","anyone"]),"role":S(enum=["owner","organizer","fileOrganizer","writer","commenter","reader"]),"emailAddress":EMAIL,"domain":S(),"expirationTime":S(format="date-time"),"allowFileDiscovery":B(),"pendingOwner":B()},("type","role")),
 "drive.permissions.update":O({"role":S(enum=["owner","organizer","fileOrganizer","writer","commenter","reader"]),"expirationTime":S(format="date-time"),"removeExpiration":B(),"pendingOwner":B()},minProperties=1),
 "drive.comments.create":O({"content":S(maxLength=32768),"quotedFileContent":O({"mimeType":S(),"value":S(maxLength=32768)})},("content",)),
 "drive.comments.update":O({"content":S(maxLength=32768)},("content",)),
 "drive.comments.replies.create":O({"content":S(maxLength=32768),"action":S(enum=["resolve","reopen"])},minProperties=1),
 "drive.comments.replies.update":O({"content":S(maxLength=32768)},("content",)),
 "drive.sharedDrives.create":O({"name":S(maxLength=128)},("name",)),
}

def body_schema(command,method):
 if command=='gmail.watch.stop':return None
 if command=='gmail.settings.update':return O({"enabled":B(),"emailAddress":EMAIL,"disposition":S(enum=["archive","leaveInInbox","markRead","trash"]),"accessWindow":S(enum=["allMail","fromNowOn"]),"expungeBehavior":S(enum=["archive","deleteForever","trash"]),"language":S(),"responseSubject":S(),"responseBodyPlainText":S(maxLength=10000),"responseBodyHtml":S(maxLength=20000),"restrictToContacts":B(),"startTime":S(pattern="^[0-9]+$"),"endTime":S(pattern="^[0-9]+$")},minProperties=1)
 if command in EXACT:return EXACT[command]
 p=command.split('.'); action=p[-1]
 if method not in ("POST","PUT","PATCH"):return None
 if action in ("trash","untrash"):return O({"trashed":B()},("trashed",))
 if command.startswith("gmail.messages.") or command.startswith("gmail.drafts."):
  if action in ("send","create","update","insert","import"):
   return O({"raw":S(maxLength=GMAIL_RAW_MAX_CHARS),"compose":COMPOSE,"threadId":S(),"labelIds":A(maxItems=100),"internalDateSource":S(enum=["receivedTime","dateHeader"]),"neverMarkSpam":B(),"processForCalendar":B()},minProperties=1)
 if command.startswith("gmail.threads.") and action=="modify":return O({"addLabelIds":A(maxItems=100),"removeLabelIds":A(maxItems=100)},minProperties=1)
 if command.startswith("gmail.settings."):
  if ".filters.create" in command:return O({"criteria":FILTER_CRITERIA,"action":FILTER_ACTION},("criteria","action"))
  if any(x in command for x in ("forwardingAddresses.create","delegates.create")):return O({"forwardingEmail":EMAIL,"delegateEmail":EMAIL},minProperties=1)
  if ".sendAs." in command:return O({"sendAsEmail":EMAIL,"displayName":S(),"replyToAddress":EMAIL,"signature":S(maxLength=10000),"isDefault":B(),"treatAsAlias":B(),"smtpMsa":SMTP_MSA,"verificationStatus":S(enum=["accepted","pending"])},minProperties=1)
  if ".smime.insert" in command:return O({"pkcs12":S(),"encryptedKeyPassword":S()},("pkcs12","encryptedKeyPassword"))
  if ".smime.setDefault" in command:return O({})
  return O({"enabled":B(),"emailAddress":EMAIL,"disposition":S(enum=["archive","leaveInInbox","markRead","trash"]),"accessWindow":S(enum=["allMail","fromNowOn"]),"expungeBehavior":S(enum=["archive","deleteForever","trash"]),"language":S(),"responseSubject":S(),"responseBodyPlainText":S(maxLength=10000),"responseBodyHtml":S(maxLength=20000),"restrictToContacts":B(),"startTime":S(pattern="^[0-9]+$"),"endTime":S(pattern="^[0-9]+$")},minProperties=1)
 if command.startswith("calendar.events."):
  return O({"id":S(),"summary":S(),"description":S(),"location":S(),"start":O({"date":S(format="date"),"dateTime":S(format="date-time"),"timeZone":S()}),"end":O({"date":S(format="date"),"dateTime":S(format="date-time"),"timeZone":S()}),"attendees":A(O({"email":EMAIL,"optional":B(),"resource":B(),"displayName":S(),"comment":S(),"additionalGuests":I(minimum=0)}),maxItems=2000),"recurrence":A(maxItems=100),"status":S(),"visibility":S(),"transparency":S(),"conferenceData":CONFERENCE,"extendedProperties":O({"private":O({},additionalProperties=S()),"shared":O({},additionalProperties=S())})},minProperties=1)
 if command.startswith("calendar.acl."):return O({"scope":O({"type":S(enum=["default","user","group","domain"]),"value":S()},("type",)),"role":S(enum=["none","freeBusyReader","reader","writer","owner"])},("scope","role") if action=="insert" else (),minProperties=1)
 if command.startswith("calendar.calendars."):return O({"summary":S(),"description":S(),"location":S(),"timeZone":S()},("summary",) if action=="insert" else (),minProperties=1)
 if command.startswith("calendar.calendarList."):return O({"id":S(),"colorRgbFormat":B(),"backgroundColor":S(),"foregroundColor":S(),"hidden":B(),"selected":B(),"summaryOverride":S()},("id",) if action=="insert" else (),minProperties=1)
 if command.startswith(("drive.files.","drive.folders.")):
  return O({"name":S(maxLength=32768),"mimeType":S(),"description":S(),"parents":A(maxItems=1),"trashed":B(),"starred":B(),"appProperties":O({},**{"additionalProperties":{"type":"string"}}),"properties":O({},**{"additionalProperties":{"type":"string"}})},minProperties=1)
 if command.startswith("drive.revisions."):return O({"keepForever":B(),"published":B(),"publishAuto":B(),"publishedOutsideDomain":B()},minProperties=1)
 if command.startswith("drive.sharedDrives."):return O({"name":S(maxLength=128),"hidden":B(),"restrictions":DRIVE_RESTRICTIONS},minProperties=1)
 return O({},minProperties=1)

QUERY_TYPES={
 "q":S(maxLength=20000),"query":S(maxLength=20000),"orderBy":S(maxLength=1024),"timeMin":S(format="date-time"),"timeMax":S(format="date-time"),"syncToken":S(maxLength=4096),"startHistoryId":S(pattern="^[0-9]+$"),"pageToken":S(maxLength=4096),"corpora":S(enum=["user","domain","drive","allDrives"]),"spaces":S(pattern="^(drive|appDataFolder|photos)(,(drive|appDataFolder|photos))*$"),"driveId":S(),"includeItemsFromAllDrives":B(),"supportsAllDrives":B(),"sendUpdates":S(enum=["all","externalOnly","none"]),"sendNotificationEmail":B(),"transferOwnership":B(),"useDomainAdminAccess":B(),"moveToNewOwnersRoot":B(),"enforceSingleParent":B(),"removeParents":S(),"addParents":S(),"destination":S(),"text":S(),"showDeleted":B(),"singleEvents":B(),"showHiddenInvitations":B(),"maxAttendees":I(minimum=1),"eventTypes":A(maxItems=20),"iCalUID":S(),"privateExtendedProperty":A(maxItems=100),"sharedExtendedProperty":A(maxItems=100),"conferenceDataVersion":I(enum=[0,1]),"maxResults":I(minimum=1,maximum=2500),"mimeType":S(),"requestId":S(),"uploadType":S(enum=["simple","media","multipart","resumable"]),"acknowledgeAbuse":B(),"includePermissionsForView":S(enum=["published"]),"includeLabels":S(),"keepRevisionForever":B(),"ocrLanguage":S(),"ignoreDefaultVisibility":B(),"sendNotifications":B(),"prettyPrint":B()
}
