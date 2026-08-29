import hashlib, json, os, subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).parents[1]; CLI=ROOT/'claude_design.py'
def run(*args,env=None):
 p=subprocess.run([str(CLI),*args],text=True,capture_output=True,env=env); return p,json.loads(p.stdout)

def test_version():
 p,o=run('system.version'); assert p.returncode==0 and o['data']['version']=='0.4.0'
def test_stable_envelope():
 _,o=run('system.version'); assert {'ok','command','request_id','data','warnings','evidence','retry_safe'}<=o.keys()
def test_onboarding_plan_is_browser_first_and_minimal_human_input():
 _,o=run('onboarding.plan'); d=o['data']; assert d['state']=='browser_ready_when_authenticated' and d['default_execution'].startswith('logged-in browser')
 assert d['human_only']==['sign-in when browser authentication is absent','MFA','provider consent']
 assert d['mcp']=={'required':False,'use_only_after_real_tool_smoke':True,'readiness_independent':True}
 assert 'MCP endpoint registration' in d['never_delegate_to_user']
def test_preflight_has_no_secret_or_cli_dependency():
 env={**os.environ,'CLAUDE_CODE_OAUTH_TOKEN':'TOP_SECRET_SENTINEL'};p,o=run('onboarding.preflight',env=env)
 assert o['data']['default_execution']=='browser' and o['data']['mcp_required'] is False and 'TOP_SECRET_SENTINEL' not in p.stdout
def test_onboarding_status_browser_readiness_independent_of_mcp():
 _,o=run('onboarding.status'); d=o['data']; assert d['capability_readiness']=='READY_PENDING_BROWSER_AUTH_CHECK' and d['mcp_required'] is False
def test_auth_contract_requires_only_browser_login_steps():
 _,o=run('auth.contract'); d=o['data']; assert d['default_auth']=='existing claude.ai browser session' and d['mcp_oauth_required'] is False and d['mcp_registration_required'] is False
@pytest.mark.parametrize('tag',['input','textarea','INPUT'])
def test_browser_input_plan_uses_fill_for_standard_fields_at_any_length(tag):
 prompt='x'*1200; p,o=run('browser.input.plan','--prompt',prompt,'--ref','field-1','--tag-name',tag)
 assert p.returncode==0 and o['data']['strategy']=='fill'
 assert o['data']['action']=={'kind':'fill','fields':[{'ref':'field-1','type':'text','value':prompt}]}
 assert o['data']['expected_length']==len(prompt) and len(o['data']['expected_sha256'])==64
@pytest.mark.parametrize('length,strategy',[ (600,'type'),(601,'evaluate') ])
def test_browser_input_plan_contenteditable_threshold(length,strategy):
 prompt='ø'*length; p,o=run('browser.input.plan','--prompt',prompt,'--ref','prompt-box','--contenteditable')
 assert p.returncode==0 and o['data']['editable_kind']=='contenteditable' and o['data']['strategy']==strategy
 assert o['data']['action']['kind']==strategy and o['data']['action']['ref']=='prompt-box'
def test_long_contenteditable_evaluate_treats_adversarial_prompt_as_text():
 prompt=('quotes " \\ newline\n markup </script><b>no</b> unicode 雪 '*20)
 _,o=run('browser.input.plan','--prompt',prompt,'--ref','r7','--role','textbox')
 fn=o['data']['action']['fn']; literal=json.dumps(prompt,ensure_ascii=True)
 assert o['data']['strategy']=='evaluate' and f'const text = {literal};' in fn
 assert 'replaceChildren(document.createTextNode(text))' in fn and "InputEvent('input'" in fn and "Event('change'" in fn
 assert prompt not in fn
def test_long_contenteditable_fails_closed_without_evaluate():
 p,o=run('browser.input.plan','--prompt','x'*601,'--ref','r','--contenteditable','--evaluate-disabled')
 assert p.returncode==2 and o['error']['code']=='UNSUPPORTED' and o['retry_safe'] is False
 assert o['data']['strategy']=='blocked' and 'type is not a safe long-input fallback' in o['data']['reason']
def test_browser_input_plan_rejects_unsupported_and_missing_target_details():
 _,missing=run('browser.input.plan','--prompt','x'); assert missing['error']['code']=='INVALID_INPUT'
 p,o=run('browser.input.plan','--prompt','x','--ref','r','--tag-name','div')
 assert p.returncode==2 and o['error']['code']=='UNSUPPORTED' and o['data']['strategy']=='blocked'
