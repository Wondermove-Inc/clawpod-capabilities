#!/usr/bin/env python3
"""Emit the closed semantic command contract inventory, without side effects."""
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CONTRACTS={
 "semantic-view":("ontology.semantic_view",()),
 "semantic-extractor-input":("semantic_v11.extractor_input",("write_private_output",)),
 "semantic-seal-extraction":("semantic_v11.seal_extraction",("write_private_output",)),
 "semantic-validate-proposals":("semantic_v11.validate_proposals",("write_private_output",)),
 "semantic-review-queue":("semantic_v11.review_queue",("write_private_output",)),
 "semantic-approve":("semantic_v11.approve",("write_private_output",)),
 "semantic-build":("semantic_v11.build_snapshot",("write_private_output",)),
 "semantic-migrate-v09":("semantic_v11.migrate_v09",()),
 "semantic-reconcile":("semantic_v11.reconcile",("write_private_output",)),
 "semantic-reconcile-verify":("semantic_v11.verify_reconcile",("write_private_output",)),
 "semantic-export-html":("semantic_v11.export_html",("write_file",)),
 "semantic-decisions-by-person":("semantic_v11.decision_lookup",()),
 "semantic-decision-why":("semantic_v11.decision_lookup",()),
 "semantic-decision-impacts":("semantic_v11.decision_lookup",()),
 "semantic-decision-evidence":("semantic_v11.decision_lookup",()),
 "semantic-hydrate":("semantic_v11.hydrate_locators",()),
}

def inventory():
 manifest=json.loads((ROOT/'harness.json').read_text())
 commands=[]
 for name in sorted(CONTRACTS):
  handler,effects=CONTRACTS[name]; spec=manifest['commands'][name]
  commands.append({
   'command':name,'handler':handler,'safety_classes':spec['safetyClasses'],
   'required_output_fields':spec['outputSchema']['required'],
   'effects':list(effects),
   'error_envelope':{'ok':False,'required':['schema_version','command','effects','error'],'secret_values_allowed':False},
   'redaction':{'secret_like_input':'reject-or-[REDACTED]','stdout_must_not_echo_secret':True},
  })
 out={'schema_version':'memory-graph-semantic-command-contracts/v1','commands':commands,
      'global_output':{'success_required':['ok','schema_version','command','effects'],'effects_default':[],'one_json_object':True}}
 out['inventory_sha256']=hashlib.sha256(json.dumps(out,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return out

if __name__=='__main__': print(json.dumps(inventory(),sort_keys=True,separators=(',',':')))
