#!/usr/bin/env python3
"""Deterministically specialize every command schema from checked provider contracts."""
import copy,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from google_workspace_core.catalog import operation
from google_workspace_core.scopes import required_scopes
from google_workspace_core.contracts import body_schema,QUERY_TYPES,S,O,A
p=ROOT/'harness.json';doc=json.loads(p.read_text())
# Seed locally evaluated onboarding policy from an existing lifecycle-compatible
# auth command. Rich schemas below remain the semantic source of truth.
if 'auth.onboarding.decide' not in doc['commands']:
 template=copy.deepcopy(doc['commands']['auth.scopes.list'])
 template['description']='Deterministically choose the Google OAuth audience and verification gates without credentials or network access.'
 template['baseArgv']=['auth.onboarding.decide']
 doc['commands']['auth.onboarding.decide']=template
ADDITIONS={
 'auth.bindings.list':('List pod-local credential aliases and sanitized metadata.',('secretUse','authReuse','readOnly'),'auth.accounts.list'),
 'auth.bindings.status':('Validate binding registry, permissions, bundle shape, and identity.',('secretUse','authReuse','readOnly'),'auth.accounts.list'),
 'auth.bindings.resolve':('Resolve one alias to sanitized metadata without exposing a path.',('secretUse','authReuse','readOnly'),'auth.accounts.list'),
 'auth.bindings.import':('Copy or explicitly reference a validated legacy credential bundle.',('secretUse','authReuse','writeSafe','humanAccountAction'),'auth.accounts.list'),
 'auth.bindings.rename':('Atomically rename a pod-local alias.',('secretUse','authReuse','writeSafe'),'auth.accounts.list'),
 'auth.bindings.remove':('Remove a binding, with separate explicit credential deletion.',('secretUse','authReuse','writeSafe'),'auth.accounts.list'),
 'auth.bindings.migrate':('Preview or apply bounded deterministic legacy discovery.',('secretUse','authReuse','writeSafe','humanAccountAction'),'auth.accounts.list'),
 'auth.bindings.permissions.check':('Report protected-root permission defects.',('secretUse','authReuse','readOnly'),'auth.accounts.list'),
 'auth.bindings.permissions.repair':('Repair owned pod-local protected-root permissions.',('secretUse','authReuse','writeSafe'),'auth.accounts.list'),
 'gmail.read':('Perform bounded Gmail message or thread reads with normalized summaries.',('secretUse','authReuse','readOnly'),'gmail.messages.list'),
 'calendar.read':('Perform bounded upcoming or ranged Calendar reads with normalized summaries.',('secretUse','authReuse','readOnly'),'calendar.events.list'),
 'drive.read':('Perform bounded Drive search, recent, or metadata reads.',('secretUse','authReuse','readOnly'),'drive.files.list'),
}
for name,(description,safety,source) in ADDITIONS.items():
 if name not in doc['commands']:
  template=copy.deepcopy(doc['commands'][source]);template['description']=description;template['baseArgv']=[name];template['safetyClasses']=list(safety);doc['commands'][name]=template
SAMPLES={k:k for k in ('messageId','threadId','attachmentId','labelId','draftId','calendarId','eventId','ruleId','settingId','fileId','permissionId','commentId','replyId','revisionId','driveId','sendAsEmail','smimeInfoId','forwardingEmail','delegateEmail','filterId')};SAMPLES.update(userId='me',kind='imap',mimeType='text/plain',requestId='request',pageToken='page')
PAGED={'list','search','instances'}
def allowed_query(cmd,action):
 out=set()
 if action in PAGED:
  out|={'q','query','orderBy'}
  out.add('maxResults' if cmd.startswith(('gmail.','calendar.')) else 'pageSize')
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
def exact_surface(command,schema,names):
 keep=set(names);schema['properties']={k:v for k,v in schema['properties'].items() if k in keep}
 schema['required']=[k for k in schema.get('required',[]) if k in keep]
 command['argMap']=[arg for arg in command.get('argMap',[]) if arg.get('arg') in keep]

commands={logical_name(key,c):c for key,c in doc['commands'].items()}
# Rehydrate rich schemas when regenerating from an already projected manifest.
# This keeps generation deterministic and prevents lifecycle projection from
# becoming the next run's semantic source of truth.
contracts_path=ROOT/'command_contracts.json'
if contracts_path.exists():
 existing_contracts=json.loads(contracts_path.read_text())
 for cmd,c in commands.items():
  if cmd in existing_contracts:
   c['inputSchema']=json.loads(json.dumps(existing_contracts[cmd]['inputSchema']))
   c['outputSchema']=json.loads(json.dumps(existing_contracts[cmd]['outputSchema']))
 # Added commands are always rebuilt from a baseline rich contract. This
 # prevents an already-projected lifecycle manifest from becoming semantic
 # input on the next deterministic generation pass.
 for name,(_description,_safety,source) in ADDITIONS.items():
  if source in existing_contracts:
   commands[name]['inputSchema']=json.loads(json.dumps(existing_contracts[source]['inputSchema']))
   commands[name]['outputSchema']=json.loads(json.dumps(existing_contracts[source]['outputSchema']))
