#!/usr/bin/env python3
"""Deterministically specialize every command schema from the checked operation catalog."""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from google_workspace_core.catalog import operation
from google_workspace_core.scopes import required_scopes
p=ROOT/'harness.json'; doc=json.loads(p.read_text())
SAMPLES={k:k for k in ('messageId','threadId','attachmentId','labelId','draftId','calendarId','eventId','ruleId','settingId','fileId','permissionId','commentId','replyId','revisionId','driveId','sendAsEmail','smimeInfoId','forwardingEmail','delegateEmail','filterId')};SAMPLES.update(userId='me',kind='imap',mimeType='text/plain',requestId='request')
READ={'list','get','search','instances','download','export','startPageToken'}
NO_BODY=READ|{'delete','trash','untrash','emptyTrash','hide','unhide','stop','clear','setDefault','verify','generateIds','watch'}
for cmd,c in doc['commands'].items():
 s=c['inputSchema'];props=s['properties'];props['expectedSha256']={'type':'string','pattern':'^[a-f0-9]{64}$'};props['batch']={'type':'array','minItems':1,'maxItems':100,'items':{'type':'object'}};s['required']=list(dict.fromkeys(s.get('required',[])))
 if cmd.startswith('auth.'):
  props['params']={'type':'object','additionalProperties':False,'properties':{}}
  c['requiredScopes']=[]
  continue
 op=operation(cmd,SAMPLES); req=sorted(op['pathParams'])
 ps={'type':'object','additionalProperties':False,'properties':{}}
 for key in req:ps['properties'][key]={'type':'string','minLength':1,'maxLength':4096}
 # provider query names remain accepted but typed; unknown query keys fail closed
 for key in ('q','query','orderBy','timeMin','timeMax','syncToken','startHistoryId','pageToken','corpora','spaces','driveId','includeItemsFromAllDrives','supportsAllDrives','sendUpdates','maxResults','mimeType','requestId','uploadType'):
  if key not in ps['properties']:ps['properties'][key]={'type':['string','boolean','integer']}
 if req:ps['required']=req
 props['params']=ps
 action=cmd.rsplit('.',1)[1]
 body_required=op['method'] in ('POST','PUT','PATCH') and action not in NO_BODY and cmd not in ('gmail.messages.send','gmail.drafts.send')
 props['body']={'type':'object','additionalProperties':True,'minProperties':1}
 if body_required and 'body' not in s['required']:s['required'].append('body')
 # transfers
 if cmd=='drive.files.upload':s['required']=list(dict.fromkeys(s['required']+['inputPath','transferRoot']))
 if cmd in ('drive.files.download','drive.files.export'):s['required']=list(dict.fromkeys(s['required']+['outputPath','transferRoot']))
 c['requiredScopes']=sorted(required_scopes(cmd,c.get('safetyClasses',[])))
p.write_text(json.dumps(doc,indent=2,ensure_ascii=False)+'\n')