def test_browser_input_verify_requires_exact_readback():
 prompt='line one\n雪 "quoted"'
 p,ok=run('browser.input.verify','--prompt',prompt,'--observed-text',prompt)
 assert p.returncode==0 and ok['data']['exact_match'] and ok['data']['expected_sha256']==hashlib.sha256(prompt.encode()).hexdigest()
 assert ok['evidence'][0]['kind']=='browser-input-verification'
 p,bad=run('browser.input.verify','--prompt',prompt,'--observed-text',prompt+' ')
 assert p.returncode==2 and bad['error']['code']=='VERIFICATION_FAILED' and bad['retry_safe'] is False and bad['data']['exact_match'] is False
def test_browser_input_diagnosis_recovers_stale_ref_once_without_restart():
 _,o=run('browser.input.diagnose','--error-message','Unknown ref from stale snapshot','--gateway-status','unhealthy')
 assert o['data']['classification']=='STALE_REF' and 'retry once' in o['data']['next_action'] and o['data']['gateway_restart'] is False
def test_browser_input_timeout_does_not_infer_gateway_restart():
 _,o=run('browser.input.diagnose','--error-message','browser action timed out','--gateway-status','healthy')
 assert o['data']['classification']=='BROWSER_ACTION_TIMEOUT' and o['data']['gateway_status'] is True and o['data']['gateway_restart'] is False
 assert 'not evidence that the Gateway must be restarted' in o['warnings'][0]
 _,bad=run('browser.input.diagnose','--error-message','failed','--gateway-status','broken'); assert bad['error']['code']=='INVALID_INPUT'
def test_setup_token_deprecated_for_default_path():
 _,o=run('auth.setup-token.plan'); assert o['data']['deprecated_for_default_path'] and o['data']['execute'] is False
def test_login_is_browser_handoff():
 p,o=run('code.login.handoff'); assert p.returncode==2 and o['error']['code']=='HUMAN_VERIFICATION' and 'sign-in, MFA, or consent' in o['error']['message']
def test_mcp_inspect_is_optional_and_connected_not_authorized():
 _,o=run('mcp.inspect'); d=o['data']; assert d['optional'] and d['required_for_readiness'] is False and d['authorized'] is False and d['tool_smoke_succeeded'] is False
 assert 'redirect_uri' in d['known_defect'] and 'Connected does not prove' in d['known_defect']
def test_mcp_validate_failure_does_not_block_readiness():
 p,o=run('mcp.validate'); assert p.returncode==2 and o['error']['code']=='BACKEND_UNAVAILABLE' and o['data']['required_for_readiness'] is False and 'real tool result' in o['data']['success_criterion']
def test_mcp_install_is_not_default_and_requires_observed_transport():
 _,o=run('mcp.install-plan'); assert o['error']['code']=='INVALID_INPUT'
 _,o=run('mcp.install-plan','--mcp-url','https://observed.example/mcp'); assert o['data']['execute'] is False and o['data']['optional'] and o['data']['readiness_impact']=='none'
def test_mcp_remove_plan_is_optional():
 _,o=run('mcp.remove-plan'); assert o['error']['code']=='INVALID_INPUT'
 _,o=run('mcp.remove-plan','--mcp-name','observed-design'); assert o['data']['argv']==['claude','mcp','remove','observed-design'] and o['data']['optional']

@pytest.mark.parametrize('command',[ 'projects.list','projects.search','projects.present','design-systems.list','templates.list','admin.status','admin.permissions','admin.usage'])
def test_reads_require_human_reconciliation(command):
 p,o=run(command); assert p.returncode==2 and o['error']['code']=='HUMAN_VERIFICATION' and o['data']['reconciliation_source']
@pytest.mark.parametrize('command,flag',[('projects.get','--project-id'),('design-systems.get','--design-system-id'),('templates.get','--template-id')])
def test_get_requires_id(command,flag):
 _,o=run(command); assert o['error']['code']=='INVALID_INPUT'
 _,o=run(command,flag,'x'); assert o['error']['code']=='HUMAN_VERIFICATION'
