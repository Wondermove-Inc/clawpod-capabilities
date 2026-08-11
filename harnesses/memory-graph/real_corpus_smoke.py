#!/usr/bin/env python3
"""Reproduce sanitized metrics for bounded external-agent-style authoring."""
import argparse, importlib.util, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
core=load("memory_graph_real_smoke_core",HERE/"memory_graph.py")
semantic=load("memory_graph_real_smoke_semantic",HERE/"semantic_v11.py")
driver=load("memory_graph_agent_authoring_driver",HERE/"agent_authoring_driver.py")

def metrics(root):
 api={"error":core.InputError,"inspect":core.inspect_workspace,"namespace":core.namespace_for,"plan":core.build_plan}
 pages=[]; cursor=None
 while True:
  page=semantic.extractor_input(root,"verification-agent","workspace",api,20,cursor); pages.append(page); cursor=page["page"]["next_cursor"]
  if cursor is None: break
 batch=semantic.seal_extraction({"pages":pages},api,root,"verification-agent","workspace")
 extractor={"extractor_id":"agent-semantic-inference","extractor_version":"1.0.0","config_hash":semantic.sha(b"memory-graph-v0.10-default")}
 proposals,authoring_diagnostics=driver.author_with_diagnostics(pages,semantic,extractor)
 bundle={"schema_version":semantic.SCHEMA_PROPOSAL,"namespace":pages[0]["namespace"],"source_snapshot_hash":pages[0]["source_snapshot_hash"],"source_digest":pages[0]["source_digest"],"extraction_batch":batch,"extractor":extractor,"proposals":proposals}
 validated=semantic.validate_proposals(root,bundle,"verification-agent","workspace",api)
 return {"schema_version":"memory-graph-real-corpus-smoke/v3","authoring_process":"bounded-page-natural-language-driver/v2","fixed_claim_ids":False,"fixed_offsets":False,"source_digest":batch["source_digest"],"batch_hash":batch["batch_hash"],"claim_count":batch["claim_count"],"eligible_claim_count":batch["eligible_claim_count"],"excluded_by_plan_conflict":batch["excluded_by_plan_conflict"],"lifecycle_counts":batch["lifecycle_counts"],"page_count":len(pages),"page_sizes":[len(x["claims"]) for x in pages],"proposal_count":len(proposals),"accepted_entity_count":len(validated["entity_proposals"]),"accepted_assertion_count":len(validated["assertion_proposals"]),"entity_types":sorted({x["payload"]["type"] for x in validated["entity_proposals"]}),"predicates":sorted({x["payload"]["predicate"] for x in validated["assertion_proposals"]}),"authoring_diagnostics":authoring_diagnostics,"quarantine_count":validated["quarantine_diagnostics"]["total"],"automatic_approval":False,"human_review_required":True,"contains_claim_text":False}

if __name__=="__main__":
 parser=argparse.ArgumentParser(); parser.add_argument("--root",required=True); args=parser.parse_args()
 print(json.dumps(metrics(Path(args.root).resolve()),sort_keys=True,separators=(",",":")))
