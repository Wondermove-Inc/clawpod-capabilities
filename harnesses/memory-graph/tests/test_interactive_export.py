import copy
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("semantic_export_v11", ROOT / "semantic_v11.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
API = {"error": ValueError}


class InteractiveExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def source(self):
        return {"path": "memory/topic.md", "line_start": 2, "line_end": 3,
                "source_content_hash": "a" * 64, "claim_content_hash": "b" * 64}

    def validated(self):
        entities = []
        for i, typ in enumerate(("Person", "Project", "Decision", "Cause", "Effect", "Event")):
            entities.append({"proposal_id": f"p-e-{i}", "kind": "entity", "claim_id": "claim-safe",
                             "source": self.source(), "payload": {"entity_id": f"{typ.lower()}:{i}", "type": typ},
                             "basis": "private rationale for entity", "lifecycle": "candidate"})
        assertions = [{"proposal_id": "p-a", "kind": "assertion", "claim_id": "claim-safe",
                       "source": self.source(), "payload": {"subject": {"entity_id": "decision:2", "type": "Decision"},
                       "predicate": "motivated_by", "object": {"entity_id": "cause:3", "type": "Cause"}},
                       "basis": "private rationale for assertion", "lifecycle": "candidate"}]
        value = {"schema_version": "memory-graph-validated-proposals/v1", "namespace": "n",
                 "entity_proposals": entities, "assertion_proposals": assertions, "quarantine": []}
        value["validated_hash"] = M.sha(value)
        return value

    def snapshot(self):
        source = self.source()
        entities = [{"semantic_id": f"e{i}", "entity_id": f"{typ.lower()}:{i}", "type": typ,
                     "claim_id": "approved-claim", "source": source, "label": "approved/private"}
                    for i, typ in enumerate(("Person", "Project", "Decision", "Cause", "Effect", "Event"))]
        assertions = [{"semantic_id": "a1", "subject": {"entity_id": "decision:2", "type": "Decision"},
                       "predicate": "caused", "object": {"entity_id": "effect:4", "type": "Effect"},
                       "claim_id": "approved-claim", "source": source, "label": "approved/private"}]
        value = {"schema_version": M.SCHEMA_SNAPSHOT, "namespace": "n", "entities": entities,
                 "assertions": assertions, "candidates": [], "quarantine": []}
        value["snapshot_hash"] = M.sha(value)
        return value

    def test_inert_and_approved_are_truthful_offline_interactive_and_deterministic(self):
        for bundle, status in ((self.validated(), "UNAPPROVED / INERT"), (self.snapshot(), "APPROVED")):
            first = self.out / ("inert.html" if status.startswith("UN") else "approved.html")
            second = self.out / ("inert-2.html" if status.startswith("UN") else "approved-2.html")
            one = M.export_html(bundle, first, API)
            two = M.export_html(copy.deepcopy(bundle), second, API)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(one["sha256"], two["sha256"])
            text = first.read_text()
            self.assertIn(status, text)
            self.assertIn('<svg id="stage"', text)
            self.assertIn('marker-end', text)
            for control in ("search", "entity-filter", "relation-filter", "claim-filter", "status-filter"):
                self.assertIn(f'id="{control}"', text)
            for typ in ("Person", "Project", "Decision", "Cause", "Effect", "Event"):
                self.assertIn(f'.{typ}', text)
            self.assertIn("nodeDrag", text)
            self.assertIn("onwheel", text)
            self.assertIn("provenance", text)
            self.assertNotIn("private rationale", text)
            self.assertNotIn("claim-safe", text)
            self.assertNotIn("approved-claim", text)
            self.assertRegex(text, r'cluster-[a-f0-9]{16}')
            self.assertIn("p.onkeydown", text)
            self.assertIn("g.onkeydown", text)
            self.assertIn("updateNode(n.id)", text)
            self.assertNotIn("updateNode(n.id);draw()", text)
            self.assertNotRegex(text, r'(?:https?:)?//')
            self.assertNotRegex(text, r'<(?:script|link|img)[^>]+(?:src|href)=')
            self.assertEqual(one["network_requests"], 0)

    def test_dangling_endpoints_lifecycle_mislabeling_and_secret_redaction(self):
        dangling = self.validated()
        dangling["assertion_proposals"][0]["payload"]["object"]["entity_id"] = "cause:missing"
        dangling["validated_hash"] = M.sha({k: v for k, v in dangling.items() if k != "validated_hash"})
        with self.assertRaises(ValueError):
            M.export_html(dangling, self.out / "dangling.html", API)
        mislabeled = self.snapshot()
        mislabeled["entities"][0]["label"] = "candidate/inert"
        mislabeled["snapshot_hash"] = M.sha({k: v for k, v in mislabeled.items() if k != "snapshot_hash"})
        with self.assertRaises(ValueError):
            M.export_html(mislabeled, self.out / "mislabel.html", API)
        secret = self.validated()
        secret["entity_proposals"][0]["basis"] = "api_key=abcdefghijklmnop"
        secret["entity_proposals"][0]["source"]["path"] = "memory/api_key=abcdefghijklmnop.md"
        secret["validated_hash"] = M.sha({k: v for k, v in secret.items() if k != "validated_hash"})
        M.export_html(secret, self.out / "redacted.html", API)
        text = (self.out / "redacted.html").read_text()
        self.assertIn("[REDACTED]", text)
        self.assertNotIn("abcdefghijklmnop", text)

    def test_candidate_collections_require_arrays_before_combining(self):
        for field in ("entity_proposals", "assertion_proposals"):
            for invalid in (None, {}):
                bundle = self.validated()
                bundle[field] = invalid
                bundle["validated_hash"] = M.sha({k: v for k, v in bundle.items() if k != "validated_hash"})
                with self.assertRaises(ValueError):
                    M.export_html(bundle, self.out / f"invalid-{field}.html", API)

    def test_gateway_manifest_keeps_canonical_typed_contract(self):
        manifest = json.loads((ROOT / "harness.json").read_text())
        command = manifest["commands"]["semantic-export-html"]
        self.assertEqual(command["safetyClasses"], ["writeSafe"])
        self.assertEqual(set(command["inputSchema"]["required"]), {"input", "output", "outputRoot"})
        self.assertFalse(command["inputSchema"]["additionalProperties"])
        self.assertEqual([x["flag"] for x in command["argMap"][:3]], ["--input", "--output", "--output-root"])


if __name__ == "__main__":
    unittest.main()