@pytest.mark.parametrize('command,args',[('projects.create',['--prompt','x']),('design-systems.create',['--name','x']),('templates.create',['--name','x']),('projects.update',['--project-id','p']),('projects.iterate',['--project-id','p','--prompt','x']),('projects.edit',['--project-id','p','--patch','{}']),('design-systems.update',['--design-system-id','d']),('design-systems.remix',['--design-system-id','d']),('templates.update',['--template-id','t'])])
def test_typed_mutations_handoff(command,args):
 p,o=run(command,*args); assert p.returncode==2 and o['error']['code']=='HUMAN_VERIFICATION'
@pytest.mark.parametrize('command,idflag',[('projects.delete','--project-id'),('design-systems.delete','--design-system-id'),('templates.delete','--template-id')])
def test_delete_exact_approval(command,idflag):
 _,o=run(command,idflag,'x'); assert o['error']['code']=='APPROVAL_REQUIRED'
 _,o=run(command,idflag,'x','--exact-name','Exact','--approve'); assert o['error']['code']=='HUMAN_VERIFICATION'
@pytest.mark.parametrize('stem,args',[('projects.share',['--project-id','p','--access','workspace']),('projects.comment',['--project-id','p','--text','hi']),('projects.handoff',['--project-id','p','--destination','Claude Code']),('design-systems.publish',['--design-system-id','d']),('design-systems.set-default',['--design-system-id','d']),('destinations.handoff',['--project-id','p','--destination','Canva']),('code.sync',['--repository-path','/tmp/repo','--direction','to-design']),('admin.enable',['--organization','o']),('admin.role-update',['--member','m','--role','Claude Design Admin'])])
def test_preview_apply_exact_digest(stem,args):
 _,pre=run(stem+'.preview',*args); d=pre['data']['effect_digest']; assert len(d)==64 and pre['data']['execute'] is False
 _,bad=run(stem+'.apply',*args,'--effect-digest','bad','--approve'); assert bad['error']['code']=='APPROVAL_REQUIRED'
 p,good=run(stem+'.apply',*args,'--effect-digest',d,'--approve'); assert p.returncode==2 and good['error']['code']=='HUMAN_VERIFICATION'
def test_digest_changes_with_effect():
 _,a=run('projects.share.preview','--project-id','p','--access','workspace');_,b=run('projects.share.preview','--project-id','p','--access','public');assert a['data']['effect_digest']!=b['data']['effect_digest']
def test_export_validates_args(tmp_path):
 _,o=run('projects.export','--project-id','p','--format','docx','--output-path',str(tmp_path/'x')); assert o['error']['code']=='INVALID_INPUT'
def pdf_bytes(pages=2):
 return b'%PDF-1.4\n'+b''.join(b'<< /Type /Page >>\n' for _ in range(pages))+b'%%EOF\n'
def test_export_handoff_uses_native_pdf_route_and_not_present_file_inference(tmp_path):
 _,o=run('projects.export','--project-id','p','--format','pdf','--output-path',str(tmp_path/'x.pdf')); msg=o['error']['message']
 assert o['error']['code']=='HUMAN_VERIFICATION' and 'Share > PDF > Print or Save as PDF' in msg
 assert 'projects.export.plan' in msg and 'one-page iframe/browser print is not a full-deck export' in msg
def export_args(filename='Quarterly 雪.dc.html',expected='3',observed='3'):
 from urllib.parse import quote
 return ['--file-url','https://claude.ai/design?file='+quote(filename,safe=''),'--ui-filename',filename,'--expected-pages',expected,'--observed-slides',observed]
def test_export_plan_requires_exact_selected_dc_html_and_counts():
 p,o=run('projects.export.plan',*export_args())
 assert p.returncode==0 and o['data']['decoded_file_parameter']=='Quarterly 雪.dc.html' and o['data']['exact_filename_match']
 assert o['data']['observed_slide_count_matches'] and o['data']['workflow'][2:5]==['Share','PDF','Print or Save as PDF']
 assert o['data']['read_only'] and o['data']['provider_execution'] is False
 assert 'shadow DOM' in o['data']['environment_workflow']['chrome'] and 'Save File' in o['data']['environment_workflow']['gtk']
def test_export_plan_rejects_active_file_mismatch_before_provider_blocker():
 args=export_args('Right.dc.html')
 args[args.index('--ui-filename')+1]='Wrong.dc.html'
 p,o=run('projects.export.diagnose',*args,'--provider-error','Share button disabled')
 assert p.returncode==2 and o['error']['code']=='ACTIVE_FILE_MISMATCH'
 assert o['data']['provider_error']=='Share button disabled' and 'does not exactly equal' in o['error']['message']
