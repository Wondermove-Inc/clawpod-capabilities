"""Command-to-minimum OAuth scope policy (one exact least-privilege scope per command)."""
GMAIL_META="https://www.googleapis.com/auth/gmail.metadata";GMAIL_READ="https://www.googleapis.com/auth/gmail.readonly";GMAIL_MOD="https://www.googleapis.com/auth/gmail.modify";GMAIL_LABELS="https://www.googleapis.com/auth/gmail.labels";GMAIL_COMPOSE="https://www.googleapis.com/auth/gmail.compose";GMAIL_SEND="https://www.googleapis.com/auth/gmail.send";GMAIL_INSERT="https://www.googleapis.com/auth/gmail.insert";GMAIL_SETTINGS="https://www.googleapis.com/auth/gmail.settings.basic";GMAIL_SHARING="https://www.googleapis.com/auth/gmail.settings.sharing";MAIL="https://mail.google.com/"
CAL_SETTINGS="https://www.googleapis.com/auth/calendar.settings.readonly";CAL_LIST_RO="https://www.googleapis.com/auth/calendar.calendarlist.readonly";CAL_LIST="https://www.googleapis.com/auth/calendar.calendarlist";CAL_CAL_RO="https://www.googleapis.com/auth/calendar.calendars.readonly";CAL_CAL="https://www.googleapis.com/auth/calendar.calendars";CAL_EVENTS_RO="https://www.googleapis.com/auth/calendar.events.readonly";CAL_EVENTS="https://www.googleapis.com/auth/calendar.events";CAL_FREE="https://www.googleapis.com/auth/calendar.freebusy";CAL_ACL_RO="https://www.googleapis.com/auth/calendar.acls.readonly";CAL_ACL="https://www.googleapis.com/auth/calendar.acls";CAL="https://www.googleapis.com/auth/calendar"
DRIVE_META="https://www.googleapis.com/auth/drive.metadata.readonly";DRIVE_READ="https://www.googleapis.com/auth/drive.readonly";DRIVE_FILE="https://www.googleapis.com/auth/drive.file";DRIVE="https://www.googleapis.com/auth/drive"
def required_scopes(c,safety=()):
 a=c.rsplit('.',1)[-1]
 if c.startswith('gmail.settings.'):
  return {GMAIL_SHARING if any(x in c for x in ('forwardingAddresses','delegates','.smime.')) else GMAIL_SETTINGS}
 if c.startswith('gmail.labels.'):
  return {GMAIL_LABELS}
 if c in ('gmail.profile.get','gmail.history.list'):return {GMAIL_META}
 if c.startswith('gmail.watch.'):return {GMAIL_MOD}
 if c.startswith('gmail.messages.') or c.startswith('gmail.threads.'):
  if a in ('delete','batchDelete'):return {MAIL}
  if a=='send':return {GMAIL_SEND}
  if a in ('insert','import'):return {GMAIL_INSERT}
  if a in ('list','get'):return {GMAIL_READ}
  return {GMAIL_MOD}
 if c.startswith('gmail.drafts.'):
  if a in ('list','get'):return {GMAIL_READ}
  if a=='send':return {GMAIL_COMPOSE}
  return {GMAIL_COMPOSE}
 if c.startswith('gmail.attachments.'):return {GMAIL_READ}
 if c.startswith('calendar.settings.') or c=='calendar.colors.get':return {CAL_SETTINGS}
 if c.startswith('calendar.calendarList.'):return {CAL_LIST_RO if a in ('list','get') else CAL_LIST}
 if c.startswith('calendar.calendars.'):return {CAL_CAL_RO if a=='get' else (CAL if a in ('delete','clear','transferOwnership') else CAL_CAL)}
 if c.startswith('calendar.events.'):return {CAL_EVENTS_RO if a in ('list','get','instances') else CAL_EVENTS}
 if c=='calendar.freebusy.query':return {CAL_FREE}
 if c.startswith('calendar.acl.'):return {CAL_ACL_RO if a in ('list','get') else CAL_ACL}
 if c.startswith('calendar.channels.'):return {CAL}
 if c.startswith('drive.'):
  if c.startswith(('drive.permissions.','drive.sharedDrives.','drive.channels.')):return {DRIVE}
  if c.startswith(('drive.comments.','drive.revisions.')):return {DRIVE_READ if a in ('list','get') else DRIVE}
  if c.startswith(('drive.about.','drive.files.list','drive.files.search','drive.changes.')):return {DRIVE_META}
  if a in ('get','download','export'):return {DRIVE_READ}
  return {DRIVE_FILE}
 return set()
def enforce(command,granted,safety=()):
 required=required_scopes(command,safety);g=set(granted or [])
 if MAIL in g:g|={GMAIL_META,GMAIL_READ,GMAIL_MOD,GMAIL_LABELS,GMAIL_COMPOSE,GMAIL_SEND,GMAIL_INSERT,GMAIL_SETTINGS,GMAIL_SHARING}
 if GMAIL_MOD in g:g|={GMAIL_META,GMAIL_READ,GMAIL_LABELS}
 if GMAIL_READ in g:g|={GMAIL_META}
 if GMAIL_COMPOSE in g:g|={GMAIL_SEND,GMAIL_READ}
 if CAL in g:g|={CAL_SETTINGS,CAL_LIST_RO,CAL_LIST,CAL_CAL_RO,CAL_CAL,CAL_EVENTS_RO,CAL_EVENTS,CAL_FREE,CAL_ACL_RO,CAL_ACL}
 if CAL_EVENTS in g:g.add(CAL_EVENTS_RO)
 if CAL_LIST in g:g.add(CAL_LIST_RO)
 if CAL_CAL in g:g.add(CAL_CAL_RO)
 if CAL_ACL in g:g.add(CAL_ACL_RO)
 if DRIVE in g:g|={DRIVE_META,DRIVE_READ,DRIVE_FILE}
 if DRIVE_READ in g:g.add(DRIVE_META)
 missing=required-g
 if missing:raise PermissionError('missing required OAuth scope(s): '+', '.join(sorted(missing)))
 return sorted(required)
