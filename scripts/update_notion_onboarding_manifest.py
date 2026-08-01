import copy,json
from pathlib import Path
root=Path(__file__).parents[1]/'harnesses/notion';hp=root/'harness.json';h=json.loads(hp.read_text());out=copy.deepcopy(h['commands']['auth.status']['outputSchema'])
roots={"type":"array","minItems":1,"maxItems":50,"items":{"type":"object","required":["type","id"],"properties":{"type":{"type":"string","enum":["page","database","data_source","block"]},"id":{"type":"string","pattern":"^[0-9a-fA-F-]{32,36}$"}},"additionalProperties":False}}
flags={'stateRoot':'--state-root','session':'--session','stateName':'--state-name','authMode':'--auth-mode','workspace':'--workspace','roots':'--roots','capabilities':'--capabilities','expectedRevision':'--expected-revision','approveHandoffs':'--approve-handoffs','sessionTimeout':'--session-timeout','now':'--now'}
def cmd(name,safety,props,required):
 return {'description':name+' secret-free Notion onboarding contract.','baseArgv':[name],'safetyClasses':safety,'inputSchema':{'type':'object','required':required,'properties':props,'additionalProperties':False},'outputSchema':out,'argMap':[{'arg':k,'type':'option','flag':flags[k],'valueType':'json' if k=='roots' else ('integer' if v.get('type')=='integer' else 'string'),'optional':k not in required} for k,v in props.items()]}
name={'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$'};common={'stateRoot':{'type':'string','minLength':1,'maxLength':4096},'session':name,'stateName':name};plan={'authMode':{'type':'string','enum':['internal','pat','oauth']},'workspace':{'type':'string','minLength':1,'maxLength':200},'roots':roots,'capabilities':{'type':'string','maxLength':500}}
start={**common,**plan,'sessionTimeout':{'type':'integer','minimum':30,'maximum':86400},'now':{'type':'integer','minimum':1}};resume={**common,'expectedRevision':{'type':'integer','minimum':0},'approveHandoffs':{'type':'string','maxLength':500},'now':{'type':'integer','minimum':1}}
commands={'onboard.plan':cmd('onboard.plan',['readOnly'],plan,[]),'onboard.desktop.plan':cmd('onboard.desktop.plan',['readOnly'],plan,[]),'onboard.desktop.task':cmd('onboard.desktop.task',['readOnly'],plan,[]),'onboard.start':cmd('onboard.start',['externalSideEffect'],start,['stateRoot','session','workspace']),'onboard.status':cmd('onboard.status',['readOnly'],common,['stateRoot','session']),'onboard.inspect':cmd('onboard.inspect',['readOnly'],common,['stateRoot','session']),'onboard.resume':cmd('onboard.resume',['externalSideEffect','secretUse','authReuse'],resume,['stateRoot','session','expectedRevision']),'onboard.cancel':cmd('onboard.cancel',['writeSafe'],{**common,'expectedRevision':{'type':'integer','minimum':0},'now':{'type':'integer','minimum':1}},['stateRoot','session','expectedRevision'])}
# Delete prior onboarding commands first so removed production arguments cannot linger.
for k in list(h['commands']):
 if k.startswith('onboard.'):del h['commands'][k]
h['commands'].update(commands)
for cap in ['resumable-minimal-intervention-onboarding','mockable-browser-desktop-adapter','protected-secret-capture-handoff','confined-private-onboarding-state']:
 if cap not in h['capabilities']:h['capabilities'].append(cap)
verify=h['commands']['auth.onboarding.verify'];verify['inputSchema']['properties']['workspace']={'type':'string','minLength':1,'maxLength':200}
if not any(x['arg']=='workspace' for x in verify['argMap']):verify['argMap'].append({'arg':'workspace','type':'option','flag':'--workspace','valueType':'string','optional':True})
hp.write_text(json.dumps(h,indent=2)+'\n');cp=root/'command_contracts.json';c=json.loads(cp.read_text())
for k in list(c['commands']):
 if k.startswith('onboard.'):del c['commands'][k]
for n,x in commands.items():c['commands'][n]={'method':None,'path':None,'safety':x['safetyClasses'][0],'paged':False,'verify':None,'requiredInputs':x['inputSchema']['required']}
cp.write_text(json.dumps(c,indent=2)+'\n')