def test_export_plan_rejects_non_dc_html_mojibake_and_literal_unicode_escape():
 for filename in ['deck.html','Deck Ã©.dc.html',r'Deck \u96ea.dc.html']:
  p,o=run('projects.export.plan',*export_args(filename))
  assert p.returncode==2 and o['error']['code']=='ACTIVE_FILE_MISMATCH'
def test_export_plan_requires_observed_slides_equal_expected_before_share():
 p,o=run('projects.export.plan',*export_args(expected='4',observed='3'))
 assert p.returncode==2 and o['error']['code']=='SLIDE_COUNT_MISMATCH' and 'Do not Share' in o['error']['message']
def test_export_plan_rejects_one_page_iframe_print_for_full_deck():
 p,o=run('projects.export.plan',*export_args(),'--preview-pages','1')
 assert p.returncode==2 and o['error']['code']=='IFRAME_PRINT_REJECTED' and 'not a full-deck export' in o['error']['message']
def test_export_diagnose_provider_blocker_only_after_identity_and_counts_pass():
 p,o=run('projects.export.diagnose',*export_args(),'--preview-pages','3','--provider-error','Share button disabled')
 assert p.returncode==0 and o['data']['classification']=='PROVIDER_BLOCKER' and 'only after active-file identity' in o['data']['next_action']
def test_export_verify_missing(tmp_path):
 _,o=run('projects.export.verify','--output-path',str(tmp_path/'none.pdf')); assert o['error']['code']=='NOT_FOUND'
def test_export_verify_requires_artifact_metadata(tmp_path):
 f=tmp_path/'x.pdf';f.write_bytes(pdf_bytes())
 _,o=run('projects.export.verify','--output-path',str(f),'--format','pdf'); assert o['error']['code']=='INVALID_INPUT'
def test_export_verify_rejects_wrong_page_count(tmp_path):
 f=tmp_path/'x.pdf';f.write_bytes(pdf_bytes())
 _,o=run('projects.export.verify','--output-path',str(f),'--format','pdf','--project-id','p','--provenance','native-claude-design','--expected-pages','3','--qa-pages','1,2,3')
 assert o['error']['code']=='VERIFICATION_FAILED' and o['data']['page_count']==2 and o['data']['page_count_matches'] is False
def test_export_verify_requires_page_by_page_visual_qa(tmp_path):
 f=tmp_path/'x.pdf';f.write_bytes(pdf_bytes())
 _,o=run('projects.export.verify','--output-path',str(f),'--format','pdf','--project-id','p','--provenance','native-claude-design','--expected-pages','2','--qa-pages','1')
 assert o['error']['code']=='VERIFICATION_FAILED' and o['data']['missing_qa_pages']==[2]
def test_export_verify_metadata_native_provenance_and_complete_qa(tmp_path):
 f=tmp_path/'x.pdf';f.write_bytes(pdf_bytes())
 _,o=run('projects.export.verify','--output-path',str(f),'--format','pdf','--project-id','p','--provenance','native-claude-design','--expected-pages','2','--qa-pages','1,2')
 assert o['data']['bytes']==len(f.read_bytes()) and o['data']['mime']=='application/pdf' and o['data']['sha256']==hashlib.sha256(f.read_bytes()).hexdigest()
 assert o['data']['page_count']==2 and o['data']['page_count_matches'] and o['data']['visual_qa_complete'] and o['data']['provenance']=='native-claude-design'
 assert o['evidence'][0]['metadata']['provenance']=='native-claude-design'
def test_export_verify_distinguishes_fallback_provenance(tmp_path):
 f=tmp_path/'x.pdf';f.write_bytes(pdf_bytes(1))
 _,o=run('projects.export.verify','--output-path',str(f),'--format','pdf','--project-id','p','--provenance','fallback-rendering','--expected-pages','1','--qa-pages','1')
 assert o['data']['provenance']=='fallback-rendering' and o['data']['visual_qa_complete']
def test_destinations_catalog():
 _,o=run('destinations.list'); assert {'Canva','Vercel','Claude Code'}<=set(o['data']['destinations'])
def test_unknown_unsupported():
 _,o=run('invented'); assert o['error']['code']=='UNSUPPORTED'
