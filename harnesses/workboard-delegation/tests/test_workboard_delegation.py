import json, subprocess, sys
from io import StringIO
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]))
import workboard_delegation as w

def pargs(owner=None,non_goals=None):
 a=['plan','--leader-id','L','--title','Execute','--agent-id','worker','--scope','run bounded tests','--done-when','all pass','--evidence-required','test log','--report-back-target','leader card']
 if owner:a+=['--expected-leader-owner-id',owner]
 if non_goals:a+=['--non-goals',non_goals]
 return a
def plan(owner=None,non_goals=None):return w.make_plan(w.parser().parse_args(pargs(owner,non_goals)))
def leader(owner=None,parents=None,comments=None):return {'id':'L','parents':parents or [],'metadata':{'claim':({'ownerId':owner} if owner else {}),'comments':comments or []}}
def child(p=None,**over):
 p=p or plan();f=p['createFields'];c={'id':'E','title':f['title'],'notes':f['notes'],'agentId':f['agentId'],'parents':[],'metadata':{'automation':{'tenant':f['tenant'],'boardId':f['boardId'],'createdByCardId':f['createdByCardId'],'idempotencyKey':f['idempotencyKey']}}};c.update(over);return c
def comment(p=None,eid='E'):p=p or plan();return {'body':p['commentTemplate'].replace('{executionCardId}',eid)}
def vargs(cmd,p=None,l=None,e=None,owner=None):
 p=p or plan(owner);a=[cmd,'--plan-json',w.stable(p),'--plan-hash',p['planHash'],'--leader-snapshot',w.stable(l or leader(owner))]
 if owner:a+=['--expected-leader-owner-id',owner]
 if e is not None:a+=['--execution-snapshot',w.stable(e)]
 return a
def run(a):
 old=sys.stdout;sys.stdout=b=StringIO()
 try:rc=w.main(a)
 finally:sys.stdout=old
 return rc,json.loads(b.getvalue())

def test_plan_determinism():assert plan()==plan()
def test_plan_hash_stable():assert len(plan()['planHash'])==64
def test_owner_changes_hash():assert plan('a')['planHash']!=plan('b')['planHash']
def test_non_goals_changes_hash():assert plan(non_goals='x')['planHash']!=plan()['planHash']
def test_idempotency_stable():assert plan()['createFields']['idempotencyKey']==plan()['createFields']['idempotencyKey']
def test_plan_contains_exact_create_fields():
 p=plan();assert set(p['createFields'])=={'title','notes','agentId','tenant','boardId','labels','createdByCardId','idempotencyKey'}
def test_structured_notes_complete():
 n=plan(non_goals='no deploy')['createFields']['notes']
 for x in ('leader_sot_card_id: L','practitioner_agent_id: worker','scope: run bounded tests','non_goals: no deploy','done_when: all pass','evidence_required: test log','report_back_target: leader card','dependency_mode: related-card-not-parent-child'):assert x in n
def test_comment_marker_and_template():
 p=plan();assert p['commentMarker'].startswith('[workboard-delegation:') and 'workboard-delegation:workboard-delegation:' not in p['commentMarker'] and p['commentMarker'] in p['commentTemplate'] and '{executionCardId}' in p['commentTemplate']
def test_plan_output_preview():assert run(pargs())[1]['data']['preview']==plan()
def test_plan_output_fits_gateway_preview():assert len(w.stable(run(pargs())[1]).encode()) <= w.MAX_STDOUT_BYTES
def test_oversized_plan_output_rejected():
 a=pargs();a[a.index('--scope')+1]='x'*1800
 assert run(a)[1]['error']['code']=='plan_output_too_large'
def test_status_pure():
 o=run(['status'])[1];assert o['data']['pure'] and not o['data']['gatewayCalls'] and not o['data']['mutates'] and not o['performed']
def test_parse_snapshot_object():assert w.parse_json_arg('{"id":"L"}','x',100)=={'id':'L'}
def test_snapshot_array_rejected():
 with pytest.raises(w.HarnessError) as e:w.parse_json_arg('[]','x',100)
 assert e.value.code=='invalid_snapshot'
def test_snapshot_malformed():
 with pytest.raises(w.HarnessError) as e:w.parse_json_arg('{','x',100)
 assert e.value.code=='malformed_json'
def test_snapshot_bound():
 with pytest.raises(w.HarnessError) as e:w.parse_json_arg('x'*101,'x',100)
 assert e.value.code=='input_too_large'
def test_redaction_nested_and_text():assert w.redact({'token':'abc','x':'Bearer xyz'})=={'token':'[REDACTED]','x':'Bearer [REDACTED]'}
def test_plan_integrity_tamper():
 p=plan();p['createFields']['title']='bad';rc,o=run(vargs('validate-leader',p=p));assert o['error']['code']=='plan_integrity_mismatch'
def test_approved_hash_mismatch():
 p=plan();a=vargs('validate-leader',p=p);a[a.index('--plan-hash')+1]='0'*64;assert run(a)[1]['error']['code']=='plan_hash_mismatch'
