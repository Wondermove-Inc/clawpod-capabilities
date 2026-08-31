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
 # One editor request per item: exactly one verb key (insertText, updateCells,
 # createSlide, ...) whose value is that verb's request object. Typed as a
 # closed single-key envelope because the provider unions are per-verb objects.
 EDITOR_REQUESTS=A({"type":"object","minProperties":1,"maxProperties":1,"additionalProperties":{"type":"object"}},minItems=1,maxItems=500)
 VALUE_CELL={"type":["string","number","boolean","null"]}
 VALUE_RANGE=O({"range":S(),"majorDimension":S(enum=["ROWS","COLUMNS"]),"values":A(A(VALUE_CELL,maxItems=10000),minItems=1,maxItems=100000)},("values",))
 RENDER=S(enum=["FORMATTED_VALUE","UNFORMATTED_VALUE","FORMULA"]);DATE_RENDER=S(enum=["SERIAL_NUMBER","FORMATTED_STRING"])
 GRID_RANGE=O({"sheetId":I(minimum=0),"startRowIndex":I(minimum=0),"endRowIndex":I(minimum=0),"startColumnIndex":I(minimum=0),"endColumnIndex":I(minimum=0)},minProperties=1)
 METADATA_LOOKUP=O({"locationType":S(enum=["ROW","COLUMN","SHEET","SPREADSHEET"]),"metadataId":I(minimum=0),"metadataKey":S(),"metadataValue":S(),"visibility":S(enum=["DOCUMENT","PROJECT"]),"locationMatchingStrategy":S(enum=["EXACT_LOCATION","INTERSECTING_LOCATION"]),"metadataLocation":O({"locationType":S(),"spreadsheet":B(),"sheetId":I(minimum=0),"dimensionRange":O({"sheetId":I(minimum=0),"dimension":S(enum=["ROWS","COLUMNS"]),"startIndex":I(minimum=0),"endIndex":I(minimum=0)})})},minProperties=1)
 DATA_FILTERS=A(O({"a1Range":S(),"gridRange":GRID_RANGE,"developerMetadataLookup":METADATA_LOOKUP},minProperties=1),minItems=1,maxItems=100)
 if command=="docs.documents.create":return O({"title":S(maxLength=4096)},minProperties=1)
 if command in ("docs.documents.batchUpdate","slides.presentations.batchUpdate"):
  return O({"requests":EDITOR_REQUESTS,"writeControl":O({"requiredRevisionId":S(),"targetRevisionId":S()})},("requests",))
 if command=="slides.presentations.create":return O({"title":S(maxLength=4096)},minProperties=1)
 if command=="sheets.spreadsheets.create":
  SHEET_STUB={"type":"object","minProperties":1,"additionalProperties":{"type":["object","array","string","number","boolean"]}}
  return O({"properties":O({"title":S(),"locale":S(),"timeZone":S(),"autoRecalc":S(enum=["ON_CHANGE","MINUTE","HOUR"])}),"sheets":A(SHEET_STUB,maxItems=200),"namedRanges":A(O({"namedRangeId":S(),"name":S(),"range":GRID_RANGE},minProperties=1),maxItems=500)},minProperties=1)
 if command=="sheets.spreadsheets.batchUpdate":
  return O({"requests":EDITOR_REQUESTS,"includeSpreadsheetInResponse":B(),"responseRanges":A(S(),maxItems=100),"responseIncludeGridData":B()},("requests",))
 if command=="sheets.spreadsheets.getByDataFilter":return O({"dataFilters":DATA_FILTERS,"includeGridData":B()},("dataFilters",))
 if command in ("sheets.values.update","sheets.values.append"):return VALUE_RANGE
 if command=="sheets.values.clear":return O({})
 if command=="sheets.values.batchUpdate":
  return O({"valueInputOption":S(enum=["RAW","USER_ENTERED"]),"data":A(VALUE_RANGE,minItems=1,maxItems=100),"includeValuesInResponse":B(),"responseValueRenderOption":RENDER,"responseDateTimeRenderOption":DATE_RENDER},("valueInputOption","data"))
 if command=="sheets.values.batchClear":return O({"ranges":A(S(),minItems=1,maxItems=100)},("ranges",))
 if command in ("sheets.values.batchGetByDataFilter","sheets.values.batchClearByDataFilter"):
  return O({"dataFilters":DATA_FILTERS,"majorDimension":S(enum=["ROWS","COLUMNS"]),"valueRenderOption":RENDER,"dateTimeRenderOption":DATE_RENDER},("dataFilters",))
 if command=="sheets.sheets.copyTo":return O({"destinationSpreadsheetId":S()},("destinationSpreadsheetId",))
 if command=="sheets.developerMetadata.search":return O({"dataFilters":DATA_FILTERS},("dataFilters",))
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
 "q":S(maxLength=20000),"query":S(maxLength=20000),"orderBy":S(maxLength=1024),"timeMin":S(format="date-time"),"timeMax":S(format="date-time"),"syncToken":S(maxLength=4096),"startHistoryId":S(pattern="^[0-9]+$"),"pageToken":S(maxLength=4096),"pageSize":I(minimum=1,maximum=500),"corpora":S(enum=["user","domain","drive","allDrives"]),"spaces":S(pattern="^(drive|appDataFolder|photos)(,(drive|appDataFolder|photos))*$"),"driveId":S(),"includeItemsFromAllDrives":B(),"supportsAllDrives":B(),"sendUpdates":S(enum=["all","externalOnly","none"]),"sendNotificationEmail":B(),"transferOwnership":B(),"useDomainAdminAccess":B(),"moveToNewOwnersRoot":B(),"enforceSingleParent":B(),"removeParents":S(),"addParents":S(),"destination":S(),"text":S(),"showDeleted":B(),"singleEvents":B(),"showHiddenInvitations":B(),"maxAttendees":I(minimum=1),"eventTypes":A(maxItems=20),"iCalUID":S(),"privateExtendedProperty":A(maxItems=100),"sharedExtendedProperty":A(maxItems=100),"conferenceDataVersion":I(enum=[0,1]),"maxResults":I(minimum=1,maximum=500),"mimeType":S(),"requestId":S(),"uploadType":S(enum=["simple","media","multipart","resumable"]),"acknowledgeAbuse":B(),"includePermissionsForView":S(enum=["published"]),"includeLabels":S(),"keepRevisionForever":B(),"ocrLanguage":S(),"ignoreDefaultVisibility":B(),"sendNotifications":B(),"prettyPrint":B(),"valueInputOption":{"type":"string","enum":["RAW","USER_ENTERED"]},"valueRenderOption":{"type":"string","enum":["FORMATTED_VALUE","UNFORMATTED_VALUE","FORMULA"]},"dateTimeRenderOption":{"type":"string","enum":["SERIAL_NUMBER","FORMATTED_STRING"]},"majorDimension":{"type":"string","enum":["ROWS","COLUMNS"]},"insertDataOption":{"type":"string","enum":["OVERWRITE","INSERT_ROWS"]},"includeValuesInResponse":{"type":"boolean"},"responseValueRenderOption":{"type":"string","enum":["FORMATTED_VALUE","UNFORMATTED_VALUE","FORMULA"]},"responseDateTimeRenderOption":{"type":"string","enum":["SERIAL_NUMBER","FORMATTED_STRING"]},"includeGridData":{"type":"boolean"},"ranges":{"type":"array","items":{"type":"string","minLength":1,"maxLength":4096},"maxItems":100},"suggestionsViewMode":{"type":"string","enum":["DEFAULT_FOR_CURRENT_ACCESS","SUGGESTIONS_INLINE","PREVIEW_SUGGESTIONS_ACCEPTED","PREVIEW_WITHOUT_SUGGESTIONS"]},"thumbnailProperties.mimeType":{"type":"string","enum":["PNG"]},"thumbnailProperties.thumbnailSize":{"type":"string","enum":["LARGE","MEDIUM","SMALL"]}
}