def test_unsafe_identifier_rejected():
 _,o=run('projects.update','--project-id','../../etc/passwd'); assert o['error']['code']=='INVALID_INPUT'
def test_manifest_contract():
 m=json.loads((ROOT/'harness.json').read_text()); assert m['name']=='claude-design' and m['title']=='Claude Design' and m['version']=='0.4.0'
 assert all(x not in (ROOT/'harness.json').read_text() for x in ['minimum','maximum','minLength','enum'])
def test_contracts_match_manifest():
 m=json.loads((ROOT/'harness.json').read_text());c=json.loads((ROOT/'command_contracts.json').read_text());assert len(c['commands'])==66 and c['commands']==list(m['commands'])
def test_export_contracts_use_gateway_supported_scalar_schemas():
 m=json.loads((ROOT/'harness.json').read_text())
 for name in ['projects.export.plan','projects.export.verify','projects.export.diagnose']:
  command=m['commands'][name]
  assert command['safetyClasses']==['readOnly'] and command['inputSchema']['additionalProperties'] is False
  assert all(schema=={'type':'string'} for schema in command['inputSchema']['properties'].values())
  assert all(arg['valueType'] in {'string','path'} for arg in command['argMap'])
def test_no_secret_literals_in_distributables():
 text='\n'.join(p.read_text(errors='ignore') for p in ROOT.rglob('*') if p.is_file() and 'tests' not in p.parts)
 assert 'TOP_SECRET_SENTINEL' not in text



import subprocess as _sp, tempfile as _tf
def run_kw(command,**kw):
 args=[str(CLI),command]
 for k,v in kw.items():
  if v is True:args.append('--'+k.replace('_','-'))
  else:args+=['--'+k.replace('_','-'),str(v)]
 p=_sp.run(args,text=True,capture_output=True);return p,json.loads(p.stdout)
BASE_LINK=dict(project_id='p14',project_url='https://claude.ai/design/p14',file_url='https://claude.ai/design/p14?file=deck.dc.html',ui_filename='deck.dc.html',expected_pages='14',observed_slides='14',canvas_served='true')

def test_link_verify_produces_link_first_handoff_card():
 p,o=run_kw('projects.link.verify',**BASE_LINK,source_version='v2.3.0 @ 9f1c2d');assert p.returncode==0 and o['ok']
 d=o['data'];assert d['deliverable']=='link' and d['completion']['link_delivery_required'] and not d['completion']['native_file_export_required']
 assert 'https://claude.ai/design/p14?file=deck.dc.html' in d['handoff_card'] and 'PowerPoint' in d['handoff_card'] and '9f1c2d' in d['handoff_card']
 assert d['read_only'] and d['provider_execution'] is False and o['evidence'][0]['kind']=='link-handoff'

def test_link_verify_korean_card_and_file_mode():
 _,o=run_kw('projects.link.verify',**BASE_LINK,language='ko',deliverable='file');d=o['data']
 assert '슬라이드: 14장' in d['handoff_card'] and d['completion']['native_file_export_required'] and 'native-export' in d['next_action']

def test_link_verify_fails_closed_on_mismatch_and_bad_urls():
 for kw,code in ((dict(observed_slides='13'),'SLIDE_COUNT_MISMATCH'),(dict(canvas_served='false'),'CANVAS_NOT_SERVED'),(dict(ui_filename='other.dc.html'),'ACTIVE_FILE_MISMATCH'),(dict(project_url='https://evil.example/design/p14'),'INVALID_INPUT'),(dict(language='fr'),'INVALID_INPUT'),(dict(file_url='https://claude.ai/design/p99?file=deck.dc.html'),'ACTIVE_FILE_MISMATCH')):
  p,o=run_kw('projects.link.verify',**{**BASE_LINK,**kw});assert p.returncode==2 and o['error']['code']==code and o['retry_safe'] is False,(kw,o)
 m=json.loads((ROOT/'harness.json').read_text());assert m['commands']['projects.link.verify']['safetyClasses']==['readOnly'] and any('link' in w for w in m['whenToUse'])

def _layout(slides):return {"viewport":{"width":1920,"height":1080},"slides":slides}
def _write(tmp,obj):
 f=Path(tmp)/'layout.json';f.write_text(json.dumps(obj));return f
