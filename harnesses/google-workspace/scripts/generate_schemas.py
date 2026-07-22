#!/usr/bin/env python3
"""Deterministically specialize every command schema from checked provider contracts."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from google_workspace_core.catalog import operation
from google_workspace_core.scopes import required_scopes
from google_workspace_core.contracts import body_schema,QUERY_TYPES,S,O,A
p=ROOT/'harness.json';doc=json.loads(p.read_text())
SAMPLES={k:k for k in ('messageId','threadId','attachmentId','labelId','draftId','calendarId','eventId','ruleId','settingId','fileId','permissionId','commentId','replyId','revisionId','driveId','sendAsEmail','smimeInfoId','forwardingEmail','delegateEmail','filterId')};SAMPLES.update(userId='me',kind='imap',mimeType='text/plain',requestId='request',pageToken='page')
PAGED={'list','search','instances'}
def allowed_query(cmd,action):
 out=set()
 if action in PAGED:out|={'q','query','orderBy','maxResults'}
 if cmd.startswith('gmail.messages.list'):out|={'labelIds','includeSpamTrash'}
 if cmd.startswith('gmail.threads.list'):out|={'labelIds','includeSpamTrash'}
 if cmd=='gmail.history.list':out|={'startHistoryId','labelId','historyTypes'}
 if cmd.startswith('calendar.events.'):
  out|={'timeMin','timeMax','timeZone','sendUpdates','maxAttendees','conferenceDataVersion'}
  if action in ('list','instances','watch'):out|={'syncToken','showDeleted','singleEvents','showHiddenInvitations','eventTypes','iCalUID','privateExtendedProperty','sharedExtendedProperty'}
  if action=='quickAdd':out|={'text'}
  if action=='move':out|={'destination'}
 if cmd.startswith('calendar.acl.'):out|={'showDeleted','syncToken','sendNotifications'}
 if cmd.startswith('calendar.calendarList.'):out|={'showDeleted','showHidden'}
 if cmd.startswith('drive.'):
  out|={'supportsAllDrives'}
  if cmd.startswith(('drive.files.list','drive.files.search')):out|={'q','orderBy','corpora','spaces','driveId','includeItemsFromAllDrives'}
  if cmd.startswith(('drive.changes.','drive.sharedDrives.list')):out|={'driveId','includeItemsFromAllDrives','useDomainAdminAccess'}
  if cmd.startswith('drive.permissions.'):out|={'sendNotificationEmail','transferOwnership','useDomainAdminAccess','moveToNewOwnersRoot','enforceSingleParent'}
  if cmd=='drive.files.move':out|={'addParents','removeParents'}
  if cmd.startswith(('drive.files.create','drive.files.update','drive.files.upload')):out|={'uploadType','addParents','removeParents','keepRevisionForever','ocrLanguage','ignoreDefaultVisibility'}
  if action in ('download','export','get'):out|={'acknowledgeAbuse','includePermissionsForView','includeLabels'}
 if cmd=='drive.sharedDrives.create':out|={'requestId'}
 if cmd.startswith('drive.changes.') and action!='startPageToken':out|={'pageToken'}
 return out
SAFETY_MAP={
 'credentialRelated':('secretUse','authReuse'),
 'externallyVisible':('externalSideEffect','humanAccountAction'),
 'externalWrite':('externalSideEffect','humanAccountAction'),
}
def logical_name(key,command):
 return command.get('baseArgv',[key])[0]
def manifest_name(command):
 # Runtime command identifiers are lowercase. Preserve the provider spelling in
 # baseArgv while exposing a lifecycle-safe kebab-case alias.
 return '.'.join(re.sub(r'(?<!^)(?=[A-Z])','-',part).lower() for part in command.split('.'))

commands={logical_name(key,c):c for key,c in doc['commands'].items()}
for cmd,c in commands.items():
 mapped=[]
 for safety in c.get('safetyClasses',[]):
  mapped.extend(SAFETY_MAP.get(safety,(safety,)))
 c['safetyClasses']=list(dict.fromkeys(mapped))
 for arg in c.get('argMap',[]):
  if arg.get('valueType')=='json':arg['valueType']='string'
  if arg.get('valueType')=='boolean':arg['type']='booleanFlag'
 # Rich JSON values are serialized as strings by the lifecycle argv bridge,
 # then decoded and checked against the command-specific schema by the CLI.
 for name in ('fields','params','body','batch'):
  if name in c['inputSchema'].get('properties',{}):
   c['inputSchema']['properties'][name]={'type':'string'}
 c.pop('requiredScopes',None)
 s=c['inputSchema'];props=s['properties'];props['fields']={'type':'array','items':{'type':'string','minLength':1,'maxLength':512},'maxItems':100};props['expectedSha256']={'type':'string','pattern':'^[a-f0-9]{64}$'};props['batch']={'type':'array','minItems':1,'maxItems':100,'items':{'type':'object'}};s['required']=list(dict.fromkeys(s.get('required',[])))
 if cmd.startswith('auth.'):
  props['params']={'type':'object','additionalProperties':False,'properties':{}}
  props['body']=O({'profiles':A(S(),maxItems=32)}) if cmd=='auth.scopes.check' else O({})
  continue
 op=operation(cmd,SAMPLES);req=sorted(op['pathParams']);ps={'type':'object','additionalProperties':False,'properties':{}}
 for key in req:ps['properties'][key]=S()
 for key in sorted(allowed_query(cmd,op['action'])):
  ps['properties'][key]=QUERY_TYPES.get(key,{'type':['string','boolean','integer','array']})
 required_query={'calendar.events.quickAdd':['text'],'calendar.events.move':['destination'],'drive.changes.list':['pageToken'],'drive.changes.watch':['pageToken'],'drive.sharedDrives.create':['requestId']}.get(cmd,[])
 required=req+required_query
 if required:ps['required']=required
 props['params']=ps
 bs=body_schema(cmd,op['method'])
 if bs is None:
  props['body']={'type':'object','additionalProperties':False,'properties':{}}
 else:
  props['body']=bs
  if op['method'] in ('POST','PUT','PATCH') and op['action'] not in ('quickAdd','move','clear','setDefault','verify','hide','unhide') and 'body' not in s['required']:s['required'].append('body')
 if cmd=='drive.files.upload':s['required']=list(dict.fromkeys(s['required']+['inputPath','transferRoot']))
 if cmd in ('drive.files.download','drive.files.export'):s['required']=list(dict.fromkeys(s['required']+['outputPath','transferRoot']))

def close_objects(node):
 if isinstance(node,dict):
  if node.get('type')=='object':node.setdefault('additionalProperties',False)
  for value in node.values():close_objects(value)
 elif isinstance(node,list):
  for value in node:close_objects(value)
for command in commands.values():
 # Batch items are intentionally typed from the command's own accepted fields.
 schema=command['inputSchema'];item_props={k:v for k,v in schema.get('properties',{}).items() if k!='batch'}
 schema['properties']['batch']['items']={'type':'object','additionalProperties':False,'properties':item_props}
 close_objects(command['inputSchema']);close_objects(command['outputSchema'])
 # Convert structured values only after the rich schemas have been generated;
 # the entrypoint remains the authoritative recursive validator after decoding.
 command['_richInputSchema']=json.loads(json.dumps(schema))
 for name in ('fields','params','body','batch'):
  if name in schema.get('properties',{}):schema['properties'][name]={'type':'string'}
contracts={cmd:{'inputSchema':c.pop('_richInputSchema'),'outputSchema':c['outputSchema'],'requiredScopes':sorted(required_scopes(cmd,c.get('safetyClasses',[]))) if not cmd.startswith('auth.') else []} for cmd,c in commands.items()}
(ROOT/'command_contracts.json').write_text(json.dumps(contracts,indent=2,ensure_ascii=False)+'\n')
doc['commands']={manifest_name(cmd):commands[cmd] for cmd in commands}
p.write_text(json.dumps(doc,indent=2,ensure_ascii=False)+'\n')
