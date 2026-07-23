#!/usr/bin/env python3
"""Generate strict command contracts and runtime manifest from one inventory."""
from pathlib import Path
import json
ROOT=Path(__file__).parents[1]
COMMANDS={
'auth.sites.list':('GET','',False,[]),'auth.whoami':('GET','/rest/api/3/myself',False,[]),
'jira.issues.search':('GET','/rest/api/3/search/jql',False,[]),'jira.issues.get':('GET','/rest/api/3/issue/{issueIdOrKey}',False,['issueIdOrKey']),'jira.issues.create':('POST','/rest/api/3/issue',True,[]),'jira.issues.update':('PUT','/rest/api/3/issue/{issueIdOrKey}',True,['issueIdOrKey']),'jira.issues.delete':('DELETE','/rest/api/3/issue/{issueIdOrKey}',True,['issueIdOrKey']),'jira.issues.transitions.list':('GET','/rest/api/3/issue/{issueIdOrKey}/transitions',False,['issueIdOrKey']),'jira.issues.transition':('POST','/rest/api/3/issue/{issueIdOrKey}/transitions',True,['issueIdOrKey']),'jira.issues.comments.list':('GET','/rest/api/3/issue/{issueIdOrKey}/comment',False,['issueIdOrKey']),'jira.issues.comments.create':('POST','/rest/api/3/issue/{issueIdOrKey}/comment',True,['issueIdOrKey']),'jira.issues.comments.update':('PUT','/rest/api/3/issue/{issueIdOrKey}/comment/{commentId}',True,['issueIdOrKey','commentId']),'jira.issues.comments.delete':('DELETE','/rest/api/3/issue/{issueIdOrKey}/comment/{commentId}',True,['issueIdOrKey','commentId']),'jira.issues.attachments.add':('POST','/rest/api/3/issue/{issueIdOrKey}/attachments',True,['issueIdOrKey']),
'jira.projects.list':('GET','/rest/api/3/project/search',False,[]),'jira.projects.get':('GET','/rest/api/3/project/{projectIdOrKey}',False,['projectIdOrKey']),
'confluence.pages.list':('GET','/wiki/api/v2/pages',False,[]),'confluence.pages.get':('GET','/wiki/api/v2/pages/{pageId}',False,['pageId']),'confluence.pages.create':('POST','/wiki/api/v2/pages',True,[]),'confluence.pages.update':('PUT','/wiki/api/v2/pages/{pageId}',True,['pageId']),'confluence.pages.delete':('DELETE','/wiki/api/v2/pages/{pageId}',True,['pageId']),'confluence.spaces.list':('GET','/wiki/api/v2/spaces',False,[]),'confluence.spaces.get':('GET','/wiki/api/v2/spaces/{spaceId}',False,['spaceId']),'confluence.search':('GET','/wiki/rest/api/search',False,[]),'confluence.attachments.list':('GET','/wiki/api/v2/pages/{pageId}/attachments',False,['pageId']),'confluence.attachments.add':('POST','/wiki/rest/api/content/{pageId}/child/attachment',True,['pageId'])}
PROPS={'site':'string','sitesFile':'string','issueIdOrKey':'string','commentId':'string','projectIdOrKey':'string','pageId':'string','spaceId':'string','params':'string','body':'string','dryRun':'boolean','confirm':'string','idempotencyKey':'string','inputPath':'string','transferRoot':'string','maxUploadBytes':'integer','timeoutMs':'integer','retries':'integer','allPages':'boolean','maxPages':'integer','maxItems':'integer','batch':'string'}
FLAGS={k:'--'+''.join(('-'+c.lower() if c.isupper() else c) for c in k) for k in PROPS}
def schema(required): return {'type':'object','required':required,'properties':{k:{'type':v} for k,v in PROPS.items()},'additionalProperties':False}
def argmap(required):
 out=[]
 for k,t in PROPS.items():
  role={'inputPath':'input','transferRoot':'inout','sitesFile':'input'}.get(k); x={'arg':k,'type':'booleanFlag' if t=='boolean' else 'option','flag':FLAGS[k],'valueType':'path' if role else t,'optional':k not in required}
  if role:x['pathRole']=role
  out.append(x)
 return out
contracts={'schemaVersion':1,'commands':{}}
manifest={'schemaVersion':1,'kind':'openclaw.harness.v1','name':'atlassian','title':'Atlassian Cloud','description':'Typed Jira Cloud v3 and Confluence Cloud v2/v1 operations with guarded mutations and stable evidence.','version':'0.1.1','entrypoint':'./atlassian.py','packageRoot':'.','whenToUse':['Operate Jira Cloud or Confluence Cloud through approved credentials'],'capabilities':['jira-cloud-v3','confluence-cloud-v2','confluence-cloud-v1-fallback','multi-site','safe-transfer'],'authModel':{'type':'basic-or-oauth-bearer','storesSecrets':False,'requiresHumanAccount':True},'commands':{}}
for name,(method,path,mutation,ids) in COMMANDS.items():
 required=([] if name=='auth.sites.list' else ['site'])+ids; inp=schema(required); output={'type':'object','required':['ok','schemaVersion','command','requestId','effects','provenance'],'properties':{'ok':{'type':'boolean'},'schemaVersion':{'type':'integer'},'command':{'type':'string'},'requestId':{'type':'string'},'data':{},'effects':{'type':'array'},'page':{'type':'object'},'provenance':{'type':'object'},'error':{'type':'object'}},'additionalProperties':False}
 contracts['commands'][name]={'method':method,'path':path,'mutation':mutation,'required':required,'inputSchema':inp,'outputSchema':output}
 manifest['commands'][name]={'description':f'{name} through Atlassian Cloud REST.','baseArgv':[name],'safetyClasses':(['externalSideEffect','humanAccountAction'] if mutation else ['readOnly']),'inputSchema':inp,'outputSchema':output,'argMap':argmap(required)}
(ROOT/'command_contracts.json').write_text(json.dumps(contracts,indent=2)+'\n'); (ROOT/'harness.json').write_text(json.dumps(manifest,indent=2)+'\n')
