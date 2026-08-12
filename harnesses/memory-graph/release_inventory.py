#!/usr/bin/env python3
"""Emit the deterministic local release inventory. No install or mutation."""
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FILES=("README.md","capability.json","harness.json","memory_graph.py","ontology.py","semantic_v10.py","semantic_v11.py","agent_authoring_driver.py","real_corpus_smoke.py","semantic_contract_inventory.py","release_inventory.py","tests/TEST.md","tests/test_interactive_export.py","tests/test_interactive_export_browser.py","tests/test_semantic_contract_inventory.py","tests/test_semantic_v10.py","tests/test_semantic_v11.py")
items=[]
for name in FILES:
 data=(ROOT/name).read_bytes()
 items.append({"path":name,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
out={"schema_version":"memory-graph-release-inventory/v1","version":json.loads((ROOT/"capability.json").read_text())["version"],"files":items,"update":"replace only after validating every listed digest","rollback":"restore the prior complete inventory; never mix versions"}
out["inventory_sha256"]=hashlib.sha256(json.dumps(out,sort_keys=True,separators=(",",":")).encode()).hexdigest()
print(json.dumps(out,sort_keys=True,separators=(",",":")))
