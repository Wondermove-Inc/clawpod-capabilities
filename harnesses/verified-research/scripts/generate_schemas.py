#!/usr/bin/env python3
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
commands={
'source.fetch':({'url':'string','outputRoot':'string','snapshot':'string','timeout':'integer','maxBytes':'integer','overwrite':'boolean'},['url'],False,[('outputRoot','--output-root','output'),('snapshot','--snapshot','output')]),
'source.batch':({'inputRoot':'string','manifest':'string','outputRoot':'string','output':'string','timeout':'integer','maxBytes':'integer','overwrite':'boolean'},['inputRoot','manifest'],False,[('inputRoot','--input-root','input'),('manifest','--manifest','input'),('outputRoot','--output-root','output'),('output','--output','output')]),
'source.import':({'inputRoot':'string','capture':'string','sourceUrl':'string','mediaType':'string','outputRoot':'string','output':'string','maxBytes':'integer','overwrite':'boolean'},['inputRoot','capture'],False,[('inputRoot','--input-root','input'),('capture','--capture','input'),('outputRoot','--output-root','output'),('output','--output','output')]),
'bundle.build':({'inputRoot':'string','sources':'string','claims':'string','outputRoot':'string','output':'string','overwrite':'boolean'},['inputRoot','sources','claims','outputRoot','output'],True,[('inputRoot','--input-root','input'),('sources','--sources','input'),('claims','--claims','input'),('outputRoot','--output-root','output'),('output','--output','output')]),
'bundle.validate':({'inputRoot':'string','bundle':'string','asOf':'string'},['inputRoot','bundle'],False,[('inputRoot','--input-root','input'),('bundle','--bundle','input')]),
'bundle.inspect':({'inputRoot':'string','bundle':'string'},['inputRoot','bundle'],False,[('inputRoot','--input-root','input'),('bundle','--bundle','input')]),}
out={'type':'object','required':['ok','schemaVersion','command','requestId','effects','provenance'],'properties':{'ok':{'type':'boolean'},'schemaVersion':{'type':'integer'},'command':{'type':'string'},'requestId':{'type':'string'},'data':{},'effects':{'type':'array'},'provenance':{'type':'object'},'error':{'type':'object'}},'additionalProperties':False}
hcmd={}; contracts={'schemaVersion':1,'commands':{}}
for name,(props,required,mutation,paths) in commands.items():
 inp={'type':'object','required':required,'properties':{k:{'type':v} for k,v in props.items()},'additionalProperties':False}
 pathmap={x:(f,r) for x,f,r in paths}; flags={'url':'--url','timeout':'--timeout','maxBytes':'--max-bytes','sourceUrl':'--source-url','mediaType':'--media-type','overwrite':'--overwrite','asOf':'--as-of'}; amap=[]
 for k,v in props.items():
  flag,role=pathmap.get(k,(flags.get(k),None)); ent={'arg':k,'type':'option','flag':flag,'valueType':'path' if role else ('number' if v=='integer' else ('boolean' if v=='boolean' else 'string')),'optional':k not in required}
  if role: ent['pathRole']=role
  amap.append(ent)
 hcmd[name]={'description':name.replace('.',' ')+' deterministic evidence operation.','baseArgv':[name],'safetyClasses':['writeSafe' if mutation or any(r=='output' for _,_,r in paths) else 'readOnly'],'inputSchema':inp,'outputSchema':out,'argMap':amap,'retryPolicy':{'mode':'bounded-idempotent' if name in ('source.fetch','source.batch') else 'none','maxAttempts':2 if name in ('source.fetch','source.batch') else 1}}
 contracts['commands'][name]={'backend':'python-stdlib','mutation':mutation,'required':required,'inputSchema':inp,'outputSchema':out}
h={'schemaVersion':1,'kind':'openclaw.harness.v1','name':'verified-research','title':'Verified Research','description':'Deterministic bounded capture, hashing, bundling, inspection, and validation of research evidence.','version':'0.1.0','entrypoint':'./verified_research.py','packageRoot':'.','execution':{'cwd':'.','timeoutMs':45000,'requiresJson':True},'whenToUse':['Capture and validate deterministic evidence records for source-backed research'],'capabilities':['public-http-capture','evidence-bundles','integrity-validation'],'authModel':{'type':'none','storesSecrets':False,'requiresHumanAccount':False},'commands':hcmd}
(root/'harness.json').write_text(json.dumps(h,indent=2)+'\n'); (root/'command_contracts.json').write_text(json.dumps(contracts,indent=2)+'\n')
print('OK: schemas synchronized')