def test_unclaimed_leader_valid():assert run(vargs('validate-leader'))[1]['data']['valid']
def test_claimed_matching_owner_valid():assert run(vargs('validate-leader',p=plan('lead'),l=leader('lead'),owner='lead'))[1]['data']['claimOwnerId']=='lead'
def test_claimed_owner_required():assert run(vargs('validate-leader',l=leader('lead')))[1]['error']['code']=='expected_owner_required'
def test_claimed_owner_mismatch():assert run(vargs('validate-leader',p=plan('other'),l=leader('lead'),owner='other'))[1]['error']['code']=='foreign_claim'
def test_unclaimed_expected_owner_rejected():assert run(vargs('validate-leader',p=plan('lead'),l=leader(),owner='lead'))[1]['error']['code']=='owner_mismatch'
def test_owner_argument_must_match_plan():assert run(vargs('validate-leader',p=plan(),l=leader(),owner='x'))[1]['error']['code']=='expected_owner_mismatch'
def test_dependency_rejected():assert run(vargs('validate-leader',l=leader(parents=['P'])))[1]['error']['code']=='dependency_mode_rejected'
def test_leader_id_mismatch():assert run(vargs('validate-leader',l={'id':'X','metadata':{}}))[1]['error']['code']=='leader_id_mismatch'
def test_validate_result_success_nested_comments():
 p=plan();l=leader(comments=[comment(p)]);assert run(vargs('validate-result',p,l,child(p)))[1]['data']['valid']
def test_validate_result_success_top_comments():
 p=plan();l=leader();l['comments']=[comment(p)];assert run(vargs('validate-result',p,l,child(p)))[1]['data']['valid']
def test_execution_notes_mismatch():assert run(vargs('validate-result',e=child(notes='bad')))[1]['error']['code']=='execution_mismatch'
def test_execution_automation_mismatch():
 p=plan();c=child(p);c['metadata']['automation']['idempotencyKey']='bad';assert run(vargs('validate-result',p,e=c))[1]['error']['code']=='execution_mismatch'
def test_execution_parents_rejected():assert run(vargs('validate-result',e=child(parents=['P'])))[1]['error']['code']=='execution_mismatch'
def test_missing_comment():assert run(vargs('validate-result',e=child()))[1]['error']['code']=='comment_missing'
def test_duplicate_comment():
 p=plan();l=leader(comments=[comment(p),comment(p)]);assert run(vargs('validate-result',p,l,child(p)))[1]['error']['code']=='duplicate_comment'
def test_reconcile_absent_execution_requests_create():
 o=run(vargs('reconcile-plan'))[1];assert o['data']['actions'][0]['action']=='create' and not o['data']['mutates']
def test_reconcile_existing_missing_comment_requests_comment():
 p=plan();o=run(vargs('reconcile-plan',p,e=child(p)))[1];assert o['data']['actions']==[{'action':'comment','cardId':'L','body':p['commentTemplate'].replace('{executionCardId}','E'),'reason':'cross-reference missing'}]
def test_reconcile_complete_no_actions():
 p=plan();o=run(vargs('reconcile-plan',p,leader(comments=[comment(p)]),child(p)))[1];assert o['data']['actions']==[]
def test_reconcile_conflict_refuses_create():assert run(vargs('reconcile-plan',e=child(notes='bad')))[1]['error']['code']=='execution_mismatch'
def test_reconcile_duplicate_comment_human_review():
 p=plan();assert run(vargs('reconcile-plan',p,leader(comments=[comment(p),comment(p)]),child(p)))[1]['error']['code']=='duplicate_comment'
def test_all_commands_read_only_manifest():
 h=json.loads((Path(__file__).parents[1]/'harness.json').read_text());assert set(h['commands'])=={'status','plan','validate-leader','validate-result','reconcile-plan'};assert all(c['safetyClasses']==['readOnly'] for c in h['commands'].values())
def test_manifest_has_no_backend_terms():
 s=(Path(__file__).parents[1]/'harness.json').read_text();assert 'gateway' not in s.lower() and 'writeSafe' not in s and 'leaderToken' not in s
def test_manifest_simple_schemas():
 h=json.loads((Path(__file__).parents[1]/'harness.json').read_text());allowed={'string','boolean','integer','number','array','object'}
 for c in h['commands'].values():
  for x in c['inputSchema'].get('properties',{}).values():assert x['type'] in allowed
def test_source_has_no_subprocess_or_openclaw():
 s=(Path(__file__).parents[1]/'workboard_delegation.py').read_text();assert 'subprocess' not in s and 'openclaw gateway' not in s and 'workboard.' not in s
def test_subprocess_status_invocation():
 exe=str(Path(__file__).parents[1]/'workboard_delegation.py');cp=subprocess.run([sys.executable,exe,'status'],capture_output=True,text=True);assert cp.returncode==0 and json.loads(cp.stdout)['data']['pure']
def test_subprocess_plan_invocation():
 exe=str(Path(__file__).parents[1]/'workboard_delegation.py');cp=subprocess.run([sys.executable,exe,*pargs()],capture_output=True,text=True);assert cp.returncode==0 and json.loads(cp.stdout)['data']['preview']['planHash']==plan()['planHash']
def test_error_envelope_never_performed():
 rc,o=run(['validate-leader','--plan-json','{}','--plan-hash','x','--leader-snapshot','{}']);assert rc==2 and not o['performed'] and o['effects']==[] and not o['error']['performed']