for cmd,c in commands.items():
 mapped=[]
 for safety in c.get('safetyClasses',[]):
  mapped.extend(SAFETY_MAP.get(safety,(safety,)))
 c['safetyClasses']=list(dict.fromkeys(mapped))
 for arg in c.get('argMap',[]):
  if arg.get('valueType')=='json':arg['valueType']='string'
  if arg.get('valueType')=='boolean':arg['type']='booleanFlag'
  # auth.login interprets outputPath relative to transferRoot itself so the
  # OAuth bundle never falls back to the package cwd chosen by the argv bridge.
  if cmd=='auth.login' and arg.get('arg')=='outputPath':
   arg['valueType']='string';arg.pop('pathRole',None)
 # Rich JSON values are serialized as strings by the lifecycle argv bridge,
 # then decoded and checked against the command-specific schema by the CLI.
 for name in ('fields','params','body','batch'):
  if name in c['inputSchema'].get('properties',{}):
   c['inputSchema']['properties'][name]={'type':'string'}
 c.pop('requiredScopes',None)
 s=c['inputSchema'];props=s['properties'];props['fields']={'type':'array','items':{'type':'string','minLength':1,'maxLength':512},'maxItems':100};props['expectedSha256']={'type':'string','pattern':'^[a-f0-9]{64}$'};props['batch']={'type':'array','minItems':1,'maxItems':100,'items':{'type':'object'}};s['required']=list(dict.fromkeys(s.get('required',[])))
 # 0.3.0 can select the sole account in an explicit bundle or the sole healthy
 # pod-local binding, so account is no longer a universal required field.
 s['required']=[name for name in s['required'] if name!='account']
 if cmd not in ('auth.login','auth.scopes.list'):
  props['credentialPath']=S(maxLength=4096)
  if not any(arg.get('arg')=='credentialPath' for arg in c.get('argMap',[])):
   c.setdefault('argMap',[]).insert(1,{'arg':'credentialPath','type':'option','flag':'--credential-path','valueType':'path','pathRole':'input','optional':True})
 if cmd.startswith('auth.'):
  props['params']={'type':'object','additionalProperties':False,'properties':{}}
  if cmd=='auth.onboarding.decide':
   props['body']=O({
    'projectInOrganization':{'type':'boolean'},
    'allIntendedUsersOrganizationMembers':{'type':'boolean'},
    'externalPublishingStatus':S(enum=['testing','inProduction']),
    'usesNonBasicScopes':{'type':'boolean'},
    'usesRestrictedGmailOrDriveScopes':{'type':'boolean'},
   },required=['projectInOrganization','allIntendedUsersOrganizationMembers','externalPublishingStatus','usesNonBasicScopes','usesRestrictedGmailOrDriveScopes'])
   s['required']=list(dict.fromkeys(s['required']+['body']))
  elif cmd=='auth.scopes.check': props['body']=O({'profiles':A(S(),maxItems=32)})
  elif cmd=='auth.login':
   props['body']=O({
    'clientPath':S(),
    'profiles':A(S(),maxItems=32),
   'managedBrowserDevtoolsUrl':S(),
   'smokeTests':A(S(enum=['gmail','calendar','drive']),maxItems=3),
    'bind':{'type':'boolean'},
   },required=['clientPath','profiles'])
   # Human consent is bounded at ten minutes. The process timeout below must
   # outlive that receiver window and the final token/identity exchanges.
   props['timeoutMs']['minimum']=5000;props['timeoutMs']['maximum']=600000;props['timeoutMs']['default']=600000
   s['required']=[name for name in s['required'] if name!='outputPath']
   s['required']=list(dict.fromkeys(s['required']+['account','body','transferRoot']))
  elif cmd=='auth.bindings.import':
   props['body']=O({'mode':S(enum=['copy','reference']),'sourceAlias':S()});s['required']=list(dict.fromkeys(s['required']+['account','inputPath']))
   exact_surface(c,s,('account','inputPath','body','overwrite','preview','dryRun','confirm','requestId'))
  elif cmd=='auth.bindings.rename':props['body']=O({'newAlias':S()},required=['newAlias']);s['required']=list(dict.fromkeys(s['required']+['account','body']))
  elif cmd=='auth.bindings.remove':props['body']=O({'deleteCredential':{'type':'boolean'}});s['required']=list(dict.fromkeys(s['required']+['account']))
  elif cmd=='auth.bindings.migrate':
   mapping=O({'candidateId':S(),'alias':S(),'sourceAlias':S(),'mode':S(enum=['copy','reference']),'overwrite':{'type':'boolean'}},required=['candidateId','alias'])
   props['body']=O({'mappings':A(mapping,maxItems=1)});s['required']=list(dict.fromkeys(s['required']+['inputPath']))
   exact_surface(c,s,('inputPath','body','preview','dryRun','confirm','requestId'))
  else: props['body']=O({})
  if cmd in ('auth.bindings.list','auth.bindings.status','auth.bindings.permissions.check'):
   exact_surface(c,s,('requestId',))
  elif cmd=='auth.bindings.resolve':
   exact_surface(c,s,('account','requestId'))
  elif cmd=='auth.bindings.rename':
   exact_surface(c,s,('account','body','preview','dryRun','confirm','requestId'))
  elif cmd=='auth.bindings.remove':
   exact_surface(c,s,('account','body','preview','dryRun','confirm','requestId'))
  elif cmd=='auth.bindings.permissions.repair':
   exact_surface(c,s,('preview','dryRun','confirm','requestId'))
  continue
 if cmd=='gmail.read':
  props['params']=O({'mode':S(enum=['messages','threads']),'userId':S(),'q':S(maxLength=20000),'labelIds':A(S(),maxItems=100),'includeSpamTrash':{'type':'boolean'},'includeBody':{'type':'boolean'},'maxResults':QUERY_TYPES['maxResults']});props['body']=O({});exact_surface(c,s,('account','credentialPath','fields','pageSize','pageToken','allPages','maxItems','maxPages','timeoutMs','params','requestId'));continue
 if cmd=='calendar.read':
  props['params']=O({'calendarId':S(),'timeMin':S(format='date-time'),'timeMax':S(format='date-time'),'timeZone':S(),'singleEvents':{'type':'boolean'},'orderBy':S(enum=['startTime','updated']),'maxResults':QUERY_TYPES['maxResults']});props['body']=O({});exact_surface(c,s,('account','credentialPath','fields','pageSize','pageToken','allPages','maxItems','maxPages','timeoutMs','params','requestId'));continue
 if cmd=='drive.read':
  props['params']=O({'mode':S(enum=['search','recent','get']),'fileId':S(),'q':S(maxLength=20000),'spaces':QUERY_TYPES['spaces'],'corpora':QUERY_TYPES['corpora'],'driveId':S(),'orderBy':S(),'pageSize':QUERY_TYPES['pageSize']});props['body']=O({});exact_surface(c,s,('account','credentialPath','fields','pageSize','pageToken','allPages','maxItems','maxPages','timeoutMs','params','requestId'));continue
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

