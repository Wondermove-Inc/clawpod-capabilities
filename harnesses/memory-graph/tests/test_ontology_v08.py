import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
CLI = PACKAGE / "memory_graph.py"
FIXTURE = Path(__file__).parent / "fixtures/ontology"

spec = importlib.util.spec_from_file_location("ontology_v08", PACKAGE / "ontology.py")
ontology = importlib.util.module_from_spec(spec); spec.loader.exec_module(ontology)


class OntologyV08Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()); shutil.copytree(FIXTURE / "memory", self.tmp / "memory")
        self.bundle = self.make_bundle(); self.save()

    def tearDown(self): shutil.rmtree(self.tmp)

    def cli(self, command, expected=0, extra=()):
        proc = subprocess.run([str(CLI), command, "--root", str(self.tmp), "--input", "bundle.json",
            "--agent-id", "test-agent", "--workspace-id", "test-workspace", *extra], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr); self.assertEqual(proc.stderr, "")
        return json.loads(proc.stdout)

    def plan(self):
        proc = subprocess.run([str(CLI), "plan", "--root", str(self.tmp), "--agent-id", "test-agent", "--workspace-id", "test-workspace", "--detail"], cwd=ROOT, text=True, capture_output=True, check=True)
        return json.loads(proc.stdout)["data"]

    def make_bundle(self):
        plan = self.plan(); claim = plan["claims"][0]
        source_path = self.tmp / claim["path"]; source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest(); evidence_hash = "a" * 64
        intents = json.loads((FIXTURE / "assertion-intents.json").read_text())
        assertions = []
        for subject, stype, predicate, obj, otype, method in intents:
            review = {"reviewer_id":"human:test","reviewed_at":"2026-08-10T00:00:00Z","review_reason":"direct_causal_statement"} if method == "human_approved" else None
            item = {"assertion_id":"", "subject":{"entity_id":subject,"type":stype}, "predicate":predicate,
                "object":{"entity_id":obj,"type":otype}, "source_claim_id":claim["claim_id"],
                "source":{"path":claim["path"],"line_start":claim["line"],"line_end":claim["line"],"source_content_hash":source_hash,"claim_content_hash":claim["content_hash"],"evidence_excerpt_hash":evidence_hash},
                "method":method,"asserted_at":"2026-08-10T00:00:00Z",
                "valid_time":{"start":"2026-01-01T00:00:00+09:00","end":None,"precision":"day","timezone":"Asia/Seoul"},
                "status":"approved","review":review,"extractor":None,"confidence":None}
            item["assertion_id"] = ontology.assertion_id(plan["ownership"]["namespace"], item); assertions.append(item)
        return {"schema_version":ontology.ASSERTION_SCHEMA_VERSION,"semantic_contract_version":"0.8","namespace":plan["ownership"]["namespace"],"source_snapshot_hash":plan["snapshot_hash"],"source_digest":plan["source_digest"],"assertions":assertions,"identity_candidates":[]}

    def save(self): (self.tmp / "bundle.json").write_text(json.dumps(self.bundle, sort_keys=True, separators=(",", ":")))

    def test_success_cq_and_semantic_first_view(self):
        validated = self.cli("ontology-validate")["data"]
        self.assertTrue(validated["conforms"]); self.assertEqual(len(validated["accepted_assertions"]), 12)
        cq = self.cli("cq-evaluate")["data"]; self.assertTrue(cq["passed"]); self.assertEqual(cq["metrics"]["cq_pass_count"], 5)
        view = self.cli("semantic-view")["data"]; self.assertEqual(len(view["approved_assertions"]), 12)
        self.assertFalse(view["structural_relations"]); self.assertTrue(all(x["label"] == "Approved explicit" and x["rehydration_required"] for x in view["approved_assertions"]))

    def test_malformed_and_secret_like_rejection_without_echo(self):
        (self.tmp / "bundle.json").write_text("{bad")
        malformed = self.cli("ontology-validate", 2); self.assertEqual(malformed["error"]["code"], "malformed_bundle")
        self.bundle = self.make_bundle(); secret = "sk_live_12345678901234567890"; self.bundle["assertions"][0]["subject"]["entity_id"] = secret; self.save()
        output = self.cli("ontology-validate"); raw = json.dumps(output)
        self.assertIn(output["data"]["quarantine"][0]["reason_code"], {"id_mismatch","secret_like_assertion","dangling_endpoint"}); self.assertNotIn(secret, raw)

    def test_stale_provenance_fails_closed(self):
        self.bundle["source_digest"] = "b" * 64; self.save()
        result = self.cli("ontology-validate", 2); self.assertEqual(result["error"]["code"], "stale_provenance")
        self.bundle = self.make_bundle(); self.bundle["assertions"][0]["source"]["claim_content_hash"] = "b" * 64
        self.bundle["assertions"][0]["assertion_id"] = ontology.assertion_id(self.bundle["namespace"], self.bundle["assertions"][0]); self.save()
        result = self.cli("ontology-validate")["data"]; self.assertIn("stale_provenance", {x["reason_code"] for x in result["quarantine"]})

    def test_causality_needs_direct_human_approval(self):
        item = next(x for x in self.bundle["assertions"] if x["predicate"] == "caused")
        item.update({"method":"explicit","review":None}); item["assertion_id"] = ontology.assertion_id(self.bundle["namespace"], item); self.save()
        result = self.cli("ontology-validate")["data"]
        self.assertIn("causality_requires_human_approval", {x["reason_code"] for x in result["quarantine"]})

    def test_naive_temporal_timestamp_is_quarantined(self):
        item = self.bundle["assertions"][0]
        item["valid_time"]["start"] = "2026-01-01T00:00:00"
        self.save()
        result = self.cli("ontology-validate")["data"]
        self.assertIn("invalid_temporal_shape", {x["reason_code"] for x in result["quarantine"]})

    def test_supersession_cycle_is_inert(self):
        original = next(x for x in self.bundle["assertions"] if x["predicate"] == "supersedes" and x["subject"]["type"] == "Decision")
        reverse = copy.deepcopy(original)
        reverse["subject"], reverse["object"] = reverse["object"], reverse["subject"]
        reverse["assertion_id"] = ontology.assertion_id(self.bundle["namespace"], reverse)
        self.bundle["assertions"].append(reverse); self.save()
        result = self.cli("ontology-validate")["data"]
        self.assertIn("supersession_cycle", {x["reason_code"] for x in result["quarantine"]})
        accepted_ids = {x["assertion_id"] for x in result["accepted_assertions"]}
        self.assertNotIn(original["assertion_id"], accepted_ids); self.assertNotIn(reverse["assertion_id"], accepted_ids)

    def test_identity_ambiguity_is_candidate_only(self):
        claim_id = self.plan()["claims"][0]["claim_id"]
        self.bundle["identity_candidates"] = [{"candidate_id":"idc_1","left":{"type":"Person","entity_id":"person:mina"},"right":{"type":"Person","entity_id":"person:lee"},"feature_codes":["same_display"],"score":0.91,"method":"deterministic-blocking","version":"1","config_hash":"c"*64,"source_claim_ids":[claim_id]}]; self.save()
        queue = self.cli("review-queue")["data"]; candidate = queue["identity_candidates"][0]
        self.assertFalse(candidate["auto_merge"]); self.assertFalse(candidate["projected"]); self.assertEqual(candidate["status"], "candidate")

    def test_identity_candidate_unknown_endpoint_is_quarantined(self):
        claim_id = self.plan()["claims"][0]["claim_id"]
        self.bundle["identity_candidates"] = [{"candidate_id":"idc_1","left":{"type":"Person","entity_id":"person:mina"},"right":{"type":"Person","entity_id":"person:missing"},"feature_codes":["same_display"],"score":0.91,"method":"deterministic-blocking","version":"1","config_hash":"c"*64,"source_claim_ids":[claim_id]}]; self.save()
        result = self.cli("ontology-validate")["data"]
        self.assertFalse(result["identity_candidates"]); self.assertIn("invalid_identity_candidate", {x["reason_code"] for x in result["quarantine"]})

    def test_lifecycle_and_candidate_separation(self):
        item = self.bundle["assertions"][0]; item.update({"method":"extracted_candidate","status":"approved","extractor":{"extractor_id":"local","extractor_version":"1","config_hash":"d"*64},"confidence":0.8}); item["assertion_id"] = ontology.assertion_id(self.bundle["namespace"], item); self.save()
        result = self.cli("ontology-validate")["data"]; self.assertIn("invalid_lifecycle", {x["reason_code"] for x in result["quarantine"]})

    def test_idempotency_reordering_and_source_immutability(self):
        before = {p.relative_to(self.tmp):(hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns, p.stat().st_mode) for p in (self.tmp/"memory").rglob("*.md")}
        first = self.cli("ontology-validate")["data"]; self.bundle["assertions"].reverse(); self.save(); second = self.cli("ontology-validate")["data"]
        after = {p.relative_to(self.tmp):(hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns, p.stat().st_mode) for p in (self.tmp/"memory").rglob("*.md")}
        self.assertEqual(first, second); self.assertEqual(before, after)

    def test_temporal_precision_preserved_and_namespace_isolated(self):
        data = self.cli("ontology-validate")["data"]; self.assertTrue(all(x["valid_time"]["precision"] == "day" for x in data["accepted_assertions"]))
        self.bundle["namespace"] = "memory-graph:v1:" + "f"*24 + ":"; self.save()
        result = self.cli("ontology-validate", 2); self.assertEqual(result["error"]["code"], "namespace_mismatch")

    def test_no_network_or_model_surface(self):
        source = (PACKAGE / "ontology.py").read_text()
        for forbidden in ("requests", "urllib", "socket", "mcporter", "openai", "anthropic"):
            self.assertNotIn(forbidden, source.lower())

    def test_v07_schema_five_snapshot_remains_valid(self):
        plan = self.plan(); plan["schema_version"] = 5; plan.pop("snapshot_hash")
        plan["snapshot_hash"] = ontology.digest(plan)
        (self.tmp / "legacy.json").write_text(json.dumps(plan))
        proc = subprocess.run([str(CLI), "validate-snapshot", "--root", str(self.tmp), "--snapshot", "legacy.json"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout); self.assertEqual(json.loads(proc.stdout)["data"]["schema_version"], 5)


if __name__ == "__main__": unittest.main()
