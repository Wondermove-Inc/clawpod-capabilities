import hashlib
import errno
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
CLI = PACKAGE / "memory_graph.py"
FIXTURE = Path(__file__).parent / "fixtures/basic"
DUPLICATE_FIXTURE = Path(__file__).parent / "fixtures/duplicate-current-key"


def claim(**overrides):
    value = {"claim_id":"c1","claim_key":"thing.one","status":"active","evidence":["memory/2026-08-09.md#L1"],"value":"safe","supersedes":[],"superseded_by":[]}
    value.update(overrides)
    return "```memory-claim\n" + json.dumps(value, sort_keys=True) + "\n```\n"


class MemoryGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        for key in ("FAKE_COMMIT_ERROR_TOOL", "FAKE_COMMIT_TIMEOUT_TOOL", "FAKE_FAIL_TOOL", "FAKE_FAIL_MARKER"):
            os.environ.pop(key, None)
        shutil.rmtree(self.tmp)

    def run_cli(self, *args, expected=0):
        args = list(args)
        if args and args[0] in {"plan", "diff"} and "--agent-id" not in args:
            args.extend(["--agent-id", "test-agent", "--workspace-id", "test-workspace"])
        proc = subprocess.run([str(CLI), *args], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(proc.returncode, expected, proc.stderr + proc.stdout)
        self.assertEqual(proc.stderr, "")
        return proc.stdout, json.loads(proc.stdout)

    def write_memory(self, text):
        (self.tmp / "memory").mkdir(exist_ok=True)
        (self.tmp / "memory" / "topic.md").write_text(text, encoding="utf-8")

    def save(self, name, value):
        (self.tmp / name).write_text(json.dumps(value), encoding="utf-8")

    def fake_mcp(self):
        script = self.tmp / "fake-mcporter"
        script.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
dbp=Path(os.environ["FAKE_MCP_DB"]); db=json.loads(dbp.read_text()) if dbp.exists() else {"entities":[],"relations":[]}
if sys.argv[1:4] == ["list","memory","--schema"]:
 signatures={"create_entities":"entities","create_relations":"relations","delete_entities":"entityNames","delete_relations":"relations","read_graph":None,"open_nodes":"names"}
 if os.environ.get("FAKE_BAD_SCHEMA"): print(json.dumps({"description":"create_entities create_relations delete_entities delete_relations read_graph open_nodes"})); raise SystemExit
 if os.environ.get("FAKE_BIG_SCHEMA"): print("x"*(1024*1024+10)); import time; time.sleep(2); raise SystemExit
 print(json.dumps({"tools":[{"name":n,"inputSchema":{"type":"object","properties":({} if a is None else {a:{"type":"array"}}),"required":([] if a is None else [a])}} for n,a in signatures.items()]})); raise SystemExit
tool=sys.argv[2].split(".")[-1]; args=json.loads(sys.argv[4]) if len(sys.argv)>4 else {}
marker=os.environ.get("FAKE_FAIL_MARKER")
if os.environ.get("FAKE_FAIL_TOOL")==tool and marker and not Path(marker).exists(): Path(marker).touch(); raise SystemExit(7)
if tool=="create_entities":
 by={e["name"]:e for e in db["entities"]}; by.update({e["name"]:e for e in args["entities"]}); db["entities"]=list(by.values())
elif tool=="delete_entities":
 gone=set(args["entityNames"]); db["entities"]=[e for e in db["entities"] if e["name"] not in gone]; db["relations"]=[r for r in db["relations"] if r["from"] not in gone and r["to"] not in gone]
elif tool=="create_relations":
 seen={(r["from"],r["to"],r["relationType"]):r for r in db["relations"]}; seen.update({(r["from"],r["to"],r["relationType"]):r for r in args["relations"]}); db["relations"]=list(seen.values())
elif tool=="delete_relations":
 gone={(r["from"],r["to"],r["relationType"]) for r in args["relations"]}; db["relations"]=[r for r in db["relations"] if (r["from"],r["to"],r["relationType"]) not in gone]
if tool not in {"read_graph","open_nodes"}: dbp.write_text(json.dumps(db))
if os.environ.get("FAKE_COMMIT_ERROR_TOOL")==tool: raise SystemExit(9)
if os.environ.get("FAKE_COMMIT_TIMEOUT_TOOL")==tool:
 import time; time.sleep(3)
if tool=="open_nodes": print(json.dumps({"entities":[e for e in db["entities"] if e["name"] in args["names"]],"relations":[]}))
else: print(json.dumps(db if tool=="read_graph" else {"ok":True}))
''', encoding="utf-8")
        script.chmod(0o755)
        os.environ["FAKE_MCP_DB"] = str(self.tmp / "mcp.json")
        return script

    def plan(self):
        return self.run_cli("plan", "--root", str(self.tmp), "--detail")[1]["data"]

    def test_skill_manifest_version_and_gateway_surface_validate(self):
        manifest = json.loads((PACKAGE / "harness.json").read_text())
        self.assertEqual(manifest["version"], "0.10.5")
        self.assertEqual(set(manifest["commands"]), {"inspect", "plan", "validate-plan", "validate-snapshot", "onboard", "cron-plan", "validate-inference-candidates", "project-inference-overlay", "ontology-validate", "review-queue", "cq-evaluate", "semantic-view", "semantic-extractor-input", "semantic-validate-proposals", "semantic-review-queue", "semantic-approve", "semantic-build", "semantic-migrate-v09", "semantic-reconcile", "semantic-reconcile-verify", "semantic-export-html"})
        self.assertNotIn("query-plan", manifest["commands"], "semantic query remains direct-CLI-only in v0.6")
        skill = (ROOT / "skills/memory-graph/SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: memory-graph\n")); self.assertIn("description:", skill.split("---", 2)[1])
        self.assertIn("first-class cron surface", skill); self.assertNotIn("UTC fallback", skill)

    def test_success_preserves_provenance_and_relation_classes(self):
        out, result = self.run_cli("plan", "--root", str(FIXTURE), "--include-inferred", "--detail")
        data = result["data"]
        self.assertFalse(data["canonical"]); self.assertTrue(data["rebuildable"])
        self.assertEqual([c["claim_id"] for c in data["claims"]], ["cl_project_alpha", "cl_project_owner_new"])
        owner = data["claims"][1]
        self.assertEqual(owner["path"], "memory/topic-projects.md")
        self.assertEqual(owner["claim"], "Mina owns Alpha.")
        self.assertEqual(owner["confidence"], 1.0)
        self.assertEqual(owner["evidence"][0]["evidence_id"], "ev_new")
        self.assertEqual(owner["evidence"][0]["content_hash"], "c" * 64)
        self.assertEqual(data["excluded_claims"], ["cl_project_owner_old", "cl_retired_archived", "cl_retired_old"])
        self.assertIsInstance(owner["line"], int); self.assertRegex(owner["hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(owner["content_hash"], owner["hash"])
        self.assertEqual(len(data["explicit_relations"]), 1)
        self.assertEqual(len(data["structural_relations"]), 5)
        self.assertEqual(len(data["inferred_relations"]), 1)
        self.assertEqual(data["conflicts"]["ambiguous_claim_keys"], [])
        self.assertEqual(result["effects"], [])

    def test_malformed_metadata(self):
        self.write_memory("```memory-claim\n{bad}\n```\n")
        _, result = self.run_cli("inspect", "--root", str(self.tmp), expected=2)
        self.assertEqual(result["error"]["code"], "malformed_metadata")

    def test_missing_required_metadata(self):
        self.write_memory(claim(evidence=None).replace('"evidence": null, ', ''))
        _, result = self.run_cli("inspect", "--root", str(self.tmp), expected=2)
        self.assertEqual(result["error"]["code"], "malformed_metadata")

    def test_idempotency_and_deterministic_output(self):
        shutil.copytree(FIXTURE, self.tmp, dirs_exist_ok=True)
        before = {p.relative_to(self.tmp): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.tmp.rglob("*") if p.is_file()}
        first, _ = self.run_cli("plan", "--root", str(self.tmp), "--include-inferred", "--detail")
        second, _ = self.run_cli("plan", "--root", str(self.tmp), "--include-inferred", "--detail")
        after = {p.relative_to(self.tmp): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.tmp.rglob("*") if p.is_file()}
        self.assertEqual(first, second); self.assertEqual(before, after)

    def test_duplicate_claim_id(self):
        self.write_memory(claim() + claim(claim_key="thing.two"))
        _, result = self.run_cli("inspect", "--root", str(self.tmp), expected=2)
        self.assertEqual(result["error"]["code"], "duplicate_claim_id")

    def test_duplicate_current_key(self):
        _, result = self.run_cli("plan", "--root", str(DUPLICATE_FIXTURE), "--detail")
        plan = result["data"]
        self.assertEqual([c["claim_id"] for c in plan["claims"]], ["cl_signal_a", "cl_signal_b"])
        names = [e["name"].split(plan["ownership"]["namespace"], 1)[1] for e in plan["entities"]]
        self.assertEqual(names, ["agent:self", "claim-key:daily-ai-signal:2026-08-09:publication-status", "claim:cl_signal_a", "claim:cl_signal_b", "workspace:self"])
        self.assertEqual(len(plan["structural_relations"]), 5)
        self.assertEqual(plan["conflicts"]["ambiguous_claim_keys"], [{"claim_key": "daily-ai-signal:2026-08-09:publication-status", "claim_ids": ["cl_signal_a", "cl_signal_b"]}])

    def test_explicit_entity_name_collision_fails_closed(self):
        self.write_memory(claim(claim_id="c1", entity={"name": "shared", "type": "Fact"}) + claim(claim_id="c2", entity={"name": "shared", "type": "Fact"}))
        _, result = self.run_cli("plan", "--root", str(self.tmp), expected=2)
        self.assertEqual(result["error"]["code"], "entity_name_collision")

    def test_explicit_entity_name_cannot_collide_with_claim_key_entity(self):
        self.write_memory(claim(entity={"name": "claim-key:thing.one", "type": "Fact"}))
        _, result = self.run_cli("plan", "--root", str(self.tmp), expected=2)
        self.assertEqual(result["error"]["code"], "entity_name_collision")

    def test_explicit_entity_name_cannot_collide_with_core_anchors(self):
        self.write_memory(claim(entity={"name": "agent:self", "type": "Fact"}))
        _, result = self.run_cli("plan", "--root", str(self.tmp), expected=2)
        self.assertEqual(result["error"]["code"], "entity_name_collision")

    def test_archived_and_superseded_excluded(self):
        self.write_memory(claim(claim_id="old", status="superseded", superseded_by=["c1"]) + claim(claim_id="c1", supersedes=["old"]))
        plan = self.plan()
        self.assertEqual([x["claim_id"] for x in plan["claims"]], ["c1"])
        self.assertEqual(plan["excluded_claims"], ["old"])

    def test_writer_missing_claim_bullet_fails_closed(self):
        text = (FIXTURE / "memory/topic-projects.md").read_text(encoding="utf-8")
        first = text.replace("- Claim: Alpha is active.\n", "", 1)
        self.write_memory(first)
        _, result = self.run_cli("inspect", "--root", str(self.tmp), expected=2)
        self.assertEqual(result["error"]["code"], "malformed_metadata")
        self.assertIn("Claim", result["error"]["details"]["fields"])

    def test_writer_html_json_malformed_and_marker_mismatch(self):
        self.write_memory("## X\n<!-- openclaw-memory-claim:c1 -->\n<!-- openclaw-memory-claim-json:{bad} -->\n")
        _, malformed = self.run_cli("inspect", "--root", str(self.tmp), expected=2)
        self.assertEqual(malformed["error"]["code"], "malformed_metadata")

    def test_all_writer_statuses_and_legacy_active(self):
        for status in ("current", "tentative", "superseded", "rejected", "conflicted", "archived", "active"):
            self.write_memory(claim(status=status))
            _, result = self.run_cli("inspect", "--root", str(self.tmp), "--detail")
            self.assertEqual(result["data"]["claims"][0]["status"], status)

    def test_one_way_supersession_is_supported(self):
        self.write_memory(claim(claim_id="old") + claim(claim_id="new", supersedes=["old"]))
        plan = self.plan()
        self.assertEqual([item["claim_id"] for item in plan["claims"]], ["new"])
        self.assertEqual(plan["excluded_claims"], ["old"])

    def test_self_supersession_fails_closed(self):
        self.write_memory(claim(claim_id="same", supersedes=["same"]))
        _, result = self.run_cli("plan", "--root", str(self.tmp), expected=2)
        self.assertEqual(result["error"]["code"], "inconsistent_supersession")

    def test_reciprocal_cross_key_supersession_is_supported(self):
        self.write_memory(
            claim(claim_id="old", claim_key="legacy.name", status="superseded", superseded_by=["new"])
            + claim(claim_id="new", claim_key="current.name", supersedes=["old"])
        )
        plan = self.plan()
        self.assertEqual([item["claim_id"] for item in plan["claims"]], ["new"])
        self.assertEqual(plan["excluded_claims"], ["old"])

    def test_secret_like_text_rejected_without_echo(self):
        secret = "sk_live_12345678901234567890"
        self.write_memory(claim(value=secret))
        stdout, result = self.run_cli("inspect", "--root", str(self.tmp), expected=2)
        self.assertEqual(result["error"]["code"], "secret_like_text")
        self.assertNotIn(secret, stdout)

    def test_secret_like_text_redacted(self):
        secret = "sk_live_12345678901234567890"
        self.write_memory(claim(value=secret))
        stdout, result = self.run_cli("inspect", "--root", str(self.tmp), "--secret-policy", "redact", "--detail")
        self.assertNotIn(secret, stdout)
        self.assertEqual(result["data"]["claims"][0]["value"], "[REDACTED]")

    def test_writer_claim_secret_redaction(self):
        secret = "sk_live_12345678901234567890"
        text = (FIXTURE / "memory/topic-projects.md").read_text(encoding="utf-8")
        self.write_memory(text.replace("Alpha is active.", secret, 1))
        stdout, result = self.run_cli("inspect", "--root", str(self.tmp), "--secret-policy", "redact", "--detail")
        self.assertNotIn(secret, stdout)
        alpha = next(c for c in result["data"]["claims"] if c["claim_id"] == "cl_project_alpha")
        self.assertEqual(alpha["claim"], "[REDACTED]")

    def test_missing_snapshot(self):
        _, result = self.run_cli("validate-snapshot", "--root", str(self.tmp), "--snapshot", "none.json", expected=2)
        self.assertEqual(result["error"]["code"], "missing_snapshot")

    def test_invalid_snapshot_hash(self):
        self.write_memory(claim()); plan = self.plan(); plan["canonical"] = True; self.save("plan.json", plan)
        _, result = self.run_cli("validate-plan", "--root", str(self.tmp), "--plan", "plan.json", expected=2)
        self.assertEqual(result["error"]["code"], "invalid_snapshot")

    def test_stale_diff_and_delete_planning(self):
        self.write_memory(claim(claim_id="stale", claim_key="thing.stale")); old = self.plan(); self.save("old.json", old)
        self.write_memory(claim(claim_id="fresh", claim_key="thing.fresh"))
        _, result = self.run_cli("diff", "--root", str(self.tmp), "--snapshot", "old.json")
        diff = result["data"]
        self.assertEqual({x.split(old["ownership"]["namespace"], 1)[1] for x in diff["delete_entities"]}, {"claim-key:thing.stale", "claim:stale"})
        self.assertTrue(all(x["name"].startswith(old["ownership"]["namespace"]) for x in diff["create_entities"]))
        self.assertEqual(diff["conflicts"]["ambiguous_claim_keys"], [])
        self.save("diff.json", diff)
        _, export = self.run_cli("export-mcp-batch", "--root", str(self.tmp), "--input", "diff.json")
        tools = [b["tool"] for b in export["data"]["batches"]]
        self.assertEqual(tools, ["delete_relations", "delete_entities", "create_entities", "create_relations"])
        self.assertEqual(export["data"]["conflicts"]["ambiguous_claim_keys"], [])
        self.assertFalse(export["data"]["mutation_performed"])

    def test_export_snapshot_explicit_default_and_inferred_opt_in(self):
        _, result = self.run_cli("plan", "--root", str(FIXTURE), "--include-inferred", "--detail")
        self.save("snapshot.json", result["data"])
        _, default = self.run_cli("export-mcp-batch", "--root", str(self.tmp), "--input", "snapshot.json")
        _, opted = self.run_cli("export-mcp-batch", "--root", str(self.tmp), "--input", "snapshot.json", "--include-inferred")
        default_rel = sum(len(b["arguments"].get("relations", [])) for b in default["data"]["batches"])
        opted_rel = sum(len(b["arguments"].get("relations", [])) for b in opted["data"]["batches"])
        self.assertEqual((default_rel, opted_rel), (6, 7))

    def test_query_plan_requires_grounding(self):
        self.write_memory(claim(value="Blue bicycle")); plan = self.plan(); self.save("plan.json", plan)
        _, result = self.run_cli("query-plan", "--root", str(self.tmp), "--input", "plan.json", "--query", "blue")
        self.assertTrue(result["data"]["canonical_grounding_required"])
        self.assertEqual(len(result["data"]["entities"]), 1)
        self.assertTrue(result["data"]["entities"][0]["name"].endswith("claim:c1"))

    def test_duplicate_conflicts_propagate_to_query_and_export(self):
        plan = self.run_cli("plan", "--root", str(DUPLICATE_FIXTURE), "--detail")[1]["data"]
        self.save("duplicate.json", plan)
        _, query = self.run_cli("query-plan", "--root", str(self.tmp), "--input", "duplicate.json", "--query", "publication")
        _, export = self.run_cli("export-mcp-batch", "--root", str(self.tmp), "--input", "duplicate.json")
        self.assertEqual(query["data"]["conflicts"], plan["conflicts"])
        self.assertEqual(export["data"]["conflicts"], plan["conflicts"])

    def test_invalid_input_path_escape(self):
        _, result = self.run_cli("validate-snapshot", "--root", str(self.tmp), "--snapshot", "../outside.json", expected=2)
        self.assertEqual(result["error"]["code"], "path_outside_root")

    def test_invalid_batch_size(self):
        self.write_memory(claim()); self.save("plan.json", self.plan())
        _, result = self.run_cli("export-mcp-batch", "--root", str(self.tmp), "--input", "plan.json", "--batch-size", "0", expected=2)
        self.assertEqual(result["error"]["code"], "invalid_batch_size")

    def test_memory_sources_reject_symlinks(self):
        (self.tmp / "memory").mkdir()
        outside = self.tmp.parent / (self.tmp.name + "-outside.md")
        outside.write_text(claim(), encoding="utf-8")
        try:
            (self.tmp / "memory" / "topic.md").symlink_to(outside)
            _, result = self.run_cli("inspect", "--root", str(self.tmp), expected=2)
            self.assertEqual(result["error"]["code"], "unsafe_memory_path")
        finally:
            outside.unlink(missing_ok=True)

    def test_changed_entity_recreates_all_incident_relations(self):
        self.write_memory(claim(value="old", relations=[{"to":"claim-key:thing.one", "type":"explicit_link"}]))
        old = self.plan(); self.save("old.json", old)
        self.write_memory(claim(value="new", relations=[{"to":"claim-key:thing.one", "type":"explicit_link"}]))
        diff = self.run_cli("diff", "--root", str(self.tmp), "--snapshot", "old.json")[1]["data"]
        self.assertEqual([x["relationType"] for x in diff["delete_relations"]], ["has_memory_claim", "explicit_link", "has_claim_key"])
        self.assertEqual(diff["delete_relations"], diff["create_relations"])
        self.assertEqual(len(diff["delete_entities"]), 1)
        self.assertTrue(diff["delete_entities"][0].endswith("claim:c1"))
        self.assertTrue(diff["create_entities"][0]["name"].endswith("claim:c1"))

    def test_export_rejects_malformed_diff_objects(self):
        self.write_memory(claim()); current = self.plan(); self.save("old.json", current)
        diff = self.run_cli("diff", "--root", str(self.tmp), "--snapshot", "old.json")[1]["data"]
        cases = []
        extra = dict(diff); extra["unexpected"] = True; cases.append(extra)
        bad_hash = dict(diff); bad_hash["from_snapshot_hash"] = "bad"; cases.append(bad_hash)
        bad_entity = dict(diff); bad_entity["create_entities"] = [{"name":"x","entityType":"T","observations":[],"extra":1}]; cases.append(bad_entity)
        bad_relation = dict(diff); bad_relation["create_relations"] = [{"from":"missing","to":"missing","relationType":"x"}]; cases.append(bad_relation)
        bad_conflict = dict(diff); bad_conflict["conflicts"] = {"ambiguous_claim_keys": [], "extra": []}; cases.append(bad_conflict)
        for index, malformed in enumerate(cases):
            self.save(f"bad-{index}.json", malformed)
            _, result = self.run_cli("export-mcp-batch", "--root", str(self.tmp), "--input", f"bad-{index}.json", expected=2)
            self.assertEqual(result["error"]["code"], "invalid_diff")

    def test_plan_and_inspect_live_output_are_bounded_without_truncation(self):
        large = "".join(claim(claim_id=f"c{i}", claim_key=f"thing.{i}", value="x" * 2000) for i in range(100))
        self.write_memory(large)
        inspect_out, inspect_result = self.run_cli("inspect", "--root", str(self.tmp))
        plan_out, plan_result = self.run_cli("plan", "--root", str(self.tmp))
        self.assertLess(len(inspect_out.encode("utf-8")), 1900)
        self.assertLess(len(plan_out.encode("utf-8")), 1900)
        self.assertEqual(inspect_result["data"]["claim_count"], 100)
        self.assertEqual(plan_result["data"]["claim_count"], 100)
        output_root = self.tmp / "outputs"; output_root.mkdir()
        _, saved = self.run_cli("plan", "--root", str(self.tmp), "--output-root", str(output_root), "--output", "plan.json")
        artifact = json.loads((output_root / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(len(artifact["claims"]), 100)
        self.assertTrue(saved["data"]["artifact_written"])
        self.assertEqual(saved["effects"], [{"path":"plan.json", "type":"write_file"}])

    def test_autonomous_onboard_isolated_idempotent_stale_and_private(self):
        self.write_memory(claim(claim_id="old")); fake = self.fake_mcp(); state = self.tmp / "state"
        (self.tmp / "mcp.json").write_text(json.dumps({"entities":[{"name":"unrelated","entityType":"Keep","observations":[]}],"relations":[]}), encoding="utf-8")
        args = ("onboard", "--root", str(self.tmp), "--agent-id", "agent-a", "--workspace-id", "workspace-a", "--state-root", str(state), "--mcporter", str(fake))
        _, first = self.run_cli(*args)
        self.assertTrue(first["data"]["verified"]); self.assertGreater(first["data"]["applied_batches"], 0)
        _, second = self.run_cli(*args); self.assertEqual(second["data"]["applied_batches"], 0)
        self.write_memory(claim(claim_id="new")); _, third = self.run_cli(*args)
        db = json.loads((self.tmp / "mcp.json").read_text()); names={e["name"] for e in db["entities"]}
        self.assertIn("unrelated", names); self.assertTrue(any(x.endswith("claim:new") for x in names)); self.assertFalse(any(x.endswith("claim:old") for x in names))
        self.assertNotEqual(first["data"]["snapshot_hash"], third["data"]["snapshot_hash"])
        for path in state.rglob("*.json"):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_onboard_namespace_isolation_empty_and_partial_resume(self):
        self.write_memory(""); fake = self.fake_mcp(); state = self.tmp / "state"
        base = ("onboard", "--root", str(self.tmp), "--workspace-id", "same-workspace", "--state-root", str(state), "--mcporter", str(fake))
        _, empty = self.run_cli(*base, "--agent-id", "empty-agent"); self.assertEqual(empty["data"]["entity_count"], 2)
        self.write_memory(claim()); marker=self.tmp/"failed"; os.environ["FAKE_FAIL_TOOL"]="create_relations"; os.environ["FAKE_FAIL_MARKER"]=str(marker)
        self.run_cli(*base, "--agent-id", "recover-agent", expected=2)
        _, recovered = self.run_cli(*base, "--agent-id", "recover-agent")
        os.environ.pop("FAKE_FAIL_TOOL", None); os.environ.pop("FAKE_FAIL_MARKER", None)
        self.assertTrue(recovered["data"]["verified"])
        _, other = self.run_cli(*base, "--agent-id", "other-agent")
        self.assertNotEqual(recovered["data"]["namespace"], other["data"]["namespace"])

    def test_backend_unavailable_records_recoverable_state_without_markdown_change(self):
        self.write_memory(claim()); before=(self.tmp/"memory"/"topic.md").read_bytes(); state=self.tmp/"state"
        _, result = self.run_cli("onboard", "--root", str(self.tmp), "--agent-id", "agent", "--workspace-id", "ws", "--state-root", str(state), "--mcporter", str(self.tmp/"missing"), expected=2)
        self.assertEqual(result["error"]["code"], "backend_unavailable"); self.assertEqual(before, (self.tmp/"memory"/"topic.md").read_bytes())
        self.assertEqual(result["error"]["message"], "Memory MCP backend executable is unavailable")
        self.assertTrue(result["error"]["details"]["mutation_definitely_not_performed"])
        journals=list(state.rglob("journal.json")); self.assertEqual(len(journals), 1)
        self.assertEqual(json.loads(journals[0].read_text())["status"], "backend_unavailable")

    def test_onboard_byte_batches_real_size_observations_beyond_arg_max(self):
        spec = importlib.util.spec_from_file_location("memory_graph_batch_test", CLI)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        item = {"name":"n", "entityType":"T", "observations":["x" * 30000]}
        arg_max = os.sysconf("SC_ARG_MAX")
        items = [{**item, "name":f"n{i}"} for i in range(arg_max // 30000 + 2)]
        unbatched = module.argv_payload_bytes(module.mcp_argv("mcporter", "create_entities", {"entities":items}))
        batches = module.mutation_batches("mcporter", "create_entities", "entities", items)
        self.assertGreater(unbatched, arg_max)
        self.assertEqual([entity for batch in batches for entity in batch["arguments"]["entities"]], items)
        self.assertTrue(all(module.argv_payload_bytes(module.mcp_argv("mcporter", batch["tool"], batch["arguments"]))
                            <= module.MAX_MCP_ARGV_BYTES for batch in batches))

        # This old unbatched argv exceeds Linux's per-string exec limit while
        # bounded read_graph output remains below the independent 1 MiB cap.
        self.write_memory("".join(claim(claim_id=f"large{i}", claim_key=f"large.{i}",
                                            value="x" * 30000) for i in range(20)))
        fake = self.fake_mcp(); state = self.tmp / "state"
        result = self.run_cli("onboard", "--root", str(self.tmp), "--agent-id", "agent",
            "--workspace-id", "large", "--state-root", str(state), "--mcporter", str(fake),
            "--timeout-seconds", "10")[1]
        self.assertTrue(result["data"]["verified"])
        self.assertGreater(result["data"]["applied_batches"], 3)

    def test_single_oversized_entity_is_precise_no_mutation_and_recovers(self):
        self.write_memory(claim(value="x" * 60000)); fake = self.fake_mcp(); state = self.tmp / "state"
        args = ("onboard", "--root", str(self.tmp), "--agent-id", "agent", "--workspace-id", "oversized",
                "--state-root", str(state), "--mcporter", str(fake))
        failed = self.run_cli(*args, expected=2)[1]
        self.assertEqual(failed["error"]["code"], "mutation_item_too_large")
        self.assertIn("no mutation was attempted", failed["error"]["message"])
        self.assertFalse(failed["error"]["details"]["mutation_performed"])
        self.assertEqual(failed["effects"], [])
        self.assertFalse((self.tmp / "mcp.json").exists())
        journal = json.loads(next(state.rglob("journal.json")).read_text())
        self.assertNotIn("mutation_attempt", journal)
        self.write_memory(claim(value="small"))
        recovered = self.run_cli(*args)[1]
        self.assertTrue(recovered["data"]["verified"])
        self.assertEqual(recovered["data"]["transaction_id"], 2)

    def test_pre_spawn_e2big_has_no_ambiguous_effect_and_retry_rereads_backend(self):
        self.write_memory(claim()); fake = self.fake_mcp(); state = self.tmp / "state"
        spec = importlib.util.spec_from_file_location("memory_graph_under_test", CLI)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        original_popen = module.subprocess.Popen
        def popen(argv, *args, **kwargs):
            if len(argv) > 2 and argv[1] == "call" and argv[2] == "memory.create_entities":
                raise OSError(errno.E2BIG, "Argument list too long")
            return original_popen(argv, *args, **kwargs)
        with mock.patch.object(module.subprocess, "Popen", side_effect=popen):
            with self.assertRaises(module.InputError) as caught:
                module.onboard(self.tmp, "agent", "e2big", state, str(fake), 10, "reject")
        self.assertEqual(caught.exception.code, "backend_argv_too_large")
        self.assertEqual(caught.exception.details["effects"], [])
        journal = json.loads(next(state.rglob("journal.json")).read_text())
        self.assertEqual(journal["mutation_attempt"]["status"], "dispatching")
        self.assertFalse((self.tmp / "mcp.json").exists())
        recovered = self.run_cli("onboard", "--root", str(self.tmp), "--agent-id", "agent",
            "--workspace-id", "e2big", "--state-root", str(state), "--mcporter", str(fake))[1]
        self.assertTrue(recovered["data"]["verified"])
        self.assertEqual(recovered["data"]["transaction_id"], 2)

    def test_lost_state_discovers_stale_owned_and_reports_foreign_inbound(self):
        self.write_memory(claim(claim_id="new")); fake = self.fake_mcp(); state = self.tmp / "state"
        prefix = self.plan()["ownership"]["namespace"]
        stale = prefix + "claim:stale"
        foreign = {"name":"foreign","entityType":"Keep","observations":["untouched"]}
        db = {"entities":[foreign,{"name":stale,"entityType":"MemoryClaim","observations":[]}],
              "relations":[{"from":"foreign","to":stale,"relationType":"references"}]}
        (self.tmp / "mcp.json").write_text(json.dumps(db), encoding="utf-8")
        result = self.run_cli("onboard", "--root", str(self.tmp), "--agent-id", "test-agent", "--workspace-id", "test-workspace", "--state-root", str(state), "--mcporter", str(fake))[1]
        final = json.loads((self.tmp / "mcp.json").read_text())
        self.assertIn(foreign, final["entities"]); self.assertNotIn(stale, {e["name"] for e in final["entities"]})
        self.assertEqual(result["data"]["removed_foreign_inbound_relations"], db["relations"])

    def test_fault_injection_at_every_state_boundary_is_recoverable(self):
        points = ("prepared", "schema_verified", "backend_discovered", "before_mutation", "after_mutation", "progress_recorded", "verified", "snapshot_committed", "complete")
        for point in points:
            with self.subTest(point=point):
                case = self.tmp / point; case.mkdir(); (case / "memory").mkdir(); (case / "memory" / "topic.md").write_text(claim(), encoding="utf-8")
                old_db = os.environ["FAKE_MCP_DB"] if "FAKE_MCP_DB" in os.environ else None
                fake = self.fake_mcp(); os.environ["FAKE_MCP_DB"] = str(case / "mcp.json")
                args = ("onboard", "--root", str(case), "--agent-id", "agent", "--workspace-id", point, "--state-root", str(case/"state"), "--mcporter", str(fake))
                os.environ["MEMORY_GRAPH_FAULT"] = point
                self.run_cli(*args, expected=2)
                os.environ.pop("MEMORY_GRAPH_FAULT", None)
                recovered = self.run_cli(*args)[1]
                self.assertTrue(recovered["data"]["verified"])
                if old_db is None: os.environ.pop("FAKE_MCP_DB", None)
                else: os.environ["FAKE_MCP_DB"] = old_db

    def test_fresh_agent_prepare_run_standing_authorization_protocol(self):
        prepared = {"approvalRequired": True, "safetyClasses": ["writeSafe"],
                    "intentHash": "sha256:prepared-exact-input"}
        run_request = {"name": "memory-graph", "command": "onboard", "input": {"agentId": "agent"},
                       "approvalIntentHash": prepared["intentHash"]}
        self.assertTrue(prepared["approvalRequired"])
        self.assertEqual(prepared["safetyClasses"], ["writeSafe"])
        self.assertEqual(run_request["approvalIntentHash"], prepared["intentHash"])
        self.assertNotIn("userApprovalToken", run_request)
        skill = (ROOT / "skills/memory-graph/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("standing owner authorization", skill)
        self.assertIn("matching `approvalIntentHash`", skill)
        self.assertIn("separate user approval token", skill)

    def test_fresh_agent_cron_contract_is_deterministic_and_idempotent(self):
        plan_args = ("cron-plan", "--root", str(self.tmp), "--agent-id", "agent", "--workspace-id", "workspace", "--state-root", str(self.tmp/"state"), "--timezone", "America/New_York")
        first = self.run_cli(*plan_args)[1]["data"]; second = self.run_cli(*plan_args)[1]["data"]
        self.assertEqual(first, second); add = first["cron_add"]
        self.assertNotIn("id", add); self.assertTrue(first["server_generated_id"])
        self.assertEqual(add["schedule"], {"kind":"cron", "expr":"0 0 * * *", "tz":"America/New_York"})
        self.assertEqual(add["agentId"], "agent"); self.assertEqual(add["sessionTarget"], "isolated")
        self.assertEqual(add["payload"]["kind"], "agentTurn")
        self.assertIn("harness.run.prepare", add["payload"]["message"])
        self.assertIn("approvalIntentHash", add["payload"]["message"])
        contract = Path(__file__).parent / "fixtures/contracts/openclaw-2026.4.11-cron-add.json"
        allowed = set(json.loads(contract.read_text())["allowed_top_level"])
        self.assertLessEqual(set(add), allowed)
        jobs = []
        matches = lambda job: all(job.get(k) == v for k,v in first["match"].items())
        if not [j for j in jobs if matches(j)]: jobs.append({"id":"server-generated-1", **add})
        if not [j for j in jobs if matches(j)]: jobs.append({"id":"server-generated-2", **add})
        owned_ids = [j["id"] for j in jobs if matches(j)]
        self.assertEqual(owned_ids, ["server-generated-1"])
        jobs = [j for j in jobs if j.get("id") not in owned_ids]
        self.assertEqual(jobs, [])
        bad = self.run_cli("cron-plan", "--root", str(self.tmp), "--agent-id", "agent", "--state-root", str(self.tmp/"state"), "--timezone", "Not/AZone", expected=2)[1]
        self.assertEqual(bad["error"]["code"], "invalid_timezone")

    def test_commit_plus_error_and_timeout_report_ambiguous_effect_and_recover(self):
        for mode, env_key in (("error", "FAKE_COMMIT_ERROR_TOOL"), ("timeout", "FAKE_COMMIT_TIMEOUT_TOOL")):
            with self.subTest(mode=mode):
                case = self.tmp / mode; case.mkdir(); (case / "memory").mkdir(); (case / "memory" / "topic.md").write_text(claim(), encoding="utf-8")
                fake = self.fake_mcp(); os.environ["FAKE_MCP_DB"] = str(case / "mcp.json")
                os.environ[env_key] = "create_entities"
                args = ("onboard", "--root", str(case), "--agent-id", "agent", "--workspace-id", mode,
                        "--state-root", str(case/"state"), "--mcporter", str(fake), "--timeout-seconds", "1")
                failed = self.run_cli(*args, expected=2)[1]
                effect = failed["effects"][0]
                self.assertEqual(effect["type"], "mutation_may_have_occurred")
                self.assertEqual(effect["tool"], "create_entities")
                self.assertEqual(effect["transaction_id"], 1)
                self.assertTrue(effect["reconciliation_required"])
                self.assertTrue(effect["namespace"].startswith("memory-graph:v1:"))
                os.environ.pop(env_key)
                recovered = self.run_cli(*args)[1]
                self.assertTrue(recovered["data"]["verified"])
                db = json.loads((case / "mcp.json").read_text())
                names = [e["name"] for e in db["entities"]]
                self.assertEqual(len(names), len(set(names)))
                for entity in db["entities"]:
                    self.assertEqual(len(entity["observations"]), len(set(entity["observations"])))

    def test_schema_is_structural_and_subprocess_output_is_capped_while_running(self):
        self.write_memory(claim()); fake = self.fake_mcp()
        args = ("onboard", "--root", str(self.tmp), "--agent-id", "agent", "--state-root", str(self.tmp/"state"), "--mcporter", str(fake))
        os.environ["FAKE_BAD_SCHEMA"] = "1"
        bad = self.run_cli(*args, expected=2)[1]
        os.environ.pop("FAKE_BAD_SCHEMA", None)
        self.assertEqual(bad["error"]["code"], "backend_schema_mismatch")
        os.environ["FAKE_BIG_SCHEMA"] = "1"
        started = __import__("time").monotonic(); capped = self.run_cli(*args, expected=2)[1]
        os.environ.pop("FAKE_BIG_SCHEMA", None)
        self.assertLess(__import__("time").monotonic() - started, 2)
        self.assertEqual(capped["error"]["code"], "backend_output_limit")

    def test_memory_only_source_boundary_and_stale_core_cleanup(self):
        ignored = ["MEMORY.md", "memory.md", "AGENTS.md", "SOUL.md", "IDENTITY.md", "USER.md",
                   "ORGANIZATIONS.md", "WORKFLOW.md", "BOOTSTRAP.md", "HEARTBEAT.md", "TOOLS.md"]
        for name in ignored:
            (self.tmp / name).write_text(claim(claim_id="ignored-" + name.replace(".", "-")), encoding="utf-8")
        nested = self.tmp / "memory" / ".evidence"; nested.mkdir(parents=True)
        (nested / "ignored.md").write_text(claim(claim_id="nested-evidence"), encoding="utf-8")
        registry = self.tmp / "memory" / ".registry"; registry.mkdir()
        (registry / "ignored.md").write_text(claim(claim_id="nested-registry"), encoding="utf-8")
        self.write_memory(claim(claim_id="direct"))
        inspected = self.run_cli("inspect", "--root", str(self.tmp), "--detail")[1]["data"]
        self.assertEqual([s["path"] for s in inspected["sources"]], ["memory/topic.md"])
        self.assertEqual([c["claim_id"] for c in inspected["claims"]], ["direct"])
        self.assertEqual(inspected["core_documents"], []); self.assertEqual(inspected["core_sections"], [])
        compact = self.run_cli("inspect", "--root", str(self.tmp))[1]["data"]
        self.assertEqual(compact["source_count"], 1); self.assertEqual(compact["core_source_count"], 0)
        self.assertEqual(compact["core_document_count"], 0); self.assertEqual(compact["core_section_count"], 0)
        old = self.plan(); prefix = old["ownership"]["namespace"]
        old_core = {"name": prefix + "document:SOUL.md", "entityType": "CoreDocument", "observations": ["{}"]}
        old["entities"].append(old_core)
        old["structural_relations"].append({"from":prefix+"workspace:self","to":old_core["name"],"relationType":"contains_core_document"})
        old["snapshot_hash"] = memory_graph_digest = __import__("hashlib").sha256(json.dumps({k:v for k,v in old.items() if k != "snapshot_hash"}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.save("old.json", old)
        diff = self.run_cli("diff", "--root", str(self.tmp), "--snapshot", "old.json")[1]["data"]
        self.assertIn(old_core["name"], diff["delete_entities"])
        fake = self.fake_mcp()
        foreign = {"name":"foreign:document:SOUL.md","entityType":"Foreign","observations":["keep"]}
        (self.tmp / "mcp.json").write_text(json.dumps({"entities":[old_core, foreign], "relations":[]}), encoding="utf-8")
        result = self.run_cli("onboard", "--root", str(self.tmp), "--agent-id", "test-agent",
                              "--workspace-id", "test-workspace", "--state-root", str(self.tmp / "state"),
                              "--mcporter", str(fake))[1]["data"]
        graph = json.loads((self.tmp / "mcp.json").read_text(encoding="utf-8"))
        self.assertTrue(result["verified"])
        self.assertNotIn(old_core["name"], {e["name"] for e in graph["entities"]})
        self.assertIn(foreign, graph["entities"])

    def test_direct_memory_symlink_fails_closed_but_root_and_nested_symlinks_are_ignored(self):
        outside = self.tmp.parent / (self.tmp.name + "-outside.md"); outside.write_text(claim(), encoding="utf-8")
        try:
            (self.tmp / "MEMORY.md").symlink_to(outside)
            nested = self.tmp / "memory" / ".evidence"; nested.mkdir(parents=True)
            (nested / "nested.md").symlink_to(outside)
            self.assertEqual(self.run_cli("inspect", "--root", str(self.tmp))[1]["data"]["source_count"], 0)
            (self.tmp / "memory" / "direct.md").symlink_to(outside)
            result = self.run_cli("inspect", "--root", str(self.tmp), expected=2)[1]
            self.assertEqual(result["error"]["code"], "unsafe_memory_path")
        finally:
            outside.unlink(missing_ok=True)

    def test_grounded_semantic_projection_query_and_quarantine(self):
        ev={"evidence_id":"ev1","path":"memory/evidence.md","content_hash":"a"*64}
        semantic={"entities":[
            {"entity_id":"person:mina","type":"Person","canonical_name":"Mina"},
            {"entity_id":"project:alpha","type":"Project","canonical_name":"Alpha"}],
            "relations":[{"from":"person:mina","type":"participates_in","to":"project:alpha"}]}
        self.write_memory(claim(status="current", evidence=[ev], semantic=semantic))
        plan=self.plan()
        self.assertEqual([e["entityType"] for e in plan["entities"] if ":semantic:" in e["name"]], ["Person","Project"])
        self.assertEqual(plan["semantic_relations"][0]["relationType"], "participates_in")
        self.assertRegex(plan["semantic_relations"][0]["edge_id"], r"^[0-9a-f]{64}$")
        self.save("plan.json", plan)
        _, result=self.run_cli("query-plan","--root",str(self.tmp),"--input","plan.json","--entity-id","person:mina","--max-depth","1","--explain")
        self.assertFalse(result["data"]["canonical"]); self.assertTrue(result["data"]["locator_only"])
        self.assertEqual(len(result["data"]["hydration_requests"]),1)

    def test_semantic_missing_provenance_is_quarantined_without_breaking_claim(self):
        semantic={"entities":[{"entity_id":"person:x","type":"Person","canonical_name":"X"}],"relations":[]}
        self.write_memory(claim(status="current", semantic=semantic))
        plan=self.plan()
        self.assertEqual(plan["semantic_quarantine"][0]["reason_code"],"missing_provenance")
        self.assertTrue(any(e["entityType"]=="MemoryClaim" for e in plan["entities"]))
        self.assertFalse(any(e["entityType"]=="Person" for e in plan["entities"]))

    def test_semantic_namespace_and_secret_isolation(self):
        ev={"evidence_id":"ev1","path":"memory/evidence.md","content_hash":"b"*64}
        semantic={"entities":[{"entity_id":"person:x","type":"Person","canonical_name":"password=supersecretvalue"}],"relations":[]}
        self.write_memory(claim(status="current", evidence=[ev], semantic=semantic))
        stdout, result=self.run_cli("plan","--root",str(self.tmp),"--detail",expected=2)
        self.assertEqual(result["error"]["code"],"secret_like_text"); self.assertNotIn("supersecretvalue",stdout)

    def test_semantic_unknown_type_relation_and_endpoint_violations_are_inert(self):
        ev={"evidence_id":"ev","path":"memory/e.md","content_hash":"a"*64}
        semantic={"entities":[
            {"entity_id":"person:p","type":"Person","canonical_name":"P"},
            {"entity_id":"project:x","type":"Project","canonical_name":"X"},
            {"entity_id":"alien:x","type":"Alien","canonical_name":"X"}],
            "relations":[
                {"from":"project:x","type":"decided","to":"person:p"},
                {"from":"person:p","type":"invented","to":"project:x"}]}
        self.write_memory(claim(status="current", evidence=[ev], semantic=semantic))
        plan=self.plan(); reasons=[q["reason_code"] for q in plan["semantic_quarantine"]]
        self.assertEqual(reasons,["invalid_endpoint_type","unknown_relation","unknown_type"])
        self.assertEqual(plan["semantic_relations"],[])

    def test_semantic_temporal_validation_normalization_and_interval_order(self):
        ev={"evidence_id":"ev","path":"memory/e.md","content_hash":"b"*64}
        semantic={"entities":[
            {"entity_id":"decision:good","type":"Decision","canonical_name":"Good","effective_at":"2026-08-10T10:00:00+09:00"},
            {"entity_id":"event:date","type":"Event","canonical_name":"Date","occurred_at":"2026-08-10"},
            {"entity_id":"event:naive","type":"Event","canonical_name":"Naive","occurred_at":"2026-08-10T01:00:00"},
            {"entity_id":"event:reverse","type":"Event","canonical_name":"Reverse","interval":{"start":"2026-08-11","end":"2026-08-10"}}],"relations":[]}
        self.write_memory(claim(status="current", evidence=[ev], semantic=semantic))
        plan=self.plan(); obs={json.loads(e["observations"][0])["entity_id"]:json.loads(e["observations"][0]) for e in plan["entities"] if ":semantic:" in e["name"]}
        self.assertEqual(obs["decision:good"]["effective_at_normalized"],"2026-08-10T01:00:00Z")
        self.assertEqual(obs["event:date"]["occurred_at_normalized"],"2026-08-10")
        self.assertEqual([q["reason_code"] for q in plan["semantic_quarantine"]],["temporal_conflict","temporal_conflict"])

    def test_semantic_supersession_cycle_self_and_backwards_time_are_quarantined(self):
        ev={"evidence_id":"ev","path":"memory/e.md","content_hash":"c"*64}
        entities=[
            {"entity_id":"decision:a","type":"Decision","canonical_name":"A","effective_at":"2026-08-10T00:00:00Z"},
            {"entity_id":"decision:b","type":"Decision","canonical_name":"B","effective_at":"2026-08-11T00:00:00Z"},
            {"entity_id":"decision:c","type":"Decision","canonical_name":"C","effective_at":"2026-08-09T00:00:00Z"}]
        relations=[
            {"from":"decision:a","type":"supersedes","to":"decision:b"},
            {"from":"decision:b","type":"supersedes","to":"decision:a"},
            {"from":"decision:c","type":"supersedes","to":"decision:c"}]
        self.write_memory(claim(status="current", evidence=[ev], semantic={"entities":entities,"relations":relations}))
        plan=self.plan(); self.assertEqual(plan["semantic_relations"],[])
        self.assertEqual({q["reason_code"] for q in plan["semantic_quarantine"]},{"supersession_cycle"})

    def test_semantic_alias_evidence_and_input_order_are_deterministic(self):
        ev1={"evidence_id":"z","path":"memory/z.md","content_hash":"d"*64}; ev2={"evidence_id":"a","path":"memory/a.md","content_hash":"e"*64}
        entity={"entity_id":"person:p","type":"Person","canonical_name":"P","aliases":["  ALICE  ","Alice"],"external_ids":["z:2","a:1"]}
        self.write_memory(claim(status="current", evidence=[ev1,ev2], semantic={"entities":[entity],"relations":[]}))
        first=self.plan()
        entity["aliases"].reverse(); entity["external_ids"].reverse()
        self.write_memory(claim(status="current", evidence=[ev2,ev1], semantic={"relations":[],"entities":[entity]}))
        second=self.plan()
        # Canonical source hashes intentionally change with file bytes, while the
        # derived semantic projection must remain byte-for-byte deterministic.
        for field in ("semantic_relations","semantic_quarantine"):
            self.assertEqual(first[field],second[field])
        first_entities=[e for e in first["entities"] if ":semantic:" in e["name"]]
        second_entities=[e for e in second["entities"] if ":semantic:" in e["name"]]
        self.assertEqual([(e["name"],e["entityType"]) for e in first_entities],
                         [(e["name"],e["entityType"]) for e in second_entities])
        first_obs=json.loads(first_entities[0]["observations"][0]); second_obs=json.loads(second_entities[0]["observations"][0])
        self.assertEqual({k:v for k,v in first_obs.items() if k!="provenance"},
                         {k:v for k,v in second_obs.items() if k!="provenance"})
        self.assertEqual(first_obs["provenance"][0]["content_hash"],second_obs["provenance"][0]["content_hash"])

    def test_semantic_status_query_cycle_bounds_and_manifest_schema_subset(self):
        ev={"evidence_id":"ev","path":"memory/e.md","content_hash":"f"*64}
        sem={"entities":[{"entity_id":"person:p","type":"Person","canonical_name":"P"}],"relations":[]}
        self.write_memory(claim(status="tentative", evidence=[ev], semantic=sem)); plan=self.plan(); self.save("p.json",plan)
        default=self.run_cli("query-plan","--root",str(self.tmp),"--input","p.json","--entity-id","person:p")[1]["data"]
        opted=self.run_cli("query-plan","--root",str(self.tmp),"--input","p.json","--entity-id","person:p","--statuses","tentative")[1]["data"]
        self.assertEqual(default["entities"],[]); self.assertEqual(len(opted["entities"]),1)
        bad=self.run_cli("query-plan","--root",str(self.tmp),"--input","p.json","--max-depth","4",expected=2)[1]
        self.assertEqual(bad["error"]["code"],"query_bounds")
        manifest=json.loads((PACKAGE/"harness.json").read_text())
        forbidden={"enum","minimum","maximum","minLength"}
        def keys(value):
            if isinstance(value,dict):
                return set(value)|set().union(*(keys(v) for v in value.values()),set())
            if isinstance(value,list): return set().union(*(keys(v) for v in value),set())
            return set()
        self.assertTrue(forbidden.isdisjoint(keys(manifest)))

    def inference_bundle(self, relation="participates_in", confidence=0.0, basis="direct_statement", explicit=False):
        ev={"evidence_id":"ev","path":"memory/e.md","content_hash":"a"*64}
        sem={"entities":[
            {"entity_id":"person:p","type":"Person","canonical_name":"P"},
            {"entity_id":"project:x","type":"Project","canonical_name":"X"}],"relations":
            ([{"from":"person:p","type":"participates_in","to":"project:x"}] if explicit else [])}
        folder=self.tmp/"memory"; folder.mkdir(exist_ok=True)
        source=folder/"topic.md"; source.write_text(claim(status="current", evidence=[ev], semantic=sem), encoding="utf-8")
        plan=self.run_cli("plan","--root",str(self.tmp),"--agent-id","test-agent","--workspace-id","test-workspace","--detail")[1]["data"]
        canonical_claim=plan["claims"][0]; namespace=plan["ownership"]["namespace"]
        candidate={"candidate_id":"", "source_claim_id":"c1", "source":{
            "path":"memory/topic.md","line_start":1,"line_end":len(source.read_text().splitlines()),
            "source_content_hash":hashlib.sha256(source.read_bytes()).hexdigest(),
            "claim_content_hash":canonical_claim["content_hash"]},
            "from":{"entity_id":"person:p","type":"Person"},"relation_type":relation,
            "to":{"entity_id":"project:x","type":"Project"},"confidence":confidence,"basis":basis}
        extractor={"name":"agent-semantic-inference","version":"extractor-v1","config_hash":"b"*64}
        parts=(namespace,"c1",candidate["source"]["claim_content_hash"],"Person","person:p",relation,"Project","project:x",extractor["name"],extractor["version"],extractor["config_hash"])
        candidate["candidate_id"]="ic_"+hashlib.sha256("".join(parts).encode()).hexdigest()
        return {"schema_version":"memory-graph-inference-candidates/v1","semantic_contract_version":"0.7",
            "namespace":namespace,"source_snapshot_hash":plan["snapshot_hash"],"source_digest":plan["source_digest"],
            "extractor":extractor,"candidates":[candidate]}, plan

    def test_inference_projection_determinism_cache_query_and_visual_separation(self):
        bundle, plan=self.inference_bundle(confidence=0.0); self.save("bundle.json",bundle); self.save("plan.json",plan)
        spec=importlib.util.spec_from_file_location("memory_graph_inference_test",CLI)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with mock.patch.object(module,"mcp_call",side_effect=AssertionError("MCP forbidden")), mock.patch.object(module.subprocess,"run",side_effect=AssertionError("network/model subprocess forbidden")):
            validated=module.validate_inference_candidates(self.tmp,bundle,"test-agent","test-workspace")
            self.assertEqual(len(module.project_inference_overlay(validated)["inferred_relations"]),1)
        before={p: (hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in self.tmp.rglob("*.md")}
        first=self.run_cli("project-inference-overlay","--root",str(self.tmp),"--input","bundle.json","--agent-id","test-agent","--workspace-id","test-workspace","--state-root",str(self.tmp/"state"))[1]
        second=self.run_cli("project-inference-overlay","--root",str(self.tmp),"--input","bundle.json","--agent-id","test-agent","--workspace-id","test-workspace","--state-root",str(self.tmp/"state"))[1]
        self.assertEqual(first["data"]["overlay_hash"],second["data"]["overlay_hash"]); self.assertTrue(second["data"]["cache"]["cache_hit"])
        cache=next((self.tmp/"state").rglob("*.json")); self.assertEqual(cache.stat().st_mode & 0o777,0o600)
        self.assertEqual(before,{p: (hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in self.tmp.rglob("*.md")})
        self.save("overlay.json",first["data"] | {"cache": first["data"]["cache"]})
        # Cache metadata is not part of an overlay artifact.
        overlay=dict(first["data"]); overlay.pop("cache"); self.save("overlay.json",overlay)
        default=self.run_cli("query-plan","--root",str(self.tmp),"--input","plan.json","--entity-id","person:p")[1]["data"]
        opted=self.run_cli("query-plan","--root",str(self.tmp),"--input","plan.json","--overlay","overlay.json","--include-inferred","--entity-id","person:p")[1]["data"]
        self.assertEqual(default["inferred_relations"],[]); self.assertEqual(opted["inferred_relations"][0]["confidence"],0.0)
        visual=self.run_cli("export-visualization","--root",str(self.tmp),"--input","plan.json","--overlay","overlay.json","--include-inferred")[1]["data"]
        self.assertEqual(visual["inferred_relations"][0]["line_style"],"dashed"); self.assertIn("Inferred, noncanonical",visual["inferred_relations"][0]["label"])

    def test_inference_stale_namespace_id_endpoint_and_secret_fail_closed(self):
        bundle,_=self.inference_bundle(); bundle["namespace"]="memory-graph:v1:"+("0"*24)+":"; self.save("bad.json",bundle)
        bad=self.run_cli("validate-inference-candidates","--root",str(self.tmp),"--input","bad.json","--agent-id","test-agent","--workspace-id","test-workspace",expected=2)[1]
        self.assertEqual(bad["error"]["code"],"namespace_mismatch")
        bundle,_=self.inference_bundle(); bundle["candidates"][0]["candidate_id"]="ic_"+("0"*64); self.save("bad.json",bundle)
        data=self.run_cli("validate-inference-candidates","--root",str(self.tmp),"--input","bad.json","--agent-id","test-agent","--workspace-id","test-workspace")[1]["data"]
        self.assertEqual(data["quarantine"][0]["reason_code"],"id_mismatch")
        secret="sk_live_12345678901234567890"; bundle["candidates"][0]["source_claim_id"]=secret; self.save("bad.json",bundle)
        stdout,result=self.run_cli("validate-inference-candidates","--root",str(self.tmp),"--input","bad.json","--agent-id","test-agent","--workspace-id","test-workspace")
        self.assertEqual(result["data"]["quarantine"][0]["reason_code"],"secret_like_candidate"); self.assertNotIn(secret,stdout)

    def test_inference_stale_source_malformed_oversized_and_symlink(self):
        bundle,_=self.inference_bundle(); self.save("bundle.json",bundle)
        (self.tmp/"memory/topic.md").write_text((self.tmp/"memory/topic.md").read_text()+"changed\n")
        stale=self.run_cli("validate-inference-candidates","--root",str(self.tmp),"--input","bundle.json","--agent-id","test-agent","--workspace-id","test-workspace",expected=2)[1]
        self.assertEqual(stale["error"]["code"],"stale_snapshot")
        (self.tmp/"bad.json").write_text("{"); malformed=self.run_cli("validate-inference-candidates","--root",str(self.tmp),"--input","bad.json","--agent-id","x",expected=2)[1]
        self.assertEqual(malformed["error"]["code"],"malformed_bundle")
        (self.tmp/"big.json").write_bytes(b"x"*(1024*1024+1)); oversized=self.run_cli("validate-inference-candidates","--root",str(self.tmp),"--input","big.json","--agent-id","x",expected=2)[1]
        self.assertEqual(oversized["error"]["code"],"oversized_bundle")

    def test_inference_rejects_bundle_and_cache_symlink_escape(self):
        bundle,_=self.inference_bundle(); outside=self.tmp.parent/(self.tmp.name+"-bundle.json")
        outside.write_text(json.dumps(bundle),encoding="utf-8")
        try:
            (self.tmp/"linked.json").symlink_to(outside)
            result=self.run_cli("validate-inference-candidates","--root",str(self.tmp),"--input","linked.json",
                "--agent-id","test-agent","--workspace-id","test-workspace",expected=2)[1]
            self.assertEqual(result["error"]["code"],"invalid_bundle")
            self.save("bundle.json",bundle)
            real_state=self.tmp/"real-state"; real_state.mkdir(); (self.tmp/"linked-state").symlink_to(real_state,target_is_directory=True)
            result=self.run_cli("project-inference-overlay","--root",str(self.tmp),"--input","bundle.json",
                "--agent-id","test-agent","--workspace-id","test-workspace","--state-root",str(self.tmp/"linked-state"),expected=2)[1]
            self.assertEqual(result["error"]["code"],"unsafe_state_path")
            self.assertEqual(list(real_state.rglob("*")),[])
        finally:
            outside.unlink(missing_ok=True)

    def test_inference_cache_reconciles_stale_entries_and_manifest_write_class(self):
        bundle,_=self.inference_bundle(confidence=0.1); self.save("bundle.json",bundle); state=self.tmp/"state"
        first=self.run_cli("project-inference-overlay","--root",str(self.tmp),"--input","bundle.json",
            "--agent-id","test-agent","--workspace-id","test-workspace","--state-root",str(state))[1]["data"]
        bundle["candidates"][0]["confidence"]=0.2; self.save("bundle.json",bundle)
        second=self.run_cli("project-inference-overlay","--root",str(self.tmp),"--input","bundle.json",
            "--agent-id","test-agent","--workspace-id","test-workspace","--state-root",str(state))[1]["data"]
        self.assertNotEqual(first["cache"]["cache_key"],second["cache"]["cache_key"])
        self.assertEqual(second["cache"]["removed_stale_entries"],[first["cache"]["cache_key"]+".json"])
        self.assertEqual(len(list(state.rglob("*.json"))),1)
        manifest=json.loads((PACKAGE/"harness.json").read_text())
        self.assertEqual(manifest["commands"]["project-inference-overlay"]["safetyClasses"],["writeSafe"])

    def test_inference_unknown_keys_types_relations_confidence_and_endpoint_fail_closed(self):
        cases=[]
        bundle,_=self.inference_bundle(); bundle["extra"]=True; cases.append((bundle,"bundle","invalid_bundle"))
        for change,reason in (
            (lambda c: c.update({"relation_type":"invented"}),"unknown_relation"),
            (lambda c: c.update({"confidence":float("nan")}),"invalid_confidence"),
            (lambda c: c.update({"confidence":float("inf")}),"invalid_confidence"),
            (lambda c: c.update({"confidence":1.01}),"invalid_confidence"),
            (lambda c: c["from"].update({"type":"Project"}),"invalid_endpoint_type"),
            (lambda c: c["to"].update({"entity_id":"project:missing"}),"unresolved_explicit_endpoint")):
            candidate_bundle,_=self.inference_bundle(); change(candidate_bundle["candidates"][0]); cases.append((candidate_bundle,"candidate",reason))
        for index,(value,level,reason) in enumerate(cases):
            self.save(f"case-{index}.json",value)
            result=self.run_cli("validate-inference-candidates","--root",str(self.tmp),"--input",f"case-{index}.json",
                "--agent-id","test-agent","--workspace-id","test-workspace",expected=2 if level=="bundle" else 0)[1]
            actual=result["error"]["code"] if level=="bundle" else result["data"]["quarantine"][0]["reason_code"]
            self.assertEqual(actual,reason)

    def test_inference_shadowing_causality_and_quarantine_order(self):
        bundle,_=self.inference_bundle(); bundle["candidates"][0]["relation_type"]="caused"; bundle["candidates"][0]["basis"]="direct_statement"
        bundle["candidates"][0]["candidate_id"]="ic_"+("0"*64); self.save("bundle.json",bundle)
        data=self.run_cli("validate-inference-candidates","--root",str(self.tmp),"--input","bundle.json","--agent-id","test-agent","--workspace-id","test-workspace")[1]["data"]
        self.assertEqual(data["quarantine"][0]["reason_code"],"causality_not_direct")
        fresh,_=self.inference_bundle(explicit=True); self.save("bundle.json",fresh)
        data=self.run_cli("validate-inference-candidates","--root",str(self.tmp),"--input","bundle.json","--agent-id","test-agent","--workspace-id","test-workspace")[1]["data"]
        self.assertEqual(data["quarantine"][0]["reason_code"],"shadowed_by_explicit"); self.assertEqual(data["accepted_candidates"],[])


if __name__ == "__main__":
    unittest.main()
