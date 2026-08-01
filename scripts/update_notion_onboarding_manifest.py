import json,copy
from pathlib import Path
root=Path(__file__).parents[1]/'harnesses/notion'
hp=root/'harness.json'; h=json.loads(hp.read_text()); out=copy.deepcopy(h['commands']['auth.status']['outputSchema'])
root_schema={"type":"array","minItems":1,"maxItems":50,"items":{"type":"object","required":["type","id"],"properties":{"type":{"type":"string","enum":["page","database","data_source","block"]},"id":{"type":"string","pattern":"^[0-9a-fA-F-]{32,36}$"}},"additionalProperties":False}}
def cmd(name,safety,props,required):
 flags={'statePath':'--state-path','authMode':'--auth-mode','workspace':'--workspace','roots':'--roots','capabilities':'--capabilities','adapterFixture':'--adapter-fixture','expectedRevision':'--expected-revision','approveHandoffs':'--approve-handoffs','sessionTimeout':'--session-timeout','now':'--now'}
 maps=[{'arg':k,'type':'option','flag':flags[k],'valueType':'json' if k=='roots' else ('integer' if v.get('type')=='integer' else 'string'),'optional':k not in required} for k,v in props.items()]
 return {'description':name+' resumable secret-free Notion onboarding orchestration.','baseArgv':[name],'safetyClasses':safety,'inputSchema':{'type':'object','required':required,'properties':props,'additionalProperties':False},'outputSchema':out,'argMap':maps}
common={'statePath':{'type':'string','minLength':1,'maxLength':4096}}
plan={'authMode':{'type':'string','enum':['internal','pat','oauth']},'workspace':{'type':'string','minLength':1,'maxLength':200},'roots':root_schema,'capabilities':{'type':'string','maxLength':500}}
start={**common,**plan,'adapterFixture':{'type':'string','maxLength':4096},'sessionTimeout':{'type':'integer','minimum':30,'maximum':86400},'now':{'type':'integer','minimum':1}}
resume={**common,'expectedRevision':{'type':'integer','minimum':0},'approveHandoffs':{'type':'string','maxLength':500},'adapterFixture':{'type':'string','maxLength':4096},'now':{'type':'integer','minimum':1}}
h['commands']['onboard.plan']=cmd('onboard.plan',['readOnly'],plan,[])
h['commands']['onboard.start']=cmd('onboard.start',['externalSideEffect'],start,['workspace'])
h['commands']['onboard.status']=cmd('onboard.status',['readOnly'],common,[])
h['commands']['onboard.inspect']=cmd('onboard.inspect',['readOnly'],common,[])
h['commands']['onboard.resume']=cmd('onboard.resume',['externalSideEffect','secretUse','authReuse'],resume,['expectedRevision'])
h['commands']['onboard.cancel']=cmd('onboard.cancel',['writeSafe'],{**common,'expectedRevision':{'type':'integer','minimum':0},'now':{'type':'integer','minimum':1}},['expectedRevision'])
for cap in ['resumable-minimal-intervention-onboarding','mockable-browser-desktop-adapter','protected-secret-capture-handoff']:
 if cap not in h['capabilities']:h['capabilities'].append(cap)
h['description']='Typed guarded Notion REST API operations with resumable minimal-intervention onboarding, protected secret handoff, allowlisted writes, previews, verification, retries, and redaction.'
hp.write_text(json.dumps(h,indent=2)+'\n')
verify=h['commands']['auth.onboarding.verify'];verify['inputSchema']['properties']['workspace']={'type':'string','minLength':1,'maxLength':200};verify['argMap'].append({'arg':'workspace','type':'option','flag':'--workspace','valueType':'string','optional':True}) if not any(x['arg']=='workspace' for x in verify['argMap']) else None
hp.write_text(json.dumps(h,indent=2)+'\n')
cp=root/'command_contracts.json'; c=json.loads(cp.read_text())
for name in ['onboard.plan','onboard.start','onboard.status','onboard.inspect','onboard.resume','onboard.cancel']:
 x=h['commands'][name]; c['commands'][name]={'method':None,'path':None,'safety':x['safetyClasses'][0],'paged':False,'verify':None,'requiredInputs':x['inputSchema']['required']}
cp.write_text(json.dumps(c,indent=2)+'\n')