# OpenClaw's run-intent bridge deliberately accepts only this small recursive
# schema vocabulary. Rich validation remains authoritative in
# command_contracts.json and the entrypoint; the lifecycle manifest is only the
# typed/closed argv boundary.
def lifecycle_schema(node):
 out={}
 if 'type' in node:
  # The runtime enforces a type only when it is a single JSON type string.
  # Omitting union types is clearer than retaining an accepted-but-ignored list.
  if isinstance(node['type'],str):
   # Gateway 2026.4.11 reports JavaScript integers as schema type "number".
   # The argMap integer valueType remains the operational integral-value gate.
   out['type']='number' if node['type']=='integer' else node['type']
 if isinstance(node.get('required'),list):out['required']=list(node['required'])
 if isinstance(node.get('properties'),dict):
  out['properties']={name:lifecycle_schema(value) for name,value in node['properties'].items()}
 if isinstance(node.get('additionalProperties'),bool):
  # A closed object with no declared properties means "empty object" to the
  # bridge. Rich provider result envelopes intentionally carry command-specific
  # payloads there, so leave those opaque while keeping every declared object
  # boundary closed.
  if node['additionalProperties'] or out.get('properties'):out['additionalProperties']=node['additionalProperties']
 return out

for command in commands.values():
 # Batch items are intentionally typed from the command's own accepted fields.
 schema=command['inputSchema'];item_props={k:v for k,v in schema.get('properties',{}).items() if k!='batch'}
 if 'batch' in schema.get('properties',{}):
  schema['properties']['batch']['items']={'type':'object','additionalProperties':False,'properties':item_props}
 close_objects(command['inputSchema']);close_objects(command['outputSchema'])
 # Snapshot full recursive semantics before projecting the lifecycle schemas.
 command['_richInputSchema']=json.loads(json.dumps(schema))
 command['_richOutputSchema']=json.loads(json.dumps(command['outputSchema']))
 for name in ('fields','params','body','batch'):
  if name in schema.get('properties',{}):schema['properties'][name]={'type':'string'}
 command['inputSchema']=lifecycle_schema(schema)
 command['outputSchema']=lifecycle_schema(command['outputSchema'])
contracts={cmd:{'inputSchema':c.pop('_richInputSchema'),'outputSchema':c.pop('_richOutputSchema'),'requiredScopes':sorted(required_scopes(cmd,c.get('safetyClasses',[]))) if not cmd.startswith('auth.') else []} for cmd,c in commands.items()}
(ROOT/'command_contracts.json').write_text(json.dumps(contracts,indent=2,ensure_ascii=False)+'\n')
doc['commands']={manifest_name(cmd):commands[cmd] for cmd in commands}
p.write_text(json.dumps(doc,indent=2,ensure_ascii=False)+'\n')
