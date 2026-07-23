import json,sys
sys.path.insert(0,'.')
from github import READ,MUTATE,REQUIRED,DESTRUCTIVE
commands=['auth.status']+list(READ)+list(MUTATE)
props={k:{'type':'string'} for k in ['host','expectedAccount','repo','state','number','runId','title','body','head','base','review','mergeMethod','tag','file','endpoint','confirm']}
props.update({k:{'type':'number'} for k in ['limit','timeoutMs','retries']});props['dryRun']={'type':'boolean'}
argmap=[]
for k,v in props.items():
 flag='--'+''.join(('-'+c.lower() if c.isupper() else c) for c in k)
 item={'arg':k,'type':'booleanFlag' if v['type']=='boolean' else 'option','flag':flag,'valueType':'boolean' if v['type']=='boolean' else ('integer' if v['type']=='number' else ('path' if k=='file' else 'string')),'optional':True}
 if k=='file':item['pathRole']='input'
 argmap.append(item)
out={'type':'object','required':['ok','schemaVersion','command','requestId','effects','provenance'],'properties':{'ok':{'type':'boolean'},'schemaVersion':{'type':'number'},'command':{'type':'string'},'requestId':{'type':'string'},'data':{},'effects':{'type':'array'},'provenance':{'type':'object'},'error':{'type':'object'}},'additionalProperties':False}
manifest={'schemaVersion':1,'kind':'openclaw.harness.v1','name':'github','title':'GitHub','description':'Guarded typed GitHub operations through the real gh CLI with stable JSON and bounded execution.','version':'0.1.0','entrypoint':'./github.py','packageRoot':'.','execution':{'cwd':'.','timeoutMs':30000,'requiresJson':True},'whenToUse':['Operate GitHub repositories, issues, pull requests, workflow runs, releases, or bounded API reads'],'capabilities':['gh-cli','guarded-mutations','stable-json'],'authModel':{'type':'pre-authenticated-gh-cli','storesSecrets':False,'requiresHumanAccount':True},'commands':{}}
contracts={'schemaVersion':1,'commands':{}}
for c in commands:
 req=[{'run_id':'runId'}.get(x,x) for x in REQUIRED.get(c,[])]
 inp={'type':'object','required':req,'properties':props,'additionalProperties':False}
 safety=['readOnly']
 if c in MUTATE:safety=['externalSideEffect','humanAccountAction']+(['destructive'] if c in DESTRUCTIVE else [])
 manifest['commands'][c]={'description':c.replace('.',' ')+' through GitHub CLI.','baseArgv':[c],'safetyClasses':safety,'inputSchema':inp,'outputSchema':out,'argMap':argmap}
 ci=json.loads(json.dumps(inp))
 for p in ci['properties'].values():
  if p.get('type')=='number':p['type']='integer'
 co=json.loads(json.dumps(out));co['properties']['schemaVersion']['type']='integer'
 contracts['commands'][c]={'backend':'gh','mutation':c in MUTATE,'required':req,'inputSchema':ci,'outputSchema':co}
open('harness.json','w').write(json.dumps(manifest,indent=2)+'\n');open('command_contracts.json','w').write(json.dumps(contracts,indent=2)+'\n')
