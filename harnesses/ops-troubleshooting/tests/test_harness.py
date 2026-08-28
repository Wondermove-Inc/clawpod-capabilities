"""ops-troubleshooting Harness tests.

Every test runs the CLI as a subprocess against fake tools in an isolated
tool root, so the suite never inspects or mutates the real host or cluster.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "ops_troubleshooting.py"
TESTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ops_troubleshooting", CLI)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

WRAPPER = """#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, {tests!r})
from fake_tools import run
sys.exit(run({tool!r}, sys.argv[1:], Path(__file__).resolve().parent))
"""


class HarnessCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tool_root = Path(self.tmp.name) / "tools"
        self.tool_root.mkdir()
        self.state_root = Path(self.tmp.name) / "state"
        self.state_root.mkdir(mode=0o700)
        for tool in ("kubectl", "systemctl", "journalctl", "ss", "df", "ps", "ip", "last", "find", "apt", "slowtool"):
            self.install_tool(tool)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def install_tool(self, tool: str) -> None:
        path = self.tool_root / tool
        path.write_text(WRAPPER.format(tests=str(TESTS), tool=tool))
        path.chmod(0o755)

    def fake_state(self) -> dict:
        path = self.tool_root / "state.json"
        return json.loads(path.read_text()) if path.exists() else {"calls": []}

    def run_cli(self, *args: str, env: dict | None = None, tool_root: bool = True) -> tuple[dict, int]:
        argv = [sys.executable, str(CLI), *args]
        if tool_root:
            argv += ["--tool-root", str(self.tool_root)]
        completed = subprocess.run(argv, capture_output=True, text=True, cwd=ROOT, env={**os.environ, **(env or {})})
        self.assertTrue(completed.stdout.strip(), completed.stderr)
        return json.loads(completed.stdout), completed.returncode

    def assert_envelope(self, payload: dict, command: str) -> None:
        self.assertEqual(set(payload), {"ok", "schemaVersion", "command", "data", "effects"})
        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(payload["command"], command)
        evidence = payload["data"]["evidence"]
        self.assertEqual(evidence["harnessVersion"], module.VERSION)
        for record in evidence["commands"]:
            self.assertEqual(set(record), {"argv", "exitCode", "durationMs", "truncated", "timedOut"})


class ContractTests(HarnessCase):
    def test_version_self_report(self) -> None:
        payload, code = self.run_cli("version", tool_root=False)
        self.assertEqual(code, 0)
        self.assert_envelope(payload, "version")
        self.assertEqual(payload["data"]["version"], module.VERSION)
        self.assertEqual(payload["data"]["remediationActions"], sorted(module.REMEDIATION_ACTIONS))

    def test_manifest_is_generated_from_the_cli_tables(self) -> None:
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_manifest.py"), "--check"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((ROOT / "harness.json").read_text())
        self.assertEqual(set(manifest["commands"]), set(module.COMMANDS))
        self.assertEqual(manifest["version"], module.VERSION)
        for name, command in manifest["commands"].items():
            self.assertEqual(command["baseArgv"], [name])
            expected = ["readOnly"] if not name.startswith("remediate.") else module.SAFETY[name]
            self.assertEqual(command["safetyClasses"], expected, name)
            flags = {arg["flag"] for arg in command["argMap"]}
            self.assertIn("--tool-root", flags)
            self.assertIn("--timeout-ms", flags)

    def test_only_remediation_commands_carry_side_effect_classes(self) -> None:
        manifest = json.loads((ROOT / "harness.json").read_text())
        for name, command in manifest["commands"].items():
            if name == "remediate.apply":
                self.assertIn("externalSideEffect", command["safetyClasses"])
            else:
                self.assertNotIn("externalSideEffect", command["safetyClasses"], name)
                self.assertNotIn("destructive", command["safetyClasses"], name)

    def test_missing_required_option_is_invalid(self) -> None:
        payload, code = self.run_cli("net.dns")
        self.assertEqual(code, module.EXIT["invalid"])
        self.assertEqual(payload["error"]["code"], "MISSING_OPTION")

    def test_unknown_tool_root_fails_closed(self) -> None:
        payload, code = self.run_cli("host.disk", "--tool-root", "/nonexistent-dir", tool_root=False)
        self.assertEqual(code, module.EXIT["invalid"])
        self.assertEqual(payload["error"]["code"], "INVALID_TOOL_ROOT")

    def test_tool_unavailable_reports_unavailable(self) -> None:
        (self.tool_root / "df").unlink()
        payload, code = self.run_cli("host.disk")
        self.assertEqual(code, module.EXIT["unavailable"])
        self.assertEqual(payload["error"]["code"], "TOOL_UNAVAILABLE")
        self.assertEqual(payload["error"]["details"]["tool"], "df")

    def test_timeout_is_bounded_and_reported(self) -> None:
        (self.tool_root / "kubectl").write_text(WRAPPER.format(tests=str(TESTS), tool="slowtool"))
        payload, code = self.run_cli("k8s.context", "--timeout-ms", "300")
        self.assertEqual(code, module.EXIT["timeout"])
        self.assertEqual(payload["error"]["code"], "TIMEOUT")
        self.assertTrue(payload["data"]["evidence"]["commands"][0]["timedOut"])


class HostTests(HarnessCase):
    def test_disk_findings_for_space_and_inodes(self) -> None:
        payload, code = self.run_cli("host.disk")
        self.assertEqual(code, 0)
        codes = {(f["code"], f["mount"], f["severity"]) for f in payload["data"]["findings"]}
        self.assertIn(("DISK_USAGE_HIGH", "/", "critical"), codes)
        self.assertIn(("INODE_USAGE_HIGH", "/", "critical"), codes)
        self.assertFalse(any(f["mount"] == "/data" for f in payload["data"]["findings"]))

    def test_services_failed_list_and_unit_detail(self) -> None:
        payload, _ = self.run_cli("host.services")
        self.assertEqual(payload["data"]["failedUnits"][0]["unit"], "broken.service")
        payload, _ = self.run_cli("host.services", "--unit", "broken.service")
        codes = {f["code"] for f in payload["data"]["findings"]}
        self.assertEqual(codes, {"UNIT_NOT_ACTIVE", "UNIT_RESTART_LOOP"})

    def test_missing_unit_is_a_precondition_failure(self) -> None:
        payload, code = self.run_cli("host.services", "--unit", "missing")
        self.assertEqual(code, module.EXIT["precondition"])
        self.assertEqual(payload["error"]["code"], "UNIT_NOT_FOUND")

    def test_journal_redacts_secrets_and_accepts_negative_since(self) -> None:
        payload, code = self.run_cli("host.journal", "--since", "-30m", "--tail", "3")
        self.assertEqual(code, 0)
        text = json.dumps(payload)
        self.assertNotIn("abc123SECRET", text)
        self.assertIn("[REDACTED]", text)
        self.assertTrue(payload["data"]["evidence"]["redacted"])
        argv = payload["data"]["evidence"]["commands"][0]["argv"]
        self.assertIn("-1800s", argv)
        self.assertEqual(argv[argv.index("-n") + 1], "3")

    def test_journal_rejects_bad_window_and_caps_tail(self) -> None:
        payload, code = self.run_cli("host.journal", "--since", "yesterday")
        self.assertEqual(code, module.EXIT["invalid"])
        self.assertEqual(payload["error"]["code"], "INVALID_SINCE")
        payload, _ = self.run_cli("host.journal", "--tail", "99999")
        self.assertEqual(payload["data"]["tail"], module.LIMITS["journalTailMax"])

    def test_processes_flag_zombies(self) -> None:
        payload, _ = self.run_cli("host.processes", "--top", "5")
        self.assertEqual(payload["data"]["findings"][0]["code"], "ZOMBIE_PROCESSES")

    def test_change_recent_root_allowlist(self) -> None:
        payload, code = self.run_cli("change.recent", "--root", "/tmp")
        self.assertEqual(code, module.EXIT["invalid"])
        self.assertEqual(payload["error"]["code"], "ROOT_NOT_ALLOWED")
        payload, code = self.run_cli("change.recent", "--root", "/etc", "--since", "1d")
        self.assertEqual(code, 0)
        self.assertEqual(payload["data"]["files"][0]["path"], "/etc/ssh/sshd_config")

    def test_triage_host_aggregates_and_survives_section_failures(self) -> None:
        (self.tool_root / "ss").unlink()
        payload, code = self.run_cli("triage.host")
        self.assertEqual(code, 0)
        sections = payload["data"]["sections"]
        self.assertTrue(sections["disk"]["ok"])
        self.assertFalse(sections["ports"]["ok"])
        self.assertEqual(sections["ports"]["error"]["code"], "TOOL_UNAVAILABLE")
        self.assertGreaterEqual(payload["data"]["summary"]["critical"], 2)
        self.assertTrue(any("ports:" in note for note in payload["data"]["evidence"]["notes"]))


class NetworkAndSecurityTests(HarnessCase):
    def test_ports_report_exposure(self) -> None:
        payload, _ = self.run_cli("net.ports")
        exposed = {(s["protocol"], s["port"]) for s in payload["data"]["exposedToAllInterfaces"]}
        self.assertEqual(exposed, {("tcp", 22), ("udp", 123)})
        self.assertEqual(payload["data"]["listening"][0]["process"], {"name": "sshd", "pid": 700})

    def test_route_findings(self) -> None:
        payload, _ = self.run_cli("net.route")
        codes = {f["code"] for f in payload["data"]["findings"]}
        self.assertEqual(codes, {"NO_DEFAULT_ROUTE", "INTERFACES_DOWN"})

    def test_reach_rejects_bad_port_and_reports_unreachable(self) -> None:
        payload, code = self.run_cli("net.reach", "--host", "127.0.0.1", "--port", "70000")
        self.assertEqual(code, module.EXIT["invalid"])
        payload, code = self.run_cli("net.reach", "--host", "127.0.0.1", "--port", "9", "--timeout-ms", "1000")
        self.assertEqual(code, 0)
        self.assertEqual(payload["data"]["findings"][0]["code"], "TCP_UNREACHABLE")

    def test_auth_events_detect_brute_force(self) -> None:
        payload, _ = self.run_cli("security.auth-events", "--since", "1d")
        self.assertEqual(payload["data"]["stats"]["failedPassword"], 25)
        self.assertEqual(payload["data"]["stats"]["accepted"], 1)
        self.assertEqual(payload["data"]["stats"]["sudo"], 1)
        self.assertEqual(payload["data"]["findings"][0]["code"], "BRUTE_FORCE_SOURCE")
        self.assertEqual(payload["data"]["topFailedSources"][0], {"source": "203.0.113.9", "count": 25})

    def test_logins_and_updates(self) -> None:
        payload, _ = self.run_cli("security.logins")
        self.assertEqual(payload["data"]["bySource"], {"198.51.100.4": 1})
        self.assertIsNone(payload["data"]["sessions"][1]["from"])
        payload, _ = self.run_cli("security.updates")
        self.assertEqual(payload["data"]["securityCount"], 1)
        self.assertEqual(payload["data"]["findings"][0]["code"], "SECURITY_UPDATES_PENDING")


class KubernetesTests(HarnessCase):
    def test_pods_classify_unhealthy_workloads(self) -> None:
        payload, code = self.run_cli("k8s.pods", "--all-namespaces")
        self.assertEqual(code, 0)
        self.assertEqual(payload["data"]["podCount"], 3)
        self.assertEqual(payload["data"]["unhealthyCount"], 2)
        first = payload["data"]["unhealthy"][0]
        self.assertEqual(first["name"], "api-7c9f-crash")
        self.assertEqual(first["issues"], ["CrashLoopBackOff", "OOMKilled(previous)"])
        codes = {f["code"]: f["severity"] for f in payload["data"]["findings"]}
        self.assertEqual(codes["POD_CRASHLOOPBACKOFF"], "critical")
        self.assertEqual(codes["POD_UNSCHEDULABLE_UNSCHEDULABLE"], "critical")
        self.assertIn("-A", payload["data"]["evidence"]["commands"][0]["argv"])

    def test_pods_namespace_and_selector_validation(self) -> None:
        payload, _ = self.run_cli("k8s.pods", "--namespace", "empty")
        self.assertEqual(payload["data"]["podCount"], 0)
        payload, code = self.run_cli("k8s.pods", "--namespace", "Bad_NS")
        self.assertEqual(code, module.EXIT["invalid"])
        payload, code = self.run_cli("k8s.pods", "--selector", "app=api; rm -rf /")
        self.assertEqual(payload["error"]["code"], "INVALID_SELECTOR")

    def test_describe_never_touches_secrets(self) -> None:
        for kind in ("secret", "secrets", "configmap", "cm"):
            payload, code = self.run_cli("k8s.describe", "--kind", kind, "--name", "x", "--namespace", "prod")
            self.assertEqual(code, module.EXIT["invalid"], kind)
            self.assertEqual(payload["error"]["code"], "KIND_NOT_ALLOWED")
            self.assertEqual(payload["data"]["evidence"]["commands"], [])
        payload, code = self.run_cli("k8s.describe", "--kind", "pod", "--name", "api-7c9f-crash", "--namespace", "prod")
        self.assertEqual(code, 0)
        self.assertIn("[REDACTED]", payload["data"]["description"])
        self.assertNotIn("shouldberedacted", payload["data"]["description"])

    def test_events_nodes_rollout_logs(self) -> None:
        payload, _ = self.run_cli("k8s.events", "--namespace", "prod")
        self.assertEqual(payload["data"]["events"][0]["reason"], "FailedScheduling")
        self.assertNotIn("hunter2", json.dumps(payload))
        self.assertIn("type=Warning", payload["data"]["evidence"]["commands"][0]["argv"])

        payload, _ = self.run_cli("k8s.nodes", "--usage")
        codes = {f["code"] for f in payload["data"]["findings"]}
        self.assertEqual(codes, {"NODE_NOT_READY", "NODE_MEMORYPRESSURE"})
        self.assertIsNone(payload["data"]["usage"])
        self.assertTrue(any("top nodes" in note for note in payload["data"]["evidence"]["notes"]))

        payload, _ = self.run_cli("k8s.rollout", "--namespace", "prod", "--name", "api")
        self.assertEqual(payload["data"]["desired"], 3)
        self.assertEqual({f["code"] for f in payload["data"]["findings"]}, {"ROLLOUT_STALLED"})

        payload, _ = self.run_cli("k8s.logs", "--namespace", "prod", "--name", "api-7c9f-crash", "--tail", "50", "--pattern", "ERROR")
        self.assertEqual(payload["data"]["lineCount"], 1)
        self.assertEqual(payload["data"]["errorLikeLines"], 1)
        argv = payload["data"]["evidence"]["commands"][0]["argv"]
        self.assertIn("--tail", argv)
        self.assertIn("--since", argv)

    def test_triage_k8s(self) -> None:
        payload, code = self.run_cli("triage.k8s", "--all-namespaces")
        self.assertEqual(code, 0)
        self.assertTrue(all(section["ok"] for section in payload["data"]["sections"].values()))
        self.assertFalse(payload["data"]["summary"]["healthy"])
        self.assertGreaterEqual(payload["data"]["summary"]["critical"], 3)


class RemediationTests(HarnessCase):
    def plan(self, *args: str) -> dict:
        payload, code = self.run_cli("remediate.plan", "--state-root", str(self.state_root), *args)
        self.assertEqual(code, 0, payload)
        return payload["data"]

    def apply(self, plan_id: str, confirm: str, env: dict | None = None) -> tuple[dict, int]:
        return self.run_cli("remediate.apply", "--state-root", str(self.state_root), "--plan-id", plan_id, "--confirm", confirm, env=env)

    def test_plan_writes_owner_only_file_and_does_not_mutate(self) -> None:
        data = self.plan("--action", "service.restart", "--target", "broken.service", "--reason", "restart loop")
        plan = data["plan"]
        self.assertEqual(data["nextAction"]["kind"], "confirm")
        self.assertEqual(plan["preconditions"]["activeState"], "failed")
        path = self.state_root / "plans" / f"{plan['id']}.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(self.fake_state()["calls"], [])
        self.assertEqual(plan["commands"][0], "systemctl restart broken.service")

    def test_apply_requires_exact_confirmation(self) -> None:
        plan = self.plan("--action", "service.restart", "--target", "broken.service")["plan"]
        payload, code = self.apply(plan["id"], "nope")
        self.assertEqual(code, module.EXIT["confirmation_required"])
        self.assertEqual(payload["error"]["code"], "CONFIRMATION_MISMATCH")
        self.assertEqual(self.fake_state()["calls"], [])

    def test_apply_rejects_expired_plan(self) -> None:
        plan = self.plan("--action", "service.restart", "--target", "broken.service")["plan"]
        payload, code = self.apply(plan["id"], plan["confirmationChallenge"], env={"OPS_TROUBLESHOOTING_NOW": "2099-01-01T00:00:00Z"})
        self.assertEqual(code, module.EXIT["confirmation_required"])
        self.assertEqual(payload["error"]["code"], "PLAN_EXPIRED")

    def test_apply_rejects_stale_preconditions(self) -> None:
        plan = self.plan("--action", "k8s.rollout.restart", "--target", "deployment/api", "--namespace", "prod")["plan"]
        state = self.fake_state()
        state["deploymentGeneration"] = 8
        (self.tool_root / "state.json").write_text(json.dumps(state))
        payload, code = self.apply(plan["id"], plan["confirmationChallenge"])
        self.assertEqual(code, module.EXIT["precondition"])
        self.assertEqual(payload["error"]["code"], "PLAN_STALE")
        self.assertEqual(payload["error"]["details"]["current"]["generation"], 8)
        self.assertEqual(self.fake_state()["calls"], [])

    def test_apply_runs_once_verifies_and_consumes_plan(self) -> None:
        plan = self.plan("--action", "service.restart", "--target", "broken.service")["plan"]
        payload, code = self.apply(plan["id"], plan["confirmationChallenge"])
        self.assertEqual(code, 0, payload)
        self.assertTrue(payload["data"]["verified"])
        self.assertEqual(payload["effects"], ["restarted systemd unit broken.service"])
        self.assertEqual(self.fake_state()["calls"], ["restart broken.service"])
        payload, code = self.apply(plan["id"], plan["confirmationChallenge"])
        self.assertEqual(code, module.EXIT["confirmation_required"])
        self.assertEqual(payload["error"]["code"], "PLAN_CONSUMED")
        self.assertEqual(len(self.fake_state()["calls"]), 1)

    def test_rollout_restart_and_pod_delete_paths(self) -> None:
        plan = self.plan("--action", "k8s.rollout.restart", "--target", "deployment/api", "--namespace", "prod")["plan"]
        payload, code = self.apply(plan["id"], plan["confirmationChallenge"])
        self.assertEqual(code, 0, payload)
        self.assertIn("rollout restart deployment/api", self.fake_state()["calls"][0])
        self.assertTrue(payload["data"]["verified"])

        payload, code = self.run_cli("remediate.plan", "--state-root", str(self.state_root), "--action", "k8s.pod.delete", "--target", "debug-shell", "--namespace", "prod")
        self.assertEqual(code, module.EXIT["precondition"])
        self.assertEqual(payload["error"]["code"], "POD_UNMANAGED")

        plan = self.plan("--action", "k8s.pod.delete", "--target", "api-7c9f-crash", "--namespace", "prod")["plan"]
        self.assertEqual(plan["preconditions"]["ownerKind"], "ReplicaSet")
        payload, code = self.apply(plan["id"], plan["confirmationChallenge"])
        self.assertEqual(code, 0, payload)
        self.assertIn("delete pod api-7c9f-crash --wait=false", self.fake_state()["calls"][-1])

    def test_action_and_target_validation(self) -> None:
        payload, code = self.run_cli("remediate.plan", "--state-root", str(self.state_root), "--action", "k8s.rollout.restart", "--target", "secret/x", "--namespace", "prod")
        self.assertEqual(code, module.EXIT["invalid"])
        self.assertEqual(payload["error"]["code"], "KIND_NOT_ALLOWED")
        payload, code = self.run_cli("remediate.plan", "--state-root", str(self.state_root), "--action", "k8s.rollout.restart", "--target", "deployment/api")
        self.assertEqual(payload["error"]["code"], "INVALID_NAMESPACE")

    def test_state_root_must_be_owner_only(self) -> None:
        self.state_root.chmod(0o755)
        payload, code = self.run_cli("remediate.plan", "--state-root", str(self.state_root), "--action", "service.restart", "--target", "broken.service")
        self.assertEqual(code, module.EXIT["precondition"])
        self.assertEqual(payload["error"]["code"], "UNSAFE_STATE")


if __name__ == "__main__":
    unittest.main()
