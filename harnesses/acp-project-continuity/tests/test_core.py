from __future__ import annotations

import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("acp_project_continuity", PACKAGE / "acp_project_continuity.py")
assert SPEC and SPEC.loader
cap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cap)


class ContinuityCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "repo"
        self.cwd = self.repo / "work"
        self.state_root = self.root / "state"
        self.cwd.mkdir(parents=True)
        self.state_root.mkdir()
        self.state = self.state_root / "continuity.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def invoke(self, *arguments: str):
        args = cap.build_parser().parse_args(list(arguments))
        return cap.run(args)

    def store(self) -> list[str]:
        return ["--state-file", str(self.state), "--state-root", str(self.state_root)]

    def context(self, agent: str = "codex", branch: str = "main") -> list[str]:
        return [*self.store(), "--project-id", "project-1", "--workspace-root", str(self.root), "--repo", str(self.repo), "--cwd", str(self.cwd), "--branch", branch, "--agent", agent]

    def onboard(self, agent: str = "both", revision: int = 0):
        return self.invoke("onboard", *self.store(), "--agent", agent, "--expected-revision", str(revision))

    def register(self, revision: int = 1):
        context = self.context()
        del context[-2:]  # remove --agent codex
        return self.invoke("project-register", *context, "--expected-revision", str(revision))

    def test_status_and_mandatory_onboarding_are_discoverable(self) -> None:
        status = self.invoke("status")
        self.assertTrue(status["pureLocal"])
        self.assertFalse(status["network"] or status["gatewayCalls"] or status["vendorCalls"])
        with self.assertRaisesRegex(cap.Failure, "post-install onboard"):
            self.invoke("project-list", *self.store())
        result = self.onboard("both")
        self.assertEqual(result["agents"], ["claude", "codex"])
        self.assertIn("protected runtime", result["runtimeInjection"])

    def test_separate_lineages_context_rotation_close_and_no_fallback(self) -> None:
        self.onboard()
        self.register()
        self.invoke("session-attach", *self.context("codex"), "--session-id", "codex-1", "--expected-revision", "2")
        self.invoke("session-attach", *self.context("claude"), "--session-id", "claude-1", "--expected-revision", "3")
        self.assertEqual(self.invoke("session-resolve", *self.context("codex"))["resumeSessionId"], "codex-1")
        self.assertEqual(self.invoke("session-resolve", *self.context("claude"))["resumeSessionId"], "claude-1")
        with self.assertRaisesRegex(cap.Failure, "does not match"):
            self.invoke("session-validate", *self.context(), "--session-id", "wrong")
        with self.assertRaisesRegex(cap.Failure, "does not match project"):
            self.invoke("session-resolve", *self.context(branch="other"))
        rotated = self.invoke("session-rotate", *self.context(), "--session-id", "codex-2", "--expected-revision", "4")
        self.assertEqual(rotated["generation"], 2)
        self.invoke("session-close", *self.context(), "--expected-revision", "5")
        with self.assertRaisesRegex(cap.Failure, "no active session"):
            self.invoke("session-resolve", *self.context())

    def test_revision_and_lease_concurrency(self) -> None:
        self.onboard("codex")
        self.register()
        with self.assertRaisesRegex(cap.Failure, "stale"):
            self.invoke("session-attach", *self.context(), "--session-id", "one", "--expected-revision", "1")
        self.invoke("lease-acquire", *self.context(), "--lease-token", "lease-a", "--now", "10", "--expires-at", "20", "--expected-revision", "2")
        with self.assertRaisesRegex(cap.Failure, "another active lease"):
            self.invoke("lease-acquire", *self.context(), "--lease-token", "lease-b", "--now", "11", "--expires-at", "21", "--expected-revision", "3")
        self.invoke("lease-release", *self.context(), "--lease-token", "lease-a", "--now", "12", "--expected-revision", "3")

    def test_secret_like_inputs_and_state_are_rejected(self) -> None:
        self.onboard()
        with self.assertRaisesRegex(cap.Failure, "branch is invalid"):
            context = self.context(branch="Authorization: bearer value")
            del context[-2:]
            self.invoke("project-register", *context, "--expected-revision", "1")
        self.state.write_text(json.dumps({"schemaVersion": 1, "revision": 1, "onboarding": {"agents": ["codex"], "version": "0.1.0"}, "projects": {"api_key": {}}}), encoding="utf-8")
        os.chmod(self.state, 0o600)
        with self.assertRaisesRegex(cap.Failure, "secret-like"):
            self.invoke("project-list", *self.store())

    def test_corrupt_permissions_path_and_symlink_defenses(self) -> None:
        self.state.write_text("{", encoding="utf-8")
        os.chmod(self.state, 0o600)
        with self.assertRaisesRegex(cap.Failure, "malformed"):
            self.invoke("project-list", *self.store())
        self.state.write_text(json.dumps(cap.empty_state()), encoding="utf-8")
        os.chmod(self.state, 0o644)
        with self.assertRaisesRegex(cap.Failure, "group or others"):
            self.invoke("project-list", *self.store())
        self.state.unlink()
        outside = self.root.parent / "outside-continuity-test.json"
        with self.assertRaisesRegex(cap.Failure, "outside"):
            self.invoke("onboard", "--state-file", str(outside), "--state-root", str(self.state_root), "--agent", "both", "--expected-revision", "0")
        target = self.state_root / "target.json"
        target.write_text(json.dumps(cap.empty_state()), encoding="utf-8")
        os.chmod(target, 0o600)
        self.state.symlink_to(target)
        with self.assertRaisesRegex(cap.Failure, "symlink"):
            self.invoke("project-list", *self.store())


if __name__ == "__main__":
    unittest.main()
