import copy, hashlib, importlib.util, json, os, shutil, subprocess, tempfile, unittest
from pathlib import Path

PACKAGE=Path(__file__).resolve().parents[1]; ROOT=PACKAGE.parents[1]; CLI=PACKAGE/'memory_graph.py'; FIXTURE=Path(__file__).parent/'fixtures/entity-proposals'
spec=importlib.util.spec_from_file_location('ontology_v09',PACKAGE/'ontology.py'); ontology=importlib.util.module_from_spec(spec); spec.loader.exec_module(ontology)

class OntologyV09Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=Path(tempfile.mkdtemp()); shutil.copytree(FIXTURE/'memory',self.tmp/'memory'); self.bundle=self.make_bundle(); self.save()
 def tearDown(self): shutil.rmtree(self.tmp)
 def cli(self,cmd,expected=0):
  p=subprocess.run([str(CLI),cmd,'--root',str(self.tmp),'--input','bundle.json','--agent-id','test-agent','--workspace-id','test-workspace'],cwd=ROOT,text=True,capture_output=True)
  self.assertEqual(p.returncode,expected,p.stdout+p.stderr); self.assertEqual(p.stderr,''); return json.loads(p.stdout)
 def plan(self):
  p=subprocess.run([str(CLI),'plan','--root',str(self.tmp),'--agent-id','test-agent','--workspace-id','test-workspace','--detail'],cwd=ROOT,text=True,capture_output=True,check=True); return json.loads(p.stdout)['data']
 def source(self,claim, evidence=False):
  d={'path':claim['path'],'line_start':claim['line'],'line_end':claim['line'],'source_content_hash':hashlib.sha256((self.tmp/claim['path']).read_bytes()).hexdigest(),'claim_content_hash':claim['content_hash']}
  if evidence:d['evidence_excerpt_hash']='a'*64
  return d
 def make_bundle(self):
  plan=self.plan(); claims={x['claim_id']:x for x in plan['claims']}; ns=plan['ownership']['namespace']; extractor={'extractor_id':'claim-entity-extractor','extractor_version':'1.0.0','config_hash':'c'*64}; review={'reviewer_id':'human:test','reviewed_at':'2026-08-10T00:00:00Z','review_reason':'claim_explicitly_identifies_entity'}
  specs=[('entity_person_mina','person:mina','Person'),('entity_person_lee','person:lee','Person'),('entity_project_alpha','project:alpha','Project'),('entity_project_beta','project:beta','Project'),('entity_decision_d1','decision:d1','Decision'),('entity_decision_d2','decision:d2','Decision'),('entity_decision_d3','decision:d3','Decision'),('entity_event_e1','event:e1','Event'),('entity_event_e2','event:e2','Event'),('entity_event_e3','event:e3','Event')]
  proposals=[]
  for cid,eid,typ in specs:
   temporal=None if typ in {'Person','Project'} else {'start':'2026-01-01T00:00:00+09:00','end':None,'precision':'day','timezone':'Asia/Seoul'}
   x={'entity_proposal_id':'','namespace':ns,'entity':{'entity_id':eid,'type':typ},'source_claim_id':cid,'source':self.source(claims[cid]),'extractor':extractor,'status':'approved','review':review,'temporal':temporal}; x['entity_proposal_id']=ontology.entity_proposal_id(ns,x); proposals.append(x)
  intents=json.loads((PACKAGE/'tests/fixtures/ontology/assertion-intents.json').read_text()); assertions=[]
  for i,(sub,st,pred,obj,ot,method) in enumerate(intents):
   cid='relation_direct_cause' if pred=='caused' else 'relation_semantic_set'; r={'reviewer_id':'human:test','reviewed_at':'2026-08-10T00:00:00Z','review_reason':'direct_causal_statement'} if method=='human_approved' else None
   x={'assertion_id':'','subject':{'entity_id':sub,'type':st},'predicate':pred,'object':{'entity_id':obj,'type':ot},'source_claim_id':cid,'source':self.source(claims[cid],True),'method':method,'asserted_at':'2026-08-10T00:00:00Z','valid_time':{'start':'2026-01-01T00:00:00+09:00','end':None,'precision':'day','timezone':'Asia/Seoul'},'status':'approved','review':r,'extractor':None,'confidence':None}; x['assertion_id']=ontology.assertion_id(ns,x); assertions.append(x)
  return {'schema_version':'memory-graph-assertions/v2','semantic_contract_version':'0.9','namespace':ns,'source_snapshot_hash':plan['snapshot_hash'],'source_digest':plan['source_digest'],'entity_proposals':proposals,'assertions':assertions,'identity_candidates':[]}
 def save(self): (self.tmp/'bundle.json').write_text(json.dumps(self.bundle,sort_keys=True,separators=(',',':')))
 def reasons(self): return {x['reason_code'] for x in self.cli('ontology-validate')['data']['quarantine']}
 def test_realistic_bootstrap_release_gates_and_semantic_view(self):
  self.assertGreaterEqual(len(self.plan()['claims']),10); data=self.cli('ontology-validate')['data']; self.assertTrue(data['conforms']); self.assertEqual(len(data['entity_proposals']),10); self.assertEqual(len(data['accepted_assertions']),12); self.assertTrue(all(x['subject_entity_source']=='approved_private_proposal' and x['object_entity_source']=='approved_private_proposal' for x in data['accepted_assertions']))
  cq=self.cli('cq-evaluate')['data']; self.assertTrue(cq['passed']); self.assertEqual(cq['metrics']['cq_pass_count'],5); self.assertEqual(cq['metrics']['unsupported_approved_edge_count'],0); self.assertEqual(cq['metrics']['canonical_hydration_locator_coverage'],1.0)
  view=self.cli('semantic-view')['data']; self.assertEqual(len(view['approved_assertions']),12); self.assertFalse(view['structural_relations']); self.assertIn('Approved private entity proposal',{x['label'] for x in view['nodes']})
 def test_candidate_and_missing_review_are_inert(self):
  p=self.bundle['entity_proposals'][0]; p['status']='candidate'; p['review']=None; self.save(); self.assertIn('unapproved_entity_proposal',self.reasons()); q=self.cli('review-queue')['data']; self.assertEqual(len(q['entity_candidates']),1); self.assertFalse(q['mutation_performed'])
  self.bundle=self.make_bundle(); self.bundle['entity_proposals'][0]['review']=None; self.save(); self.assertIn('missing_review',self.reasons())
  self.bundle=self.make_bundle(); self.bundle['entity_proposals'][0]['review']['review_reason']='looks_plausible'; self.save(); self.assertIn('invalid_review',self.reasons())
 def test_temporal_closed_shape_and_precision(self):
  p=next(x for x in self.bundle['entity_proposals'] if x['entity']['type']=='Decision'); self.assertEqual(p['temporal']['precision'],'day'); p['temporal']['start']='2026-01-01T00:00:00'; p['entity_proposal_id']=ontology.entity_proposal_id(self.bundle['namespace'],p); self.save(); self.assertIn('invalid_temporal_shape',self.reasons())
  self.bundle=self.make_bundle(); self.bundle['entity_proposals'][0]['temporal']={'start':None,'end':None,'precision':'unknown','timezone':'unknown'}; self.save(); self.assertIn('invalid_temporal_shape',self.reasons())
 def test_stale_claim_source_and_id(self):
  p=self.bundle['entity_proposals'][0]; p['source']['claim_content_hash']='b'*64; p['entity_proposal_id']=ontology.entity_proposal_id(self.bundle['namespace'],p); self.save(); self.assertIn('claim_hash_mismatch',self.reasons())
  out=self.cli('ontology-validate')['data']; self.assertIn('stale_entity_proposal',{x['reason_code'] for x in out['quarantine'] if x['record_kind']=='assertion'})
  self.bundle=self.make_bundle(); self.bundle['entity_proposals'][0]['entity_proposal_id']='ep_'+'f'*64; self.save(); self.assertIn('entity_proposal_id_mismatch',self.reasons())
  self.bundle=self.make_bundle(); p=self.bundle['entity_proposals'][0]; p['source']['line_end']+=1; p['entity_proposal_id']=ontology.entity_proposal_id(self.bundle['namespace'],p); self.save(); self.assertIn('stale_provenance',self.reasons())
 def test_path_namespace_secret_and_unknown_keys_fail_closed(self):
  p=self.bundle['entity_proposals'][0]; p['source']['path']='../MEMORY.md'; p['entity_proposal_id']=ontology.entity_proposal_id(self.bundle['namespace'],p); self.save(); self.assertIn('path_escape',self.reasons())
  self.bundle=self.make_bundle(); self.bundle['entity_proposals'][0]['namespace']='memory-graph:v1:'+'f'*24+':'; self.save(); self.assertIn('cross_namespace_entity',self.reasons())
  self.bundle=self.make_bundle(); secret='sk_'+'test_'+'12345678901234567890'; self.bundle['entity_proposals'][0]['entity']['entity_id']='person:'+secret; self.save(); out=self.cli('ontology-validate'); self.assertNotIn(secret,json.dumps(out)); self.assertIn('secret_like_entity_proposal',{x['reason_code'] for x in out['data']['quarantine']})
  self.bundle=self.make_bundle(); secret='sk_'+'test_'+'abcdefghijklmnopqrst'; p=self.bundle['entity_proposals'][0]; p['source_claim_id']=secret; p['entity_proposal_id']=ontology.entity_proposal_id(self.bundle['namespace'],p); self.save(); out=self.cli('ontology-validate'); self.assertNotIn(secret,json.dumps(out)); self.assertTrue(any(x.get('redacted') for x in out['data']['quarantine']))
  self.bundle=self.make_bundle(); self.bundle['entity_proposals'][0]['extra']=1; self.save(); self.assertIn('invalid_entity_proposal_shape',self.reasons())
 def test_duplicate_idempotency_conflict_and_reordering(self):
  first=self.cli('ontology-validate')['data']; self.bundle['entity_proposals'].reverse(); self.bundle['assertions'].reverse(); self.save(); self.assertEqual(first,self.cli('ontology-validate')['data'])
  self.bundle=self.make_bundle(); self.bundle['entity_proposals'].append(copy.deepcopy(self.bundle['entity_proposals'][0])); self.save(); self.assertEqual(len(self.cli('ontology-validate')['data']['entity_proposals']),10)
  self.bundle=self.make_bundle(); dup=copy.deepcopy(self.bundle['entity_proposals'][0]); dup['status']='candidate'; dup['review']=None; self.bundle['entity_proposals'].append(dup); self.save(); self.assertEqual(self.cli('ontology-validate',2)['error']['code'],'conflicting_entity_proposal')
 def test_identity_alias_never_merges(self):
  self.bundle['identity_candidates']=[{'candidate_id':'idc_1','left':{'type':'Person','entity_id':'person:mina'},'right':{'type':'Person','entity_id':'person:lee'},'feature_codes':['same_alias'],'score':.9,'method':'blocking','version':'1','config_hash':'d'*64,'source_claim_ids':['entity_person_mina']}]; self.save(); c=self.cli('review-queue')['data']['identity_candidates'][0]; self.assertFalse(c['auto_merge']); self.assertFalse(c['projected']); self.assertTrue(c['aliases_inert'])
 def test_causality_chronology_is_insufficient(self):
  x=next(x for x in self.bundle['assertions'] if x['predicate']=='caused'); x['review']['review_reason']='chronology_only'; self.save(); self.assertIn('causality_not_direct',self.reasons())
  self.bundle=self.make_bundle(); x=next(x for x in self.bundle['assertions'] if x['predicate']=='caused'); x['method']='explicit'; x['review']=None; x['assertion_id']=ontology.assertion_id(self.bundle['namespace'],x); self.save(); self.assertIn('causality_requires_human_approval',self.reasons())
 def test_v08_migration_compatibility(self):
  legacy=self.bundle.copy(); legacy.pop('entity_proposals'); legacy['schema_version']='memory-graph-assertions/v1'; legacy['semantic_contract_version']='0.8'; legacy['assertions']=[]; (self.tmp/'bundle.json').write_text(json.dumps(legacy)); data=self.cli('ontology-validate')['data']; self.assertEqual(data['migration'],{'from':'0.8','to':'0.9','input_rewritten':False}); self.assertFalse(data['entity_proposals'])
 def test_source_immutability_and_symlink_rejected(self):
  files=list((self.tmp/'memory').rglob('*.md')); before=[(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns,p.stat().st_mode) for p in files]; self.cli('ontology-validate'); after=[(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns,p.stat().st_mode) for p in files]; self.assertEqual(before,after)
  self.bundle=self.make_bundle(); target=self.tmp/'memory/entity-bootstrap.md'; real=self.tmp/'memory/real.md'; target.rename(real); target.symlink_to(real); self.save(); out=self.cli('ontology-validate',2); self.assertIn(out['error']['code'],{'symlink_source','path_escape','unsafe_memory_path'})
 def test_bounds_malformed_lifecycle_and_no_network_surface(self):
  (self.tmp/'bundle.json').write_text('{bad'); self.assertEqual(self.cli('ontology-validate',2)['error']['code'],'malformed_bundle')
  self.bundle=self.make_bundle(); self.bundle['entity_proposals']*=26; self.save(); self.assertEqual(self.cli('ontology-validate',2)['error']['code'],'invalid_assertion_bundle')
  self.bundle=self.make_bundle(); self.bundle['entity_proposals'][0]['status']='invented'; self.save(); self.assertIn('invalid_lifecycle',self.reasons())
  source=(PACKAGE/'ontology.py').read_text().lower(); [self.assertNotIn(x,source) for x in ('requests','urllib','socket','mcporter','openai','anthropic')]

if __name__=='__main__': unittest.main()
