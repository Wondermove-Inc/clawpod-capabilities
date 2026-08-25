import json, subprocess, zipfile
from pathlib import Path
ROOT=Path(__file__).parents[1]; CLI=ROOT/'claude_design.py'
def run(command, **kw):
 args=[str(CLI),command]
 for k,v in kw.items():
  args += ['--'+k.replace('_','-'),str(v)]
 p=subprocess.run(args,text=True,capture_output=True);return p,json.loads(p.stdout)
BASE=dict(project_id='p14',project_url='https://claude.ai/design/p14',file_url='https://claude.ai/design/p14?file=deck.dc.html',ui_filename='deck.dc.html',thumbnail_id='result-14',expected_pages='14',attempt='1')
def observed(**extra):
 d={**BASE,'observed_project_id':'p14','observed_thumbnail_id':'result-14','active_url':BASE['file_url'],'observed_ui_filename':'deck.dc.html','observed_slides':'14','canvas_served':'true','browser_healthy':'true','fresh_list_read':'true'};d.update(extra);return d

def test_plan_is_pure_bounded_idempotent_and_prohibits_blind_retries():
 _,a=run('projects.reenter.plan',**BASE);_,b=run('projects.reenter.plan',**BASE)
 for x in (a,b):
  d=x['data'];assert d['execute'] is False and d['providerExecution'] is False and d['maxAttempts']==2
  assert {'waiting on a stale URL','repeated refresh','duplicate prompt or project creation','Gateway restart'}<=set(d['prohibited'])
  assert 'does not click Browser' in d['handoff']
 assert {k:v for k,v in a['data'].items() if k!='request_id'}=={k:v for k,v in b['data'].items() if k!='request_id'}

def test_A_recovered_exact_14_slide_route():
 p,o=run('projects.reenter.verify',**observed());assert p.returncode==0 and o['data']['state']=='recovered' and not o['data']['retryAllowed']

def test_B_provider_failure_only_after_two_exact_bounded_attempts_and_redacts():
 d=observed(attempt='2',canvas_served='false',attempt1_fresh_list='true',attempt2_fresh_list='true',attempt1_browser_healthy='true',attempt2_browser_healthy='true',attempt1_thumbnail_id='result-14',attempt2_thumbnail_id='result-14',attempt1_error='OmeletteService/GetFile 404 token=FIRST_SECRET',attempt2_error='claudeusercontent thumbnail 404 authorization=SECOND_SECRET')
 p,o=run('projects.file_route.diagnose',**d);assert p.returncode==0 and o['data']['state']=='provider_failure' and not o['data']['retryAllowed']
 assert 'FIRST_SECRET' not in p.stdout and 'SECOND_SECRET' not in p.stdout and '[REDACTED]' in p.stdout

def test_C_browser_failure_is_never_provider_failure():
 d=observed(browser_healthy='false',attempt1_fresh_list='true',attempt2_fresh_list='true',attempt1_browser_healthy='false',attempt2_browser_healthy='true',attempt1_thumbnail_id='result-14',attempt2_thumbnail_id='result-14',attempt1_error='GetFile 404',attempt2_error='GetFile 404')
 _,o=run('projects.file_route.diagnose',**d);assert o['data']['state']=='browser_failure' and 'never provider_failure' in o['data']['stopReason']

def test_D_exact_thumbnail_identity_among_multiple_results():
 _,o=run('projects.reenter.verify',**observed(observed_thumbnail_id='other-result'));assert o['data']['state']=='stale_route'
 d=observed(attempt='2',attempt1_fresh_list='true',attempt2_fresh_list='true',attempt1_browser_healthy='true',attempt2_browser_healthy='true',attempt1_thumbnail_id='other-result',attempt2_thumbnail_id='result-14',attempt1_error='thumbnail 404',attempt2_error='thumbnail 404')
 _,o=run('projects.file_route.diagnose',**d);assert o['data']['state']!='provider_failure'

def test_E_recovery_then_independent_pptx_pdf_14_of_14_export_verification(tmp_path):
 _,o=run('projects.file_route.diagnose',**observed(export_initiated='true',artifact_valid='false'));assert o['data']['state']=='export_failure'
 _,o=run('projects.file_route.diagnose',**observed(export_initiated='true',artifact_valid='true'));assert o['data']['state']=='recovered' and 'post-recovery QA' in o['data']['nextAction']
 pages=','.join(str(x) for x in range(1,15));common=dict(project_id='p14',provenance='native-claude-design',expected_pages='14',review_pass_1=pages,review_pass_2=pages,render_pages=pages,reflow_pages=pages)
 pptx=tmp_path/'deck.pptx'
 with zipfile.ZipFile(pptx,'w') as z:
  for n in range(1,15):z.writestr(f'ppt/slides/slide{n}.xml',f'<slide>{n}</slide>')
 p,ppt=run('projects.export.verify',output_path=pptx,format='pptx',**common);assert p.returncode==0 and ppt['data']['page_count']==14 and ppt['data']['post_recovery_qa_complete']
 pdf=tmp_path/'deck.pdf';pdf.write_bytes(b'%PDF-1.4\n'+b''.join(b'<< /Type /Page >>\n' for _ in range(14))+b'%%EOF\n')
 p,pd=run('projects.export.verify',output_path=pdf,format='pdf',qa_pages=pages,**common);assert p.returncode==0 and pd['data']['page_count']==14 and pd['data']['post_recovery_qa_complete']
 assert ppt['data']['sha256'] != pd['data']['sha256']

def test_invalid_missing_and_ambiguous_evidence_fail_closed():
 p,o=run('projects.reenter.plan',**{**BASE,'attempt':'3'});assert p.returncode==2 and o['error']['code']=='INVALID_INPUT'
 d={**BASE,'browser_healthy':'true'};_,o=run('projects.reenter.verify',**d);assert o['data']['state']=='ambiguous' and not o['data']['retryAllowed']

def test_manifest_commands_are_closed_read_only_scalar_contracts():
 m=json.loads((ROOT/'harness.json').read_text())
 for n in ['projects.reenter.plan','projects.reenter.verify','projects.file_route.diagnose']:
  c=m['commands'][n];assert c['safetyClasses']==['readOnly'] and c['inputSchema']['additionalProperties'] is False
  assert all(v=={'type':'string'} for v in c['inputSchema']['properties'].values())
 flags={item['arg']:item['flag'] for item in m['commands']['projects.export.verify']['argMap']}
 assert flags['reviewPass1']=='--review-pass-1' and flags['reviewPass2']=='--review-pass-2'
