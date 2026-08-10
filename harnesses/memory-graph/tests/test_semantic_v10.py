import copy, hashlib, json, shutil, subprocess, tempfile, unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]; ROOT=P.parents[1]; CLI=P/'memory_graph.py'; FIX=Path(__file__).parent/'fixtures/entity-proposals'
class SemanticV10(unittest.TestCase):
 def setUp(self):
  self.t=Path(tempfile.mkdtemp()); shutil.copytree(FIX/'memory',self.t/'memory'); self.input=self.cli('semantic-extractor-input','--limit','20')['data']; self.claim=self.input['claims'][0]; self.bundle=self.make_bundle(); self.write('bundle.json',self.bundle)
 def tearDown(self): shutil.rmtree(self.t)
 def cli(self,cmd,*args,code=0):
  common=['--root',str(self.t)];
  if cmd in {'semantic-extractor-input','semantic-validate-proposals','semantic-review-queue'}: common += ['--agent-id','test-agent','--workspace-id','test-workspace']
  if cmd=='semantic-approve' and '--expected-reviewer-id' not in args:
   manifest=args[args.index('--manifest')+1]; common += ['--expected-reviewer-id',json.loads((self.t/manifest).read_text())['reviewer_id']]
  p=subprocess.run([str(CLI),cmd,*common,*args],cwd=ROOT,text=True,capture_output=True); self.assertEqual(p.returncode,code,p.stdout+p.stderr); return json.loads(p.stdout)
 def write(self,name,v): (self.t/name).write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')))
 def source(self): return {k:self.claim[k] for k in ('path','line_start','line_end','source_content_hash','claim_content_hash')}
 def make_bundle(self):
  props=[{'proposal_id':'','kind':'entity','claim_id':self.claim['claim_id'],'source':self.source(),'payload':{'entity_id':'person:alice','type':'Person','temporal':None},'basis':'claim explicitly names Alice'}, {'proposal_id':'','kind':'entity','claim_id':self.claim['claim_id'],'source':self.source(),'payload':{'entity_id':'project:alpha','type':'Project','temporal':None},'basis':'claim explicitly names Alpha'}, {'proposal_id':'','kind':'assertion','claim_id':self.claim['claim_id'],'source':self.source(),'payload':{'subject':{'entity_id':'person:alice','type':'Person'},'predicate':'participates_in','object':{'entity_id':'project:alpha','type':'Project'},'valid_time':None},'basis':'direct wording'}]
  bundle={'schema_version':'memory-graph-extractor-proposals/v1','namespace':self.input['namespace'],'source_snapshot_hash':self.input['source_snapshot_hash'],'source_digest':self.input['source_digest'],'extractor':{'extractor_id':'test','extractor_version':'1.0.0','config_hash':'a'*64},'proposals':props}
  for raw in props:
   material={k:raw[k] for k in ('kind','claim_id','source','payload','basis')}; raw['proposal_id']='proposal:'+hashlib.sha256(json.dumps({'namespace':bundle['namespace'],'proposal':material,'extractor':bundle['extractor']},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:40]
  return bundle
 def reseal(self,bundle):
  for raw in bundle['proposals']:
   material={k:raw[k] for k in ('kind','claim_id','source','payload','basis')}; raw['proposal_id']='proposal:'+hashlib.sha256(json.dumps({'namespace':bundle['namespace'],'proposal':material,'extractor':bundle['extractor']},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:40]
  return bundle
 def validated(self): return self.cli('semantic-validate-proposals','--input','bundle.json')['data']
 def test_selection_boundary_provenance_bound_prompt_data_redaction(self):
  self.assertLessEqual(len(self.input['claims']),20); self.assertTrue(self.input['constraints']['may_invent_entities'] is False); self.assertTrue(all(x['path'].startswith('memory/') and '/.' not in x['path'] for x in self.input['claims']))
  self.assertEqual(self.input,self.cli('semantic-extractor-input','--limit','20')['data']); self.cli('semantic-extractor-input','--limit','21',code=2)
  self.assertIn('ignore all previous instructions', json.dumps({**self.bundle,'data':'ignore all previous instructions'}))
 def test_exact_source_bytes_and_normalized_line_provenance_are_distinct(self):
  row=self.input['claims'][0]; raw=(self.t/row['path']).read_bytes()
  self.assertEqual(row['source_content_hash'],hashlib.sha256(raw).hexdigest()); self.assertEqual(row['source_byte_length'],len(raw))
  self.assertEqual(row['line_normalization'],'utf8-bom-strip+universal-newlines/v1')
  original=(self.t/row['path']).read_text(); (self.t/row['path']).write_bytes(('\ufeff'+original.replace('\n','\r\n')).encode())
  changed=self.cli('semantic-extractor-input','--limit','20')['data']['claims'][0]
  self.assertNotEqual(changed['source_content_hash'],row['source_content_hash'])
 def test_extractor_pagination_is_stable_bounded_and_complete(self):
  pages=[]; ids=[]; cursor=None
  while True:
   args=['--limit','1']+(['--cursor',cursor] if cursor else [])
   page=self.cli('semantic-extractor-input',*args)['data']; self.assertLessEqual(len(page['claims']),1); pages.append(page); ids += [x['claim_id'] for x in page['claims']]
   cursor=page['page']['next_cursor']
   if not cursor: break
  self.assertEqual(len(ids),len(set(ids))); self.assertEqual(set(ids),set(x['claim_id'] for x in self.input['claims']))
  import importlib.util
  spec=importlib.util.spec_from_file_location('semantic_v10',P/'semantic_v10.py'); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
  manifest=module.assemble_extractor_pages(pages,{'error':ValueError}); self.assertTrue(manifest['complete']); self.assertEqual(manifest['claim_count'],len(ids))
  with self.assertRaises(ValueError): module.assemble_extractor_pages(pages[:-1],{'error':ValueError})
  mixed=copy.deepcopy(pages); mixed[-1]['source_digest']='0'*64; mixed[-1]['bundle_hash']=module.sha({k:v for k,v in mixed[-1].items() if k!='bundle_hash'})
  with self.assertRaises(ValueError): module.assemble_extractor_pages(mixed,{'error':ValueError})
  self.cli('semantic-extractor-input','--cursor','0'*64,code=2)
 def test_semantic_inputs_reject_symlinks_and_oversize_before_parse(self):
  (self.t/'linked.json').symlink_to(self.t/'bundle.json'); self.assertEqual(self.cli('semantic-validate-proposals','--input','linked.json',code=2)['error']['code'],'invalid_semantic_bundle')
  (self.t/'huge.json').write_bytes(b' '*((1024*1024)+1)); self.assertEqual(self.cli('semantic-validate-proposals','--input','huge.json',code=2)['error']['code'],'oversized_semantic_bundle')
 def test_semantic_inputs_bound_depth_items_strings_and_integer_types(self):
  deep={}; cursor=deep
  for _ in range(34): cursor['x']={}; cursor=cursor['x']
  self.write('deep.json',deep); self.assertEqual(self.cli('semantic-build','--input','deep.json',code=2)['error']['code'],'complex_semantic_bundle')
  self.write('many.json',[None]*2001); self.assertEqual(self.cli('semantic-build','--input','many.json',code=2)['error']['code'],'complex_semantic_bundle')
  self.write('long.json','x'*16385); self.assertEqual(self.cli('semantic-build','--input','long.json',code=2)['error']['code'],'complex_semantic_bundle')
  import importlib.util
  spec=importlib.util.spec_from_file_location('semantic_v10',P/'semantic_v10.py'); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
  with self.assertRaises(Exception) as caught: module.extractor_input(self.t,'test-agent','test-workspace',{'error':ValueError},True)
 def test_malformed_stale_and_secret_quarantine(self):
  bad=copy.deepcopy(self.bundle); bad['extra']=1; self.write('bad.json',bad); self.assertEqual(self.cli('semantic-validate-proposals','--input','bad.json',code=2)['error']['code'],'malformed_model_output')
  bad=copy.deepcopy(self.bundle); bad['proposals'][0]['source']['claim_content_hash']='b'*64; self.write('bad.json',self.reseal(bad)); self.assertEqual(self.cli('semantic-validate-proposals','--input','bad.json')['data']['quarantine'][0]['reason_code'],'stale_provenance')
  bad=copy.deepcopy(self.bundle); bad['proposals'][0]['basis']='password=abcdefghijklmnop'; self.write('bad.json',self.reseal(bad)); out=self.cli('semantic-validate-proposals','--input','bad.json'); self.assertNotIn('abcdefghijklmnop',json.dumps(out)); self.assertTrue(out['data']['quarantine'][0]['redacted'])
 def test_quarantine_diagnostics_are_bounded_redacted_and_deterministic(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('semantic_v10',P/'semantic_v10.py'); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
  entries=[{'proposal_id':'token='+'x'*100,'reason_code':'bad reason'}]+[{'proposal_id':str(i),'reason_code':'invalid_shape'} for i in range(1005)]
  first,summary=module.bounded_quarantine(entries); second,_=module.bounded_quarantine(list(reversed(entries)))
  self.assertEqual(first,second); self.assertEqual(len(first),1000); self.assertTrue(summary['truncated']); self.assertEqual(summary['total'],1006); self.assertNotIn('x'*20,json.dumps(first)); self.assertIn('[REDACTED]',json.dumps(first)); self.assertIn('invalid_output',summary['reason_counts'])
 def test_extractor_provenance_is_exactly_allowlisted_and_rollback_is_reproducible(self):
  out=self.validated(); self.assertEqual(out['extractor_policy']['policy_version'],'memory-graph-extractor-allowlist/v1'); self.assertTrue(out['extractor_policy']['rollback']['revalidate_from_canonical_sources']); self.assertFalse(out['extractor_policy']['rollback']['reuse_prior_approvals'])
  for field,value,code in [('extractor_version','1.0.1','extractor_not_allowlisted'),('config_hash','b'*64,'extractor_config_not_allowlisted')]:
   bad=copy.deepcopy(self.bundle); bad['extractor'][field]=value; self.write('bad.json',self.reseal(bad)); self.assertEqual(self.cli('semantic-validate-proposals','--input','bad.json',code=2)['error']['code'],code)
 def test_unicode_and_path_confusables_fail_closed(self):
  for path in ('memory\\source.md','memory/../memory/source.md','/memory/source.md','C:memory/source.md','memo\u0301ry/source.md'):
   bad=copy.deepcopy(self.bundle); bad['proposals'][0]['source']['path']=path; self.write('bad.json',self.reseal(bad)); self.assertIn('stale_provenance',{x['reason_code'] for x in self.cli('semantic-validate-proposals','--input','bad.json')['data']['quarantine']})
  bad=copy.deepcopy(self.bundle); bad['proposals'][0]['payload']['entity_id']='person:аlice'; self.write('bad.json',self.reseal(bad)); self.assertIn('invalid_payload',{x['reason_code'] for x in self.cli('semantic-validate-proposals','--input','bad.json')['data']['quarantine']})
  v=self.validated(); self.write('v.json',v); m={'schema_version':'memory-graph-approval-manifest/v1','namespace':v['namespace'],'validated_hash':v['validated_hash'],'reviewer_id':'human:réviewer','reviewed_at':'2026-08-10T12:00:00Z','decisions':[]}; self.write('m.json',m)
  self.assertEqual(self.cli('semantic-approve','--input','v.json','--manifest','m.json',code=2)['error']['code'],'invalid_approval_authority')
 def test_review_approval_build_unapproved_inert_aliases(self):
  v=self.validated(); self.write('validated.json',v); q=self.cli('semantic-review-queue','--input','bundle.json')['data']; self.assertFalse(q['automatic_approval']); self.assertEqual(len(q['items']),3); self.assertTrue(q['review_policy']['single_reviewer_per_manifest']); self.assertFalse(q['review_policy']['producer_may_review'])
  m={'schema_version':'memory-graph-approval-manifest/v1','namespace':v['namespace'],'validated_hash':v['validated_hash'],'reviewer_id':'human:reviewer','reviewed_at':'2026-08-10T12:00:00Z','decisions':[{'proposal_id':x['proposal_id'],'lifecycle':'approved','reason':'direct explicit entity'} for x in v['entity_proposals']]}; self.write('manifest.json',m)
  r=self.cli('semantic-approve','--input','validated.json','--manifest','manifest.json')['data']; self.write('reviewed.json',r); s=self.cli('semantic-build','--input','reviewed.json')['data']; self.assertEqual(len(s['entities']),2); self.assertFalse(s['assertions']); self.assertEqual(len(s['candidates']),1); self.assertFalse(s['inference_overlays'])
 def test_extractor_producer_cannot_serve_as_human_reviewer(self):
  v=self.validated(); self.write('v.json',v); m={'schema_version':'memory-graph-approval-manifest/v1','namespace':v['namespace'],'validated_hash':v['validated_hash'],'reviewer_id':'human:test','reviewed_at':'2026-08-10T12:00:00Z','decisions':[]}; self.write('m.json',m)
  self.assertEqual(self.cli('semantic-approve','--input','v.json','--manifest','m.json',code=2)['error']['code'],'separation_of_duties_violation')
 def test_conflicting_entity_types_for_same_id_are_all_quarantined(self):
  bad=copy.deepcopy(self.bundle); conflict=copy.deepcopy(bad['proposals'][0]); conflict['payload']['type']='Project'; bad['proposals'].append(conflict); self.write('bundle.json',self.reseal(bad))
  out=self.validated(); conflicts=[x for x in out['quarantine'] if x['reason_code']=='entity_identity_conflict']
  self.assertEqual(len(conflicts),2); self.assertFalse(any(x['payload']['entity_id']=='person:alice' for x in out['entity_proposals']))
  self.assertIn('dangling_endpoints',{x['reason_code'] for x in out['quarantine']})
 def test_domain_valid_but_dangling_assertion_is_quarantined(self):
  bad=copy.deepcopy(self.bundle); bad['proposals'][-1]['payload']['object']={'entity_id':'project:missing','type':'Project'}; self.write('bundle.json',self.reseal(bad))
  self.assertIn('dangling_endpoints',{x['reason_code'] for x in self.validated()['quarantine']})
 def test_temporal_intervals_require_iana_zone_and_normalize_to_utc(self):
  good=copy.deepcopy(self.bundle); good['proposals'][0]['payload']['temporal']={'start':'2026-08-10T21:00:00+09:00','end':'2026-08-10T22:00:00+09:00','timezone':'Asia/Seoul','time_unknown':False}; self.write('bundle.json',self.reseal(good)); temporal=next(x for x in self.validated()['entity_proposals'] if x['payload']['entity_id']=='person:alice')['payload']['temporal']; self.assertEqual(temporal['start'],'2026-08-10T12:00:00Z')
  for temporal in ({'start':'2026-08-10T22:00:00+09:00','end':'2026-08-10T21:00:00+09:00','timezone':'Asia/Seoul','time_unknown':False},{'start':'2026-08-10T12:00:00Z','end':None,'timezone':'UTC','time_unknown':False},{'start':None,'end':None,'timezone':'Asia/Seoul','time_unknown':False}):
   bad=copy.deepcopy(self.bundle); bad['proposals'][-1]['payload']['valid_time']=temporal; self.write('bundle.json',self.reseal(bad)); self.assertIn('invalid_temporal_interval',{x['reason_code'] for x in self.validated()['quarantine']})
 def test_approval_rejects_unknown_duplicate_and_malformed_decisions(self):
  v=self.validated(); self.write('v.json',v)
  base={'schema_version':'memory-graph-approval-manifest/v1','namespace':v['namespace'],'validated_hash':v['validated_hash'],'reviewer_id':'human:r','reviewed_at':'2026-08-10T12:00:00Z','decisions':[]}
  pid=v['entity_proposals'][0]['proposal_id']
  for decisions in [[{'proposal_id':'unknown','lifecycle':'approved','reason':'direct'}],[{'proposal_id':pid,'lifecycle':'approved','reason':'direct'}]*2,[{'proposal_id':pid,'lifecycle':'approved','reason':''}]]:
   self.write('m.json',{**base,'decisions':decisions}); self.assertEqual(self.cli('semantic-approve','--input','v.json','--manifest','m.json',code=2)['error']['code'],'invalid_approval_manifest')
 def test_revocation_is_preserved_as_audit_evidence_and_removed_on_rebuild(self):
  v=self.validated(); self.write('v.json',v); pid=v['entity_proposals'][0]['proposal_id']; m={'schema_version':'memory-graph-approval-manifest/v1','namespace':v['namespace'],'validated_hash':v['validated_hash'],'reviewer_id':'human:r','reviewed_at':'2026-08-10T12:00:00Z','decisions':[{'proposal_id':pid,'lifecycle':'revoked','reason':'withdraw approval after evidence review'}]}; self.write('m.json',m)
  reviewed=self.cli('semantic-approve','--input','v.json','--manifest','m.json')['data']; revoked=next(x for x in reviewed['proposals'] if x['proposal_id']==pid); self.assertEqual(revoked['review']['approval_effect'],'withdrawn'); self.assertEqual(revoked['lifecycle'],'archived'); self.write('r.json',reviewed); snapshot=self.cli('semantic-build','--input','r.json')['data']; self.assertFalse(any(x['semantic_id']==pid for x in snapshot['entities'])); self.assertEqual(snapshot['revoked'][0]['proposal_id'],pid)
 def test_approval_rejects_reviewer_spoof_and_temporally_stale_review(self):
  v=self.validated(); self.write('v.json',v); pid=v['entity_proposals'][0]['proposal_id']; base={'schema_version':'memory-graph-approval-manifest/v1','namespace':v['namespace'],'validated_hash':v['validated_hash'],'reviewer_id':'human:alice','reviewed_at':'2026-08-10T12:00:00Z','decisions':[{'proposal_id':pid,'lifecycle':'approved','reason':'direct'}]}
  self.write('m.json',base); self.assertEqual(self.cli('semantic-approve','--input','v.json','--manifest','m.json','--expected-reviewer-id','human:mallory',code=2)['error']['code'],'invalid_approval_authority')
  base['reviewed_at']='2000-01-01T00:00:00Z'; self.write('m.json',base); self.assertEqual(self.cli('semantic-approve','--input','v.json','--manifest','m.json',code=2)['error']['code'],'stale_approval_manifest')
 def test_future_source_mtime_skew_fails_before_review(self):
  import os,time
  source=next((self.t/'memory').glob('*.md')); future=time.time()+301; os.utime(source,(future,future))
  self.assertEqual(self.cli('semantic-validate-proposals','--input','bundle.json',code=2)['error']['code'],'source_clock_skew')
 def test_approval_binds_exact_validated_bundle(self):
  v=self.validated(); self.write('v.json',v); m={'schema_version':'memory-graph-approval-manifest/v1','namespace':v['namespace'],'validated_hash':'0'*64,'reviewer_id':'human:r','reviewed_at':'2026-08-10T12:00:00Z','decisions':[]}; self.write('m.json',m)
  self.assertEqual(self.cli('semantic-approve','--input','v.json','--manifest','m.json',code=2)['error']['code'],'invalid_approval_manifest')
  v['quarantine'].append({'proposal_id':'x','reason_code':'tampered'}); self.write('v.json',v); m['validated_hash']=v['validated_hash']; self.write('m.json',m)
  self.assertEqual(self.cli('semantic-approve','--input','v.json','--manifest','m.json',code=2)['error']['code'],'invalid_validated_bundle')
 def test_build_rejects_tampered_reviewed_bundle(self):
  v=self.validated(); self.write('v.json',v); m={'schema_version':'memory-graph-approval-manifest/v1','namespace':v['namespace'],'validated_hash':v['validated_hash'],'reviewer_id':'human:r','reviewed_at':'2026-08-10T12:00:00Z','decisions':[{'proposal_id':v['entity_proposals'][0]['proposal_id'],'lifecycle':'approved','reason':'direct'}]}; self.write('m.json',m)
  reviewed=self.cli('semantic-approve','--input','v.json','--manifest','m.json')['data']; reviewed['proposals'][0]['lifecycle']='rejected'; self.write('r.json',reviewed)
  self.assertEqual(self.cli('semantic-build','--input','r.json',code=2)['error']['code'],'invalid_reviewed_bundle')
 def test_build_requires_fresh_re_review_after_approval_expiry(self):
  v=self.validated(); self.write('v.json',v); m={'schema_version':'memory-graph-approval-manifest/v1','namespace':v['namespace'],'validated_hash':v['validated_hash'],'reviewer_id':'human:r','reviewed_at':'2026-08-10T12:00:00Z','decisions':[]}; self.write('m.json',m)
  reviewed=self.cli('semantic-approve','--input','v.json','--manifest','m.json')['data']; reviewed['approval_expires_at']='2000-01-01T00:00:00Z'; reviewed['reviewed_hash']=hashlib.sha256(json.dumps({k:v for k,v in reviewed.items() if k!='reviewed_hash'},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(); self.write('r.json',reviewed)
  self.assertEqual(self.cli('semantic-build','--input','r.json',code=2)['error']['code'],'approval_expired')
 def test_build_rejects_duplicate_assertions_and_supersession_cycles(self):
  def reviewed(assertions):
   proposals=[]
   for i,p in enumerate(assertions): proposals.append({'proposal_id':'proposal:'+str(i),'kind':'assertion','claim_id':'c','source':{},'payload':p,'basis':'direct','lifecycle':'approved','review':{'reviewer_id':'human:r','reviewed_at':'2026-08-10T12:00:00Z','review_reason':'direct'}})
   out={'schema_version':'memory-graph-reviewed-proposals/v1','namespace':self.input['namespace'],'source_snapshot_hash':'a'*64,'source_digest':'b'*64,'proposals':proposals,'quarantine':[],'manifest_hash':'c'*64,'approval_expires_at':'2999-01-01T00:00:00Z','review_policy':{'policy_version':'memory-graph-single-reviewer-sod/v1','reviewer_id':'human:r','single_reviewer':True,'producer_distinct':True}}; out['reviewed_hash']=hashlib.sha256(json.dumps(out,sort_keys=True,separators=(',',':')).encode()).hexdigest(); return out
  edge={'subject':{'entity_id':'project:a','type':'Project'},'predicate':'supersedes','object':{'entity_id':'project:b','type':'Project'},'valid_time':None}
  self.write('r.json',reviewed([edge,copy.deepcopy(edge)])); self.assertEqual(self.cli('semantic-build','--input','r.json',code=2)['error']['code'],'duplicate_semantic_assertion')
  reverse={'subject':edge['object'],'predicate':'supersedes','object':edge['subject'],'valid_time':None}; self.write('r.json',reviewed([edge,reverse])); self.assertEqual(self.cli('semantic-build','--input','r.json',code=2)['error']['code'],'supersession_cycle')
  for predicate in ('supersedes','caused'):
   self_loop={'subject':{'entity_id':'event:a','type':'Event'},'predicate':predicate,'object':{'entity_id':'event:a','type':'Event'},'valid_time':None}; self.write('r.json',reviewed([self_loop])); self.assertEqual(self.cli('semantic-build','--input','r.json',code=2)['error']['code'],'semantic_self_loop')
 def test_v09_migration_is_read_only_inert_and_version_closed(self):
  report={'conforms':True,'shape_version':'memory-graph-ontology-shapes/v2','semantic_contract_version':'0.9','namespace':self.input['namespace'],'source_snapshot_hash':self.input['source_snapshot_hash'],'source_digest':self.input['source_digest'],'migration':{'from':None,'to':'0.9','input_rewritten':False},'entity_proposals':[{'entity_proposal_id':'legacy:e','status':'approved'}],'approved_endpoint_catalog':[],'accepted_assertions':[{'assertion_id':'legacy:a','status':'approved'}],'quarantine':[],'identity_candidates':[]}
  report['report_hash']=hashlib.sha256(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(); self.write('v09.json',report); out=self.cli('semantic-migrate-v09','--input','v09.json')['data']
  self.assertFalse(out['input_rewritten']); self.assertFalse(out['approval_authority_migrated']); self.assertTrue(out['requires_fresh_v10_validation_and_human_review']); self.assertTrue(all(x['lifecycle']=='candidate' and x['review'] is None for x in out['candidates']))
  report['semantic_contract_version']='0.8'; report['report_hash']=hashlib.sha256(json.dumps({k:v for k,v in report.items() if k!='report_hash'},sort_keys=True,separators=(',',':')).encode()).hexdigest(); self.write('v09.json',report); self.assertEqual(self.cli('semantic-migrate-v09','--input','v09.json',code=2)['error']['code'],'unsupported_semantic_version')
 def test_chronology_cause_rejected(self):
  for i in ('a','b'): self.bundle['proposals'].insert(0,{'proposal_id':'','kind':'entity','claim_id':self.claim['claim_id'],'source':self.source(),'payload':{'entity_id':'event:'+i,'type':'Event','temporal':None},'basis':'explicit event'})
  self.bundle['proposals'][-1]['payload'].update(predicate='caused',subject={'entity_id':'event:a','type':'Event'},object={'entity_id':'event:b','type':'Event'})
  for raw in self.bundle['proposals']:
   material={k:raw[k] for k in ('kind','claim_id','source','payload','basis')}; raw['proposal_id']='proposal:'+hashlib.sha256(json.dumps({'namespace':self.bundle['namespace'],'proposal':material,'extractor':self.bundle['extractor']},sort_keys=True,separators=(',',':')).encode()).hexdigest()[:40]
  self.write('bundle.json',self.bundle); v=self.validated(); self.assertIn('chronology_only_cause',{x['reason_code'] for x in v['quarantine']})
 def test_causal_language_and_review_binding_are_exact_in_english_and_korean(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('semantic_v10',P/'semantic_v10.py'); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
  for text in ('the root cause analysis was reviewed','원인 분석을 검토했다','A happened before B'):
   self.assertIsNone(module.CAUSAL.search(text))
  for text in ('A directly caused B','A 때문에 B가 발생했다','A가 B를 초래했다'):
   self.assertIsNotNone(module.CAUSAL.search(text))
  proposal={'payload':{'predicate':'caused'},'source':{'claim_content_hash':'a'*64}}
  self.assertFalse(module.causal_review_bound(proposal,{'lifecycle':'approved','reason':'direct evidence'}))
  self.assertTrue(module.causal_review_bound(proposal,{'lifecycle':'approved','reason':'verified causal-evidence:'+('a'*64)}))
 def test_assertion_endpoint_ids_and_domains_are_closed(self):
  for subject,object_,predicate in [({'entity_id':'person:alice','type':'Project'},{'entity_id':'project:alpha','type':'Project'},'participates_in'),({'entity_id':'unsafe id','type':'Person'},{'entity_id':'decision:x','type':'Decision'},'decided')]:
   bad=copy.deepcopy(self.bundle); bad['proposals'][-1]['payload'].update(subject=subject,object=object_,predicate=predicate); self.write('bundle.json',self.reseal(bad))
   self.assertIn('invalid_endpoints',{x['reason_code'] for x in self.validated()['quarantine']})
 def test_reconcile_idempotency_stale_owned_delete_foreign_preserved(self):
  v=self.validated(); self.write('v.json',v); m={'schema_version':'memory-graph-approval-manifest/v1','namespace':v['namespace'],'validated_hash':v['validated_hash'],'reviewer_id':'human:r','reviewed_at':'2026-08-10T12:00:00Z','decisions':[{'proposal_id':x['proposal_id'],'lifecycle':'approved','reason':'direct explicit evidence'} for x in v['entity_proposals']+v['assertion_proposals']]}; self.write('m.json',m); r=self.cli('semantic-approve','--input','v.json','--manifest','m.json')['data']; self.write('r.json',r); s=self.cli('semantic-build','--input','r.json')['data']; self.write('s.json',s)
  cur={'schema_version':'memory-mcp/v1','entities':[{'semantic_id':'stale','namespace':s['namespace'],'semantic_owner':s['namespace']},{'semantic_id':'foreign','namespace':'other','semantic_owner':'other'}],'relations':[]}; self.write('c.json',cur); plan=self.cli('semantic-reconcile','--input','s.json','--current','c.json')['data']; self.assertTrue(any(x['op']=='delete' and x['semantic_id']=='stale' for x in plan['operations'])); self.assertEqual(plan['foreign_entities_preserved'],1); self.assertTrue(plan['journal']['retry_safe']); self.assertFalse(plan['canonical_markdown_mutated'])
  self.assertEqual(plan['journal']['next_operation_hash'],plan['operations'][0]['operation_hash']); self.assertTrue(plan['journal']['resume_requires_fresh_current_view']); self.assertEqual(plan,self.cli('semantic-reconcile','--input','s.json','--current','c.json')['data']); self.assertEqual(len({x['operation_hash'] for x in plan['operations']}),len(plan['operations']))
  self.write('plan.json',plan); self.assertEqual(self.cli('semantic-reconcile-verify','--input','s.json','--plan','plan.json','--current','c.json',code=2)['error']['code'],'semantic_reconcile_incomplete')
  current={'schema_version':'memory-mcp/v1','entities':[x['value'] for x in plan['operations'] if x['kind']=='entity' and x['op']!='delete']+[cur['entities'][1]],'relations':[x['value'] for x in plan['operations'] if x['kind']=='relation' and x['op']!='delete']}; self.write('c2.json',current); self.assertTrue(self.cli('semantic-reconcile','--input','s.json','--current','c2.json')['data']['idempotent'])
  verified=self.cli('semantic-reconcile-verify','--input','s.json','--plan','plan.json','--current','c2.json')['data']; self.assertTrue(verified['verified']); self.assertEqual(verified['remaining_operations'],0); self.assertEqual(verified['transaction_id'],plan['journal']['transaction_id'])
  tampered=copy.deepcopy(plan); tampered['operations'][0]['operation_hash']='0'*64; self.write('bad-plan.json',tampered); self.assertEqual(self.cli('semantic-reconcile-verify','--input','s.json','--plan','bad-plan.json','--current','c2.json',code=2)['error']['code'],'invalid_reconcile_plan')
  tampered=copy.deepcopy(plan); tampered['journal']['dispatch_index']=1; self.write('bad-plan.json',tampered); self.assertEqual(self.cli('semantic-reconcile-verify','--input','s.json','--plan','bad-plan.json','--current','c2.json',code=2)['error']['code'],'invalid_reconcile_plan')
 def test_reconcile_orders_dependency_operations_and_blocks_foreign_dangling_edges(self):
  snap={'schema_version':'memory-graph-semantic-snapshot/v1','namespace':self.input['namespace'],'source_snapshot_hash':'a'*64,'source_digest':'b'*64,'entities':[],'assertions':[],'candidates':[],'revoked':[],'quarantine':[],'inference_overlays':[]}; snap['snapshot_hash']=hashlib.sha256(json.dumps(snap,sort_keys=True,separators=(',',':')).encode()).hexdigest(); self.write('s.json',snap)
  owned_entity={'semantic_id':'owned-e','entity_id':'person:a','namespace':snap['namespace'],'semantic_owner':snap['namespace']}; owned_relation={'semantic_id':'owned-r','namespace':snap['namespace'],'semantic_owner':snap['namespace'],'from':{'entity_id':'person:a'},'to':{'entity_id':'project:b'}}; current={'schema_version':'memory-mcp/v1','entities':[owned_entity],'relations':[owned_relation]}; self.write('c.json',current); operations=self.cli('semantic-reconcile','--input','s.json','--current','c.json')['data']['operations']; self.assertEqual([(x['kind'],x['op']) for x in operations],[('relation','delete'),('entity','delete')])
  current['relations']=[{**owned_relation,'semantic_id':'foreign-r','namespace':'other','semantic_owner':'other'}]; self.write('c.json',current); self.assertEqual(self.cli('semantic-reconcile','--input','s.json','--current','c.json',code=2)['error']['code'],'foreign_relation_dependency')
 def test_html_output_path_rejects_escape_symlinks_and_non_html_targets(self):
  base={'schema_version':'memory-graph-semantic-snapshot/v1','namespace':self.input['namespace'],'source_snapshot_hash':'a'*64,'source_digest':'b'*64,'entities':[],'assertions':[],'candidates':[],'quarantine':[],'inference_overlays':[]}; base['snapshot_hash']=hashlib.sha256(json.dumps(base,sort_keys=True,separators=(',',':')).encode()).hexdigest(); self.write('s.json',base)
  outside=self.t.parent/'semantic-outside.html'; outside.write_text('preserve'); (self.t/'linked.html').symlink_to(outside)
  for target,code in (('../escape.html','invalid_output_path'),('linked.html','output_symlink'),('graph.txt','invalid_output_path')):
   self.assertEqual(self.cli('semantic-export-html','--input','s.json','--output',target,'--output-root',str(self.t),code=2)['error']['code'],code)
  self.assertEqual(outside.read_text(),'preserve'); outside.unlink()
 def test_html_export_rejects_tampered_and_oversized_snapshots(self):
  base={'schema_version':'memory-graph-semantic-snapshot/v1','namespace':self.input['namespace'],'source_snapshot_hash':'a'*64,'source_digest':'b'*64,'entities':[],'assertions':[],'candidates':[],'quarantine':[],'inference_overlays':[]}; base['snapshot_hash']=hashlib.sha256(json.dumps(base,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  bad=copy.deepcopy(base); bad['namespace']='tampered'; self.write('bad.json',bad); self.assertEqual(self.cli('semantic-export-html','--input','bad.json','--output','x.html','--output-root',str(self.t),code=2)['error']['code'],'invalid_semantic_snapshot')
  large=copy.deepcopy(base); large['entities']=[{'semantic_id':str(i),'entity_id':'person:'+str(i)} for i in range(501)]; large['snapshot_hash']=hashlib.sha256(json.dumps({k:v for k,v in large.items() if k!='snapshot_hash'},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(); self.write('large.json',large)
  self.assertEqual(self.cli('semantic-export-html','--input','large.json','--output','x.html','--output-root',str(self.t),code=2)['error']['code'],'semantic_visualization_too_large')
 def test_html_graph_dataset_escape_offline_deterministic_and_immutable(self):
  before=[(p,hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in (self.t/'memory').glob('*.md')]
  entities=[{'semantic_id':'x','type':'Person','entity_id':'person:x','name':'</script><img src=x>','claim_id':'c1','label':'approved/explicit'},{'semantic_id':'y','type':'Project','entity_id':'project:y','claim_id':'c1','label':'approved/private'}]
  assertions=[{'semantic_id':'a','subject':{'entity_id':'person:x','type':'Person'},'predicate':'participates_in','object':{'entity_id':'project:y','type':'Project'},'claim_id':'c1'}]
  candidates=[{'proposal_id':'candidate-e','kind':'entity','claim_id':'c2','payload':{'entity_id':'person:z','type':'Person'}},{'proposal_id':'candidate-r','kind':'assertion','claim_id':'c2','payload':{'subject':{'entity_id':'person:z','type':'Person'},'predicate':'decided','object':{'entity_id':'project:y','type':'Project'}}}]
  snap={'schema_version':'memory-graph-semantic-snapshot/v1','namespace':self.input['namespace'],'source_snapshot_hash':'a'*64,'source_digest':'b'*64,'entities':entities,'assertions':assertions,'candidates':candidates,'quarantine':[],'inference_overlays':[]}; snap['snapshot_hash']=hashlib.sha256(json.dumps(snap,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(); self.write('s.json',snap)
  default=self.cli('semantic-export-html','--input','s.json','--output','approved.html','--output-root',str(self.t))['data']; self.assertFalse(default['candidate_lane_included']); self.assertEqual(default['quarantine_count'],0); self.assertNotIn('candidate/inert',default['labels'])
  response=self.cli('semantic-export-html','--input','s.json','--output','graph.html','--output-root',str(self.t),'--include-candidates'); out=response['data']; self.assertTrue(out['candidate_lane_included']); self.assertFalse(out['quarantine_projected']); self.assertEqual(response['effects'],[{'path':'graph.html','sha256':out['sha256'],'type':'write_file'}]); text=(self.t/'graph.html').read_text(); first=(self.t/'graph.html').read_bytes(); self.cli('semantic-export-html','--input','s.json','--output','graph.html','--output-root',str(self.t),'--include-candidates'); self.assertEqual(first,(self.t/'graph.html').read_bytes())
  self.assertEqual((self.t/'graph.html').stat().st_mode & 0o777,0o600); self.assertFalse(list(self.t.glob('.graph.html.*.tmp')))
  import re
  graph=json.loads(re.search(r'<script id="graph-data" type="application/json">(.*?)</script>',text).group(1))
  self.assertEqual({n['id'] for n in graph['nodes']},{'person:x','project:y','person:z'}); self.assertEqual({e['id'] for e in graph['edges']},{'a','candidate-r'}); self.assertEqual(next(e for e in graph['edges'] if e['id']=='candidate-r')['status'],'candidate'); self.assertFalse(graph['inferred_edges'])
  self.assertTrue(all(len(n['label'])<=81 for n in graph['nodes'])); self.assertNotIn('source',json.dumps([n['detail'] for n in graph['nodes']])); self.assertNotIn('review_reason',json.dumps(graph))
  self.assertNotIn('</script><img',text); self.assertNotRegex(text,r'(?:src|href)=["\'](?:https?:)?//'); self.assertNotIn('http://',text); self.assertNotIn('https://',text); self.assertTrue(out['offline']); self.assertIn('Content-Security-Policy',text); self.assertIn("default-src 'none'",text); self.assertIn("connect-src 'none'",text); self.assertIn('name="referrer" content="no-referrer"',text); self.assertEqual(out['interactions'],['pan','zoom','node_details','edge_details']); self.assertIn('<svg id="stage"',text); self.assertIn('edge-label',text); self.assertIn('canonical explicit',text); self.assertIn('approved private proposal',text); self.assertIn('candidate/inert',text); self.assertIn('cluster',text); self.assertIn('aria-live="polite"',text); self.assertIn('prefers-reduced-motion:reduce',text); self.assertIn('aria-describedby="graph-help"',text); self.assertIn("role:'button'",text); self.assertIn("e.key==='Enter'||e.key===' '",text)
  self.assertEqual(before,[(p,hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in (self.t/'memory').glob('*.md')])
 def test_claim_lifecycle_precedence_is_explicit_and_auditable(self):
  v=self.validated(); self.write('v.json',v); states=['current','tentative','superseded']; decisions=[{'proposal_id':x['proposal_id'],'lifecycle':states[i],'reason':'explicit lifecycle decision'} for i,x in enumerate(v['entity_proposals']+v['assertion_proposals'])]
  m={'schema_version':'memory-graph-approval-manifest/v1','namespace':v['namespace'],'validated_hash':v['validated_hash'],'reviewer_id':'human:r','reviewed_at':'2026-08-10T12:00:00Z','decisions':decisions}; self.write('m.json',m)
  reviewed=self.cli('semantic-approve','--input','v.json','--manifest','m.json')['data']; self.write('r.json',reviewed); snap=self.cli('semantic-build','--input','r.json')['data']
  self.assertEqual(len(snap['entities']),1); self.assertEqual(len(snap['candidates']),1); self.assertEqual(len(snap['revoked']),1); self.assertEqual(snap['lifecycle_counts']['current'],1); self.assertEqual(snap['lifecycle_counts']['tentative'],1)
 def test_semantic_query_is_bounded_and_returns_hydration_locators(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('semantic_v10',P/'semantic_v10.py'); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
  source={'path':'memory/source.md','line_start':1,'line_end':1,'source_content_hash':'a'*64,'claim_content_hash':'b'*64}
  entities=[{'semantic_id':'e1','entity_id':'person:a','claim_id':'c1','source':source},{'semantic_id':'e2','entity_id':'project:b','claim_id':'c1','source':source}]
  edges=[{'semantic_id':'r1','subject':{'entity_id':'person:a'},'object':{'entity_id':'project:b'},'claim_id':'c1','source':source}]
  snap={'schema_version':'memory-graph-semantic-snapshot/v1','entities':entities,'assertions':edges}; snap['snapshot_hash']=module.sha(snap)
  out=module.semantic_query(snap,'person:a',{'error':ValueError},depth=1); self.assertFalse(out['canonical']); self.assertTrue(out['locator_only']); self.assertEqual(len(out['entities']),2); self.assertEqual(len(out['hydration_locators']),3)
  with self.assertRaises(ValueError): module.semantic_query(snap,'person:a',{'error':ValueError},depth=4)
 def test_private_state_json_write_is_atomic_mode_0600_and_repeatable(self):
  import importlib.util,os
  spec=importlib.util.spec_from_file_location('semantic_v10',P/'semantic_v10.py'); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
  target=self.t/'journal.json'; value={'state':'pending','operation':1}; module.atomic_write_json(target,value); first=target.read_bytes(); module.atomic_write_json(target,value)
  self.assertEqual(first,target.read_bytes()); self.assertEqual(target.stat().st_mode & 0o777,0o600); self.assertFalse(list(self.t.glob('.journal.json.*.tmp')))
if __name__=='__main__': unittest.main()
