#!/usr/bin/env python3
import json
from pathlib import Path
R=Path(__file__).resolve().parents[2];N='cloudflare-quick-tunnel-preview';V='0.1.0';D='Create TTL-bounded accountless Cloudflare Quick Tunnel previews for loopback-only local services.'
base={'$schema':'../../schemas/package-metadata.schema.json','schemaVersion':1,'version':V,'description':D,'compatibility':{'openclaw':'>=2026.4.0','platforms':['linux']},'safety':{'risk':'externally-visible','approvalRequired':True}}
(R/'harnesses'/N/'capability.json').write_text(json.dumps(base,indent=2)+'\n'); skill={**base,'linkedHarness':{'id':N,'version':V}};(R/'skills'/N/'capability.json').write_text(json.dumps(skill,indent=2)+'\n')
P={'stateRoot':{'type':'string'},'cloudflared':{'type':'string'},'host':{'type':'string'},'port':{'type':'integer'},'ttl':{'type':'integer'},'discoveryTimeout':{'type':'number'},'skipConnect':{'type':'boolean'}}
OUT={'type':'object','required':['ok','schemaVersion','command'],'properties':{'ok':{'type':'boolean'},'schemaVersion':{'type':'number'},'command':{'type':'string'},'data':{},'effects':{'type':'array'},'error':{'type':'object'}},'additionalProperties':False}
def cmd(n,safety,args):
 m=[]
 for x in args:
  vt={'port':'integer','ttl':'integer','discoveryTimeout':'number','skipConnect':'boolean'}.get(x,'path' if x in ('stateRoot','cloudflared') else 'string');a={'arg':x,'type':'booleanFlag' if vt=='boolean' else 'option','flag':'--'+repl(x),'valueType':vt,'optional':x not in ('stateRoot','cloudflared','port')}
  if vt=='path':a['pathRole']='inout' if x=='stateRoot' else 'input'
  m.append(a)
 return {'description':n+' Quick Tunnel operation.','baseArgv':[n],'safetyClasses':safety,'inputSchema':{'type':'object','properties':{x:P[x] for x in args},'additionalProperties':False},'outputSchema':OUT,'argMap':m}
def repl(x):return ''.join('-'+c.lower() if c.isupper() else c for c in x)
C={'status':cmd('status',['readOnly'],['stateRoot']),'preflight':cmd('preflight',['readOnly'],['stateRoot','cloudflared','host','port','skipConnect']),'start':cmd('start',['writeSafe','externalSideEffect'],['stateRoot','cloudflared','host','port','ttl','discoveryTimeout']),'inspect':cmd('inspect',['readOnly'],['stateRoot']),'stop':cmd('stop',['writeSafe','destructive'],['stateRoot'])}
M={'schemaVersion':1,'kind':'openclaw.harness.v1','name':N,'title':'Cloudflare Quick Tunnel Preview','description':D,'version':V,'entrypoint':'./cloudflare_quick_tunnel_preview.py','packageRoot':'.','execution':{'cwd':'.','timeoutMs':35000,'requiresJson':True},'whenToUse':['Temporarily expose a loopback-only local preview through an accountless public URL'],'capabilities':['quick-tunnel-preview','ttl-process-control'],'authModel':{'type':'none','storesSecrets':False,'requiresHumanAccount':False},'commands':C}
(R/'harnesses'/N/'harness.json').write_text(json.dumps(M,indent=2)+'\n')
