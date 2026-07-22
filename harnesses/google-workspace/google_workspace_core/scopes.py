"""Complete command-to-minimum OAuth scope policy."""
from __future__ import annotations
GMAIL_READ="https://www.googleapis.com/auth/gmail.readonly";GMAIL_MOD="https://www.googleapis.com/auth/gmail.modify";GMAIL_COMPOSE="https://www.googleapis.com/auth/gmail.compose";GMAIL_SEND="https://www.googleapis.com/auth/gmail.send";GMAIL_SETTINGS="https://www.googleapis.com/auth/gmail.settings.basic";GMAIL_SHARING="https://www.googleapis.com/auth/gmail.settings.sharing"
CAL_READ="https://www.googleapis.com/auth/calendar.readonly";CAL_EVENTS="https://www.googleapis.com/auth/calendar.events";CAL="https://www.googleapis.com/auth/calendar";CAL_ACL="https://www.googleapis.com/auth/calendar.acl"
DRIVE_READ="https://www.googleapis.com/auth/drive.readonly";DRIVE_FILE="https://www.googleapis.com/auth/drive.file";DRIVE="https://www.googleapis.com/auth/drive"
def required_scopes(command,safety=()):
 a=command.rsplit('.',1)[-1]
 if command.startswith('gmail.settings.'):
  return {GMAIL_SHARING if any(x in command for x in ('forwardingAddresses','delegates')) else GMAIL_SETTINGS}
 if command.startswith('gmail.'):
  if a in ('send','insert','import','create','update'):return {GMAIL_COMPOSE}
  if a in ('list','get'):return {GMAIL_READ}
  return {GMAIL_MOD}
 if command.startswith('calendar.acl.'):return {CAL_ACL}
 if command.startswith('calendar.'):
  if command.startswith(('calendar.events.','calendar.freebusy.')) and a not in ('list','get','instances'):return {CAL_EVENTS}
  return {CAL_READ} if a in ('list','get','instances') else {CAL}
 if command.startswith('drive.'):
  return {DRIVE_READ} if a in ('list','search','get','download','export','startPageToken') else ({DRIVE_FILE} if command.startswith('drive.files.') else {DRIVE})
 return set()
def enforce(command,granted,safety=()):
 required=required_scopes(command,safety); granted=set(granted or [])
 # broader scopes imply narrow scopes
 if GMAIL_MOD in granted:granted|={GMAIL_READ}
 if CAL in granted:granted|={CAL_READ,CAL_EVENTS,CAL_ACL}
 if DRIVE in granted:granted|={DRIVE_READ,DRIVE_FILE}
 missing=required-granted
 if missing:raise PermissionError('missing required OAuth scope(s): '+', '.join(sorted(missing)))
 return sorted(required)