CLEAN=[{"index":i,"elements":[{"id":f"t{i}","kind":"text","text":"Title","bbox":[120,80,800,60],"fontPx":36,"clientWidth":800,"scrollWidth":700},
 {"id":f"box{i}","kind":"shape","shape":"rect","bbox":[120,200,400,200]},{"id":f"b{i}","kind":"text","text":"Body text that fits","bbox":[140,220,360,80],"fontPx":18,"parent":f"box{i}","clientWidth":360,"scrollWidth":300,"clientHeight":80,"scrollHeight":60}]} for i in (1,2,3)]

def test_qa_layout_passes_clean_deck(tmp_path):
 p,o=run_kw('projects.qa.layout',layout_json=_write(tmp_path,_layout(CLEAN)),expected_pages='3');assert p.returncode==0 and o['data']['pass'] and o['data']['summary']=={'slides':3,'critical':0,'warning':0}
 assert o['data']['qa_pages']==[1,2,3] and o['data']['revision_prompt'] is None and o['evidence'][0]['kind']=='layout-qa'

def test_qa_layout_catches_overflow_escape_overlap_misalignment_and_drift(tmp_path):
 bad=json.loads(json.dumps(CLEAN))
 s2=bad[1]['elements'];s2[2]['scrollWidth']=520                                  # text wider than box
 s2.append({"id":"esc","kind":"text","text":"escapes","bbox":[300,380,300,60],"fontPx":18,"parent":"box2"})   # escapes container
 s2.append({"id":"ov1","kind":"text","text":"a","bbox":[900,500,200,50],"fontPx":12});s2.append({"id":"ov2","kind":"text","text":"b","bbox":[950,510,200,50],"fontPx":18})  # overlap + small font
 s3=bad[2]['elements'];s3[0]['bbox']=[120,92,800,60];s3.append({"id":"sub","kind":"text","text":"subtitle","bbox":[131,150,600,40],"fontPx":20})  # title drift + almost left-aligned subtitle
 s3+= [{"id":"c1","kind":"shape","shape":"rect","bbox":[100,600,200,100]},{"id":"c2","kind":"shape","shape":"rect","bbox":[320,600,200,100]},{"id":"c3","kind":"shape","shape":"rect","bbox":[560,600,200,100]},{"id":"off","kind":"shape","shape":"pill","bbox":[1800,900,300,100]},{"id":"c4","kind":"shape","shape":"diamond","bbox":[100,800,50,50]},{"id":"c5","kind":"shape","shape":"cloud","bbox":[200,800,50,50]}]
 p,o=run_kw('projects.qa.layout',layout_json=_write(tmp_path,_layout(bad)),expected_pages='4')
 assert p.returncode==2 and o['error']['code']=='QA_FAILED' and o['retry_safe'] is False
 d=o['data'];codes={f['code'] for s in d['slides'] for f in s['findings']}|{f['code'] for f in d['deck_findings']}
 for code in ('TEXT_OVERFLOW','TEXT_OUTSIDE_SHAPE','OVERLAP','FONT_TOO_SMALL','MISALIGNED_EDGE','UNEVEN_SPACING','OFF_CANVAS','INCONSISTENT_SHAPES','TITLE_DRIFT','PAGE_COUNT_MISMATCH'):assert code in codes,code
 assert d['revision_prompt'].startswith('Fix the following layout defects') and 'Slide 2:' in d['revision_prompt'] and 'Deck:' in d['revision_prompt']

def test_qa_layout_strict_and_invalid_inputs(tmp_path):
 warn=json.loads(json.dumps(CLEAN));warn[0]['elements'][0]['fontPx']=10
 _,o=run_kw('projects.qa.layout',layout_json=_write(tmp_path,_layout(warn)));assert o['ok'] and o['data']['summary']['warning']==1
 p,o=run_kw('projects.qa.layout',layout_json=_write(tmp_path,_layout(warn)),strict=True);assert p.returncode==2 and o['error']['code']=='QA_FAILED'
 p,o=run_kw('projects.qa.layout',layout_json=str(Path(tmp_path)/'missing.json'));assert o['error']['code']=='NOT_FOUND'
 p,o=run_kw('projects.qa.layout',layout_json=_write(tmp_path,{"slides":[]}));assert o['error']['code']=='INVALID_INPUT'
 p,o=run_kw('projects.qa.layout',layout_json=_write(tmp_path,_layout(CLEAN)),overlap_ratio='7');assert o['error']['code']=='INVALID_INPUT'
