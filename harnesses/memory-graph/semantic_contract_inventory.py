#!/usr/bin/env python3
"""Emit the closed semantic command contract inventory, without side effects."""
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CONTRACTS={
 "semantic-view":("ontology.semantic_view",False),
 "semantic-extractor-input":("semantic_v10.extractor_input",False),
 "semantic-validate-proposals":("semantic_v10.validate_proposals",False),
 "semantic-review-queue":("semantic_v10.review_queue",False),
 "semantic-approve":("semantic_v10.approve",False),
 "semantic-build":("semantic_v10.build_snapshot",False),
 "semantic-migrate-v09":("semantic_v10.migrate_v09",False),
 "semantic-reconcile":("semantic_v10.reconcile",False),
 "semantic-reconcile-verify":("semantic_v10.verify_reconcile",False),
 "semantic-export-html":("semantic_v10.export_html",True),
}

def inventory():
 manifest=json.loads((ROOT/'harness.json').read_text())
 commands=[]
 for name in sorted(CONTRACTS):
  handler,writes=CONTRACTS[name]; spec=manifest['commands'][name]
  commands.append({
   'command':name,'handler':handler,'safety_classes':spec['safetyClasses'],
   'required_output_fields':spec['outputSchema']['required'],
   'effects':(['write_file'] if writes else []),
   'error_envelope':{'ok':False,'required':['schema_version','command','effects','error'],'secret_values_allowed':False},
   'redaction':{'secret_like_input':'reject-or-[REDACTED]','stdout_must_not_echo_secret':True},
  })
 out={'schema_version':'memory-graph-semantic-command-contracts/v1','commands':commands,
      'global_output':{'success_required':['ok','schema_version','command','effects'],'effects_default':[],'one_json_object':True}}
 out['inventory_sha256']=hashlib.sha256(json.dumps(out,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return out

if __name__=='__main__': print(json.dumps(inventory(),sort_keys=True,separators=(',',':')))
