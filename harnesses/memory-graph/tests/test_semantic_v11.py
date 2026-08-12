import importlib.util, json, shutil, subprocess, tempfile, unittest
from pathlib import Path

P=Path(__file__).resolve().parents[1]
FIX=P/'tests/fixtures/entity-proposals'

def load_module():
 spec=importlib.util.spec_from_file_location('semantic_v11_tests',P/'semantic_v11.py')
 module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
def load_driver():
 spec=importlib.util.spec_from_file_location('agent_authoring_driver_tests',P/'agent_authoring_driver.py')
 module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

class SemanticV11(unittest.TestCase):
 def setUp(self):
  self.root=Path(tempfile.mkdtemp()); shutil.copytree(FIX/'memory',self.root/'memory')
 def tearDown(self): shutil.rmtree(self.root)
 def cli(self,*args,code=0):
  run=subprocess.run([str(P/'memory_graph.py'),*args,'--root',str(self.root)],text=True,capture_output=True)
  self.assertEqual(run.returncode,code,run.stdout+run.stderr); return json.loads(run.stdout)
 def test_extractor_pages_and_seal_account_for_all_213_claim_lifecycles(self):
  # Match the real corpus total and lifecycle distribution without importing
  # private corpus text into the repository.
  evidence=[{'content_hash':'a'*64,'evidence_id':'fixture','path':'memory/.evidence/not-live.md'}]
  ordinary=[]
  for i in range(201):
   status='current' if i<140 else 'tentative' if i<144 else 'superseded' if i<199 else 'archived'
   superseded_by=['ordinary_002'] if i<2 else []
   supersedes=['ordinary_000','ordinary_001'] if i==2 else []
   claim={'claim_id':f'ordinary_{i:03}','claim_key':f'fixture.ordinary.{i:03}','evidence':evidence,'status':status,'superseded_by':superseded_by,'supersedes':supersedes,'claim':f'Ordinary natural-language claim {i}.'}
   ordinary.append('```memory-claim\n'+json.dumps(claim,separators=(',',':'))+'\n```\n')
  (self.root/'memory/ordinary.md').write_text('\n'.join(ordinary))
  pages=[]; cursor=None
  while True:
   args=['semantic-extractor-input','--agent-id','test-agent','--workspace-id','test-workspace','--limit','20']+(['--cursor',cursor] if cursor else [])
   page=self.cli(*args)['data']; pages.append(page); cursor=page['page']['next_cursor']
   if cursor is None: break
  self.assertEqual(len(pages),11); self.assertEqual(sum(len(x['claims']) for x in pages),213)
  self.assertEqual(pages[0]['corpus']['lifecycle_counts'],{'archived':2,'current':152,'superseded':55,'tentative':4})
  (self.root/'pages.json').write_text(json.dumps({'pages':pages}))
  seal=self.cli('semantic-seal-extraction','--input','pages.json','--agent-id','test-agent','--workspace-id','test-workspace')['data']
  self.assertEqual(seal['claim_count'],213); self.assertEqual(seal['eligible_claim_count'],154); self.assertEqual(seal['excluded_by_plan_conflict'],2)
  self.assertEqual(seal['lifecycle_counts'],{'archived':2,'current':152,'superseded':55,'tentative':4})
  self.assertTrue(seal['complete']); self.assertTrue(seal['fresh_source_verified']); self.assertTrue(seal['authoring_boundary']['external_agent_required']); self.assertFalse(seal['authoring_boundary']['automatic_approval'])
  tampered=json.loads(json.dumps({'pages':pages})); tampered['pages'][0]['claims'][0]['lifecycle']='tentative'; m=load_module(); tampered['pages'][0]['bundle_hash']=m.sha({k:v for k,v in tampered['pages'][0].items() if k!='bundle_hash'})
  (self.root/'tampered-pages.json').write_text(json.dumps(tampered)); error=self.cli('semantic-seal-extraction','--input','tampered-pages.json','--agent-id','test-agent','--workspace-id','test-workspace',code=2)
  self.assertEqual(error['error']['code'],'extractor_page_source_mismatch')
 def test_natural_language_external_candidates_are_useful_untrusted_and_grounded(self):
  source=self.root/'memory/entity-bootstrap.md'; text=source.read_text()
  natural=('Mina decided to ship the Memory Graph project. The decision was motivated because missing review evidence blocked release. '
   'That decision directly caused the safer launch effect, affected the Memory Graph project, and produced the release event.')
  source.write_text(text.replace('Mina is the reviewed participant in the non-live fixture.',natural))
  pages=[]; cursor=None
  while True:
   args=['semantic-extractor-input','--agent-id','test-agent','--workspace-id','test-workspace']+(['--cursor',cursor] if cursor else [])
   page=self.cli(*args)['data']; pages.append(page); cursor=page['page']['next_cursor']
   if cursor is None: break
  (self.root/'natural-pages.json').write_text(json.dumps({'pages':pages})); batch=self.cli('semantic-seal-extraction','--input','natural-pages.json','--agent-id','test-agent','--workspace-id','test-workspace')['data']
  page=pages[0]; row=next(x for p in pages for x in p['claims'] if x['claim_id']=='entity_person_mina')
  m=load_module(); extractor={'extractor_id':'agent-semantic-inference','extractor_version':'1.0.0','config_hash':m.sha(b'memory-graph-v0.10-default')}
  src={k:row[k] for k in ('path','line_start','line_end','source_content_hash','claim_content_hash')}; props=[]
  def evidence(claim,*roles):
   text=claim['claim_text']; mentions=[]; cursor=0
   for role,value in roles:
    start=text.index(value,cursor); mentions.append({'role':role,'start':start,'end':start+len(value),'text':value}); cursor=start+len(value)
   return {'mentions':mentions,'evidence_hash':m.sha({'claim_content_hash':claim['claim_content_hash'],'mentions':mentions})}
  def add(kind,payload,basis,roles,claim=row,source_record=src):
   raw={'proposal_id':'','kind':kind,'claim_id':claim['claim_id'],'source':source_record,'payload':payload,'basis':basis,'evidence':evidence(claim,*roles)}; raw['proposal_id']=m.proposal_id(page['namespace'],raw,extractor); props.append(raw)
  endpoints=[('Mina','Person'),('Memory Graph','Project'),('decision','Decision'),('missing review evidence','Cause'),('safer launch effect','Effect'),('release event','Event')]
  ids={typ:m.grounded_entity_id(typ,mention) for mention,typ in endpoints}
  for mention,typ in endpoints: add('entity',{'entity_id':ids[typ],'type':typ,'temporal':None},f'natural-language claim explicitly identifies {typ.lower()}',(('entity',mention),))
  def relation(stype,predicate,otype,subject_text,predicate_text,object_text): add('assertion',{'subject':{'entity_id':ids[stype],'type':stype},'predicate':predicate,'object':{'entity_id':ids[otype],'type':otype},'valid_time':None},'direct natural-language statement',(('subject',subject_text),('predicate',predicate_text),('object',object_text)))
  relation('Person','decided','Decision','Mina','decided','decision'); relation('Decision','motivated_by','Cause','decision','because','missing review evidence')
  relation('Decision','caused','Effect','decision','directly caused','safer launch effect'); relation('Decision','affected','Project','decision','affected','Memory Graph')
  bundle={'schema_version':m.SCHEMA_PROPOSAL,'namespace':page['namespace'],'source_snapshot_hash':page['source_snapshot_hash'],'source_digest':page['source_digest'],'extraction_batch':batch,'extractor':extractor,'proposals':props}
  (self.root/'natural.json').write_text(json.dumps(bundle)); validated=self.cli('semantic-validate-proposals','--input','natural.json','--agent-id','test-agent','--workspace-id','test-workspace')['data']
  self.assertEqual({x['payload']['type'] for x in validated['entity_proposals']},{'Person','Project','Decision','Cause','Effect','Event'})
  self.assertEqual({x['payload']['predicate'] for x in validated['assertion_proposals']},{'decided','motivated_by','caused','affected'})
  self.assertTrue(all(x['lifecycle']=='candidate' and x['review'] is None for x in validated['entity_proposals']+validated['assertion_proposals']))
  # Genuine validator-to-export boundary: consume the command's exact output,
  # including its candidate lifecycle, rather than adapting a fixture by hand.
  (self.root/'validated-natural.json').write_text(json.dumps(validated))
  exported=self.cli('semantic-export-html','--input','validated-natural.json','--output','natural.html','--output-root',str(self.root))['data']
  html=(self.root/'natural.html').read_text()
  self.assertEqual(exported['input_kind'],'validated_candidates'); self.assertEqual(exported['display_status'],'UNAPPROVED / INERT')
  self.assertNotIn(row['claim_id'],html); self.assertFalse(any(x['basis'] in html for x in validated['entity_proposals']+validated['assertion_proposals']))
  self.assertRegex(html,r'cluster-[a-f0-9]{16}')
  skipped=dict(bundle); skipped.pop('extraction_batch'); (self.root/'skipped-batch.json').write_text(json.dumps(skipped)); self.assertEqual(self.cli('semantic-validate-proposals','--input','skipped-batch.json','--agent-id','test-agent','--workspace-id','test-workspace',code=2)['error']['code'],'malformed_model_output')
  tampered=json.loads(json.dumps(bundle)); tampered['extraction_batch']['claim_count']+=1; (self.root/'tampered-batch.json').write_text(json.dumps(tampered)); self.assertEqual(self.cli('semantic-validate-proposals','--input','tampered-batch.json','--agent-id','test-agent','--workspace-id','test-workspace',code=2)['error']['code'],'invalid_extraction_batch')
  stale=json.loads(json.dumps(bundle)); stale['extraction_batch']['claim_count']+=1; stale['extraction_batch']['batch_hash']=m.sha({k:v for k,v in stale['extraction_batch'].items() if k!='batch_hash'}); (self.root/'stale-batch.json').write_text(json.dumps(stale)); self.assertEqual(self.cli('semantic-validate-proposals','--input','stale-batch.json','--agent-id','test-agent','--workspace-id','test-workspace',code=2)['error']['code'],'stale_extraction_batch')
  # An external agent cannot turn mere ordering/co-occurrence into a cause.
  add('assertion',{'subject':{'entity_id':ids['Decision'],'type':'Decision'},'predicate':'caused','object':{'entity_id':ids['Event'],'type':'Event'},'valid_time':None},'events appeared in order',(('subject','decision'),('predicate','produced'),('object','release event')))
  add('assertion',{'subject':{'entity_id':ids['Decision'],'type':'Decision'},'predicate':'affected','object':{'entity_id':ids['Event'],'type':'Event'},'valid_time':None},'plausible but unstated impact',(('subject','decision'),('predicate','produced'),('object','release event')))
  add('assertion',{'subject':{'entity_id':'person:arbitrary','type':'Person'},'predicate':'decided','object':{'entity_id':ids['Decision'],'type':'Decision'},'valid_time':None},'unrelated arbitrary endpoint ID',(('subject','Mina'),('predicate','decided'),('object','decision')))
  bundle['proposals']=props; (self.root/'unsupported.json').write_text(json.dumps(bundle)); bad=self.cli('semantic-validate-proposals','--input','unsupported.json','--agent-id','test-agent','--workspace-id','test-workspace')['data']
  self.assertIn('chronology_only_cause',{x['reason_code'] for x in bad['quarantine']})
  self.assertIn('unsupported_impact',{x['reason_code'] for x in bad['quarantine']})
  self.assertIn('invalid_grounding_evidence',{x['reason_code'] for x in bad['quarantine']})
  overlap=json.loads(json.dumps(bundle)); assertion=next(x for x in overlap['proposals'] if x['kind']=='assertion'); assertion['evidence']['mentions'][1]=dict(assertion['evidence']['mentions'][0],role='predicate'); assertion['evidence']['evidence_hash']=m.sha({'claim_content_hash':assertion['source']['claim_content_hash'],'mentions':assertion['evidence']['mentions']}); assertion['proposal_id']=m.proposal_id(overlap['namespace'],assertion,extractor)
  (self.root/'overlap.json').write_text(json.dumps(overlap)); overlap_result=self.cli('semantic-validate-proposals','--input','overlap.json','--agent-id','test-agent','--workspace-id','test-workspace')['data']
  self.assertIn('invalid_grounding_evidence',{x['reason_code'] for x in overlap_result['quarantine']})
 def test_review_queue_is_paged_at_twenty_and_cursor_sealed(self):
  module=load_module(); proposals=[{'proposal_id':f'proposal:{i:040d}','kind':'entity','claim_id':str(i),'basis':'explicit','lifecycle':'candidate'} for i in range(45)]
  validated={'namespace':'n','validated_hash':'a'*64,'entity_proposals':proposals,'assertion_proposals':[],'quarantine':[]}
  page1=module.review_queue(validated); self.assertEqual(len(page1['items']),20); self.assertEqual(page1['page']['remaining'],25)
  page2=module.review_queue(validated,cursor=page1['page']['next_cursor']); self.assertEqual(len(page2['items']),20)
  page3=module.review_queue(validated,cursor=page2['page']['next_cursor']); self.assertEqual(len(page3['items']),5); self.assertIsNone(page3['page']['next_cursor'])
  with self.assertRaises(ValueError): module.review_queue(validated,cursor='tampered')
 def test_bounded_authoring_driver_handles_english_korean_and_negative_language(self):
  m=load_module(); driver=load_driver(); extractor={'extractor_id':'agent-semantic-inference','extractor_version':'1.0.0','config_hash':m.sha(b'memory-graph-v0.10-default')}
  texts=[
   'Alice decided to deploy release because review failed. The decision was required due to policy requiring audit. The decision was used because harness.run failed validation. The decision was blocked by missing approval. The decision caused launch effect. Review delay led to launch effect. Audit failure resulted in release effect. The decision affected release event. Alice works on Atlas project. Atlas project replaces Legacy project.',
   '검증 실패 때문에 배포가 차단되었다. 변경이 영향을 주어 출시 이벤트가 지연되었다.',
   'The decision never caused release effect. The workflow status blocked release until fixed with proof. Status project replaces archived project. The decision happened before release event. Documentation lists Person Project Decision Cause Effect Event.',
   'If Alice decided to ship release, review caused launch effect. Unless Alice chose release, review affected launch event. Alice would decide release. Alice could decide release. Alice might decide release. Alice may decide release. Alice will decide release next week. The planned decision caused future effect. The proposed decision impacted future event.',
   '만약 검증 실패 때문에 배포가 차단되었다면 후보일 뿐이다. 변경이 영향을 주어 다음 주 출시 이벤트가 지연될 예정이다.',
  ]
  claims=[]
  for i,text in enumerate(texts): claims.append({'claim_id':f'c{i}','claim_text':text,'proposal_eligible':True,'path':'memory/x.md','line_start':i+1,'line_end':i+1,'source_content_hash':'a'*64,'claim_content_hash':m.sha(text)})
  page={'namespace':'n','claims':claims}; proposals,diagnostics=driver.author_with_diagnostics([page],m,extractor); assertions=[x for x in proposals if x['kind']=='assertion']
  predicates={x['payload']['predicate'] for x in assertions}; self.assertTrue({'decided','motivated_by','caused','affected','participates_in','supersedes'}<=predicates)
  self.assertGreaterEqual(sum(x['payload']['predicate']=='motivated_by' for x in assertions),2); self.assertGreaterEqual(sum(x['payload']['predicate']=='caused' for x in assertions),4)
  dotted=next(x for x in assertions if x['payload']['predicate']=='motivated_by' and x['evidence']['mentions'][2]['text'].startswith('harness.run')); self.assertEqual(dotted['evidence']['mentions'][2]['text'],'harness.run failed validation')
  self.assertTrue({'caused','affected'}<={x['payload']['predicate'] for x in assertions if x['claim_id']=='c1'}); self.assertTrue(all(x['basis'].startswith('explicit ') for x in assertions))
  self.assertGreaterEqual(diagnostics['rejected_by_reason']['negated'].get('caused',0),1); self.assertGreaterEqual(diagnostics['rejected_by_reason']['nonfactual_modality'].get('caused',0),1); self.assertGreaterEqual(diagnostics['rejected_by_reason']['status_language'].get('affected',0),1); self.assertEqual(diagnostics['claims_scanned'],5); self.assertEqual(diagnostics['eligible_claims_scanned'],5)
  for assertion in assertions:
   mentions=assertion['evidence']['mentions']; self.assertEqual([x['role'] for x in mentions],['subject','predicate','object'])
   self.assertLessEqual(mentions[0]['end'],mentions[1]['start']); self.assertLessEqual(mentions[1]['end'],mentions[2]['start'])
  negative=[x for x in assertions if x['claim_id'] in {'c2','c3','c4'}]; self.assertEqual(negative,[])
  self.assertFalse(any(x['kind']=='entity' and x['claim_id']=='c2' and x['payload']['type']=='Project' for x in proposals)); self.assertGreaterEqual(diagnostics['rejected_by_reason']['ontology_or_status_listing']['entity:Project'],1)
 def test_motivation_uses_complete_governing_sentence_and_complete_cause(self):
  m=load_module(); driver=load_driver(); extractor={'extractor_id':'agent-semantic-inference','extractor_version':'1.0.0','config_hash':m.sha(b'memory-graph-v0.10-default')}
  texts=[
   'The Workboard recommended contract is to add a narrow, versioned no-exfiltration block because they impose dependency gating and can block child claim/completion.',
   'd safely from publication was blocked safely because proof failed.',
   '-exfiltration warning was manually reviewed as false positive loses potential because review failed.',
   'narrow, versioned compatibility block because checks failed.',
   '권장 계약은 좁고 버전이 지정된 블록을 추가하는 것이다 왜냐하면 의존성 게이팅을 부과하고 하위 완료를 차단하기 때문이다.',
  ]
  claims=[]
  for i,text in enumerate(texts): claims.append({'claim_id':f'g{i}','claim_text':text,'proposal_eligible':True,'path':'memory/x.md','line_start':i+1,'line_end':i+1,'source_content_hash':'a'*64,'claim_content_hash':m.sha(text)})
  proposals,diagnostics=driver.author_with_diagnostics([{'namespace':'n','claims':claims}],m,extractor); assertions=[x for x in proposals if x['kind']=='assertion' and x['payload']['predicate']=='motivated_by']
  self.assertEqual({x['claim_id'] for x in assertions},{'g0','g4'})
  english=next(x for x in assertions if x['claim_id']=='g0'); self.assertEqual(english['evidence']['mentions'][0]['text'],'The Workboard recommended contract is to add a narrow, versioned no-exfiltration block'); self.assertEqual(english['evidence']['mentions'][2]['text'],'they impose dependency gating and can block child claim/completion')
  korean=next(x for x in assertions if x['claim_id']=='g4'); self.assertTrue(korean['evidence']['mentions'][0]['text'].startswith('권장 계약은')); self.assertIn('의존성 게이팅',korean['evidence']['mentions'][2]['text'])
  self.assertEqual(diagnostics['rejected_by_reason']['fragmentary_decision_subject']['motivated_by'],3)
 def test_completed_policy_actions_scope_embedded_modality(self):
  m=load_module(); driver=load_driver(); extractor={'extractor_id':'agent-semantic-inference','extractor_version':'1.0.0','config_hash':m.sha(b'memory-graph-v0.10-default')}
  texts=[
   'Jang Jaewon updated the rule so public rumors may be included because the section is explicitly for rumors.',
   'Jang Jaewon decided that after installing the planned skill/harness, agents must prefer shared storage.',
   'Jang Jaewon explicitly stopped Memory Graph v0.6 Plugin migration because the path was too costly and complex.',
   'Jang Jaewon may update the rule because the section is for rumors.',
   'Jang Jaewon might stop Plugin migration because the path is costly.',
   'Jang Jaewon planned to adopt the shared-storage policy.',
   'Jang Jaewon updated the rule because the section might be for rumors.',
   '장재원은 채택했다 공유 저장소 정책을.',
   '장재원은 채택할 수도 있다 공유 저장소 정책을.',
  ]
  claims=[{'claim_id':f'p{i}','claim_text':text,'proposal_eligible':True,'path':'memory/x.md','line_start':i+1,'line_end':i+1,'source_content_hash':'a'*64,'claim_content_hash':m.sha(text)} for i,text in enumerate(texts)]
  proposals,diagnostics=driver.author_with_diagnostics([{'namespace':'n','claims':claims}],m,extractor)
  assertions=[x for x in proposals if x['kind']=='assertion']
  self.assertEqual(sorted((x['claim_id'],x['payload']['predicate']) for x in assertions if x['claim_id'] in {'p0','p1','p2'}),[('p0','decided'),('p0','motivated_by'),('p1','decided'),('p2','decided'),('p2','motivated_by')])
  self.assertFalse(any(x['claim_id'] in {'p3','p4','p5'} for x in assertions))
  self.assertFalse(any(x['claim_id']=='p6' and x['payload']['predicate']=='motivated_by' for x in assertions))
  self.assertTrue(any(x['claim_id']=='p7' and x['payload']['predicate']=='decided' for x in assertions)); self.assertFalse(any(x['claim_id']=='p8' for x in assertions))
  for assertion in assertions:
   mentions=assertion['evidence']['mentions']; self.assertLessEqual(mentions[0]['end'],mentions[1]['start']); self.assertLessEqual(mentions[1]['end'],mentions[2]['start'])
  stopped=next(x for x in assertions if x['claim_id']=='p2' and x['payload']['predicate']=='motivated_by')
  self.assertEqual(stopped['evidence']['mentions'][0]['text'],'Jang Jaewon explicitly stopped Memory Graph v0.6 Plugin migration')
  self.assertEqual(stopped['evidence']['mentions'][2]['text'],'the path was too costly and complex')
  self.assertGreaterEqual(diagnostics['rejected_by_reason']['nonfactual_modality']['motivated_by'],1)
 def test_stopped_plugin_paraphrase_duplicate_keeps_richer_rationale_and_distinct_stop(self):
  m=load_module(); driver=load_driver(); extractor={'extractor_id':'agent-semantic-inference','extractor_version':'1.0.0','config_hash':m.sha(b'memory-graph-v0.10-default')}
  texts=[
   'Jang Jaewon explicitly stopped the Memory Graph v0.6 Plugin migration and dependent registry work because the Plugin path was too costly and complex.',
   'Jang Jaewon stopped the v0.6 Plugin direction.',
   'Jang Jaewon stopped the v0.6 Plugin deployment.',
   'Jang Jaewon stopped the Atlas v0.6 Plugin migration.',
  ]
  claims=[{'claim_id':f'd{i}','claim_text':text,'proposal_eligible':True,'path':'memory/x.md','line_start':i+1,'line_end':i+1,'source_content_hash':'a'*64,'claim_content_hash':m.sha(text)} for i,text in enumerate(texts)]
  proposals,diagnostics=driver.author_with_diagnostics([{'namespace':'n','claims':claims}],m,extractor)
  assertions=[x for x in proposals if x['kind']=='assertion']
  self.assertEqual(sorted((x['claim_id'],x['payload']['predicate']) for x in assertions),[('d0','decided'),('d0','motivated_by'),('d2','decided'),('d3','decided')])
  self.assertEqual(diagnostics['rejected_by_reason']['semantic_duplicate_decision']['decided'],1)
  self.assertFalse(any(x['claim_id']=='d1' for x in proposals))
  retained=next(x for x in assertions if x['claim_id']=='d0' and x['payload']['predicate']=='decided'); self.assertIn('dependent registry work',retained['evidence']['mentions'][2]['text'])
 def test_actor_bound_present_policy_actions_and_korean_sov_are_factual_only(self):
  m=load_module(); driver=load_driver(); extractor={'extractor_id':'agent-semantic-inference','extractor_version':'1.0.0','config_hash':m.sha(b'memory-graph-v0.10-default')}
  texts=[
   'Jang Jaewon prohibits long-running Gateway executions.',
   'Jang Jaewon requires short and bounded Gateway calls.',
   '장재원은 연결된 Harness도 설치하고 검증할 것을 요구한다.',
   'If Jang Jaewon prohibits long-running Gateway executions, this is conditional.',
   'Jang Jaewon might require short Gateway calls.',
   'Jang Jaewon reportedly prohibits long-running Gateway executions.',
   'The report says Jang Jaewon requires short Gateway calls.',
   'The document quotes “Jang Jaewon prohibits long-running Gateway executions.”',
   "The note contains 'Jang Jaewon requires short Gateway calls.'",
   'Jang Jaewon recommends prohibiting long-running Gateway executions.',
   '만약 장재원은 연결된 Harness 설치를 요구한다.',
   '장재원은 연결된 Harness 설치를 요구할 수도 있다.',
   '장재원은 clawpod-capability-registry Skill/Harness 설치 시 에이전트의 기존 WORKFLOW.md를 절대 덮어쓰지 않고, 레지스트리 우선 검색 정책을 관리 블록으로 추가하거나 해당 블록만 갱신하도록 요구한다.',
   'Jang Jaewon requires immediate post-install onboarding that interviews the human about desired providers/models and obtains the corresponding API credentials through protected secret capture, then configures and verifies each provider.',
   'Jang Jaewon requires '+('x'*257)+'.',
   'Jang Jaewon requires WORKFLOW.md. Jang Jaewon might require a later policy.',
  ]
  claims=[{'claim_id':f't{i}','claim_text':text,'proposal_eligible':True,'path':'memory/x.md','line_start':i+1,'line_end':i+1,'source_content_hash':'a'*64,'claim_content_hash':m.sha(text)} for i,text in enumerate(texts)]
  proposals,diagnostics=driver.author_with_diagnostics([{'namespace':'n','claims':claims}],m,extractor); assertions=[x for x in proposals if x['kind']=='assertion']
  self.assertEqual({x['claim_id'] for x in assertions},{'t0','t1','t2','t12','t13','t15'})
  korean=next(x for x in assertions if x['claim_id']=='t2'); mentions=korean['evidence']['mentions']; self.assertEqual([x['role'] for x in mentions],['subject','predicate','object']); self.assertLessEqual(mentions[0]['end'],mentions[2]['start']); self.assertLessEqual(mentions[2]['end'],mentions[1]['start'])
  self.assertGreaterEqual(diagnostics['rejected_by_reason']['nonfactual_modality']['decided'],2); self.assertGreaterEqual(diagnostics['rejected_by_reason']['reporting_or_quoted_policy']['decided'],2)
  dotted=next(x for x in assertions if x['claim_id']=='t12'); self.assertIn('WORKFLOW.md',dotted['evidence']['mentions'][2]['text'])
  long_policy=next(x for x in assertions if x['claim_id']=='t13'); self.assertGreater(len(long_policy['evidence']['mentions'][2]['text']),180)
  sentence=next(x for x in assertions if x['claim_id']=='t15'); self.assertEqual(sentence['evidence']['mentions'][2]['text'],'WORKFLOW.md'); self.assertNotIn('later policy',sentence['evidence']['mentions'][2]['text'])
 def test_snapshot_rejects_approved_assertion_when_endpoint_entity_is_not_approved(self):
  m=load_module(); now=__import__('datetime').datetime.now(__import__('datetime').timezone.utc); source={}
  entity=lambda pid,eid,typ,state:{'proposal_id':pid,'kind':'entity','claim_id':'c','source':source,'payload':{'entity_id':eid,'type':typ,'temporal':None},'basis':'grounded','evidence':{},'lifecycle':state,'review':{}}
  relation={'proposal_id':'a','kind':'assertion','claim_id':'c','source':source,'payload':{'subject':{'entity_id':'person:mina','type':'Person'},'predicate':'decided','object':{'entity_id':'decision:ship','type':'Decision'},'valid_time':None},'basis':'grounded','evidence':{},'lifecycle':'current','review':{}}
  reviewed={'schema_version':'memory-graph-reviewed-proposals/v1','namespace':'n','source_snapshot_hash':'a'*64,'source_digest':'b'*64,'extraction_batch_hash':'c'*64,'proposals':[entity('e1','person:mina','Person','current'),entity('e2','decision:ship','Decision','rejected'),relation],'quarantine':[],'manifest_hash':'d'*64,'approval_expires_at':(now+__import__('datetime').timedelta(hours=1)).isoformat().replace('+00:00','Z'),'review_policy':{}}
  reviewed['reviewed_hash']=m.sha(reviewed)
  with self.assertRaises(ValueError): m.build_snapshot(reviewed,{'error':ValueError})
 def test_reconcile_and_decision_query_reject_rehashed_dangling_snapshot(self):
  m=load_module(); entity={'semantic_id':'e1','entity_id':'person:mina','type':'Person'}
  edge={'semantic_id':'a1','subject':{'entity_id':'person:mina','type':'Person'},'predicate':'decided','object':{'entity_id':'decision:missing','type':'Decision'}}
  snapshot={'schema_version':m.SCHEMA_SNAPSHOT,'namespace':'n','entities':[entity],'assertions':[edge]}; snapshot['snapshot_hash']=m.sha(snapshot)
  with self.assertRaises(ValueError): m.reconcile(snapshot,{'schema_version':'memory-mcp/v1','entities':[],'relations':[]},{'error':ValueError})
  with self.assertRaises(ValueError): m.decision_lookup(snapshot,'by-person',{'error':ValueError},person_id='person:mina')
 def test_first_class_decision_queries_are_approved_only_and_locator_only(self):
  m=load_module(); source={'path':'memory/x.md','line_start':1,'line_end':1,'source_content_hash':'a'*64,'claim_content_hash':'b'*64}
  review={'reviewer_id':'human:r','review_reason':'SENSITIVE_DECISION_REVIEW'}
  def entity(sid,eid,typ): return {'semantic_id':sid,'namespace':'n','claim_id':sid,'source':source,'review':review,'label':'approved/private','entity_id':eid,'type':typ,'temporal':None}
  entities=[entity('e1','person:mina','Person'),entity('e2','decision:ship','Decision'),entity('e3','cause:review','Cause'),entity('e4','effect:release','Effect'),entity('e5','project:graph','Project')]
  def edge(sid,sub,st,pred,obj,ot): return {'semantic_id':sid,'namespace':'n','claim_id':sid,'source':source,'review':review,'label':'approved/private','subject':{'entity_id':sub,'type':st},'predicate':pred,'object':{'entity_id':obj,'type':ot},'valid_time':None}
  assertions=[edge('a1','person:mina','Person','decided','decision:ship','Decision'),edge('a2','decision:ship','Decision','motivated_by','cause:review','Cause'),edge('a3','decision:ship','Decision','caused','effect:release','Effect'),edge('a4','decision:ship','Decision','affected','project:graph','Project')]
  snapshot={'schema_version':m.SCHEMA_SNAPSHOT,'namespace':'n','source_snapshot_hash':'a'*64,'source_digest':'b'*64,'entities':entities,'assertions':assertions,'candidates':[],'revoked':[],'lifecycle_counts':{},'entity_rename_policy':{},'quarantine':[],'inference_overlays':[]}; snapshot['snapshot_hash']=m.sha(snapshot)
  api={'error':ValueError}
  by=m.decision_lookup(snapshot,'by-person',api,person_id='person:mina'); self.assertEqual([x['entity_id'] for x in by['entities']],['decision:ship'])
  why=m.decision_lookup(snapshot,'why',api,decision_id='decision:ship'); self.assertEqual([x['entity_id'] for x in why['entities']],['cause:review'])
  impacts=m.decision_lookup(snapshot,'impacts',api,decision_id='decision:ship'); self.assertEqual({x['type'] for x in impacts['entities']},{'Effect','Project'})
  evidence=m.decision_lookup(snapshot,'evidence',api,decision_id='decision:ship'); self.assertTrue(evidence['locator_only']); self.assertTrue(evidence['hydration_locators'])
  for result in (by,why,impacts,evidence):
   self.assertTrue(all(set(x)<={'semantic_id','entity_id','type'} for x in result['entities']))
   self.assertTrue(all(set(x)=={'semantic_id','subject','predicate','object'} for x in result['assertions']))
   self.assertTrue(all(set(x['subject'])=={'entity_id','type'} and set(x['object'])=={'entity_id','type'} for x in result['assertions']))
   serialized=json.dumps(result['entities']+result['assertions'],sort_keys=True); self.assertNotIn('SENSITIVE_DECISION_REVIEW',serialized); self.assertNotIn('memory/x.md',serialized)
 def test_actual_corpus_aggregate_evidence_is_reproducible_when_present(self):
  corpus=Path('/workspace/memory'); artifact=P.parents[1]/'artifacts/memory-graph-v0.11-real-corpus-smoke.json'
  if not corpus.is_dir(): self.skipTest('direct private corpus is unavailable')
  run=subprocess.run(['python3',str(P/'real_corpus_smoke.py'),'--root','/workspace'],text=True,capture_output=True)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  actual=json.loads(run.stdout); expected=json.loads(artifact.read_text())
  if actual.get('source_digest')!=expected.get('source_digest'): self.skipTest('private corpus has changed since the sealed release artifact')
  self.assertEqual(actual,expected); self.assertFalse(actual['contains_claim_text']); self.assertTrue(actual['human_review_required']); self.assertFalse(actual['automatic_approval'])
  self.assertEqual((actual['claim_count'],actual['eligible_claim_count'],actual['excluded_by_plan_conflict']),(213,154,2))
  self.assertEqual(actual['authoring_diagnostics']['eligible_claims_scanned'],154); self.assertTrue({'decided','motivated_by','caused'}<=set(actual['predicates']))
  self.assertEqual(actual['authoring_diagnostics']['zero_predicates'],['affected','participates_in','supersedes']); self.assertGreater(actual['authoring_diagnostics']['rejected_by_reason']['status_language']['affected'],0)
  self.assertEqual(len(actual['authoring_diagnostics']['accepted_assertion_summaries']),actual['accepted_assertion_count'])
  motivated=[x for x in actual['authoring_diagnostics']['accepted_assertion_summaries'] if x['predicate']=='motivated_by']; self.assertTrue(all(x['subject_chars']>=40 and x['object_proposition_verified'] for x in motivated)); self.assertIn('recommendation',{x['subject_proposition_kind'] for x in motivated})

if __name__=='__main__': unittest.main()
