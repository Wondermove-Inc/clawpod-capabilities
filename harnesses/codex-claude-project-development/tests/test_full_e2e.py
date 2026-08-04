from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class InstalledPackageE2ETests(unittest.TestCase):
    def test_generated_registry_pair_installs_and_runs_onboarding(self) -> None:
        registry = json.loads((ROOT / "registry" / "index.json").read_text(encoding="utf-8"))
        entries = {(item["type"], item["id"]): item for item in registry["capabilities"]}
        old_name = "acp-" + "project-continuity"
        self.assertNotIn(("skill", old_name), entries)
        self.assertNotIn(("harness", old_name), entries)
        self.assertFalse((ROOT / "skills" / old_name).exists())
        self.assertFalse((ROOT / "harnesses" / old_name).exists())
        skill = entries[("skill", "codex-claude-project-development")]
        harness = entries[("harness", "codex-claude-project-development")]
        self.assertEqual(skill["linkedHarness"], {"id": "codex-claude-project-development", "version": "0.2.1"})
        self.assertEqual(skill["id"], harness["id"])
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            installed_skill = base / "skills" / skill["id"]
            installed_harness = base / "harnesses" / harness["id"]
            for entry, destination in ((skill, installed_skill), (harness, installed_harness)):
                destination.mkdir(parents=True)
                source = ROOT / entry["path"]
                for item in entry["files"]:
                    output = destination / item["path"]
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source / item["path"], output)
            skill_text = (installed_skill / "SKILL.md").read_text(encoding="utf-8")
            onboarding_text = (installed_skill / "references" / "onboarding.md").read_text(encoding="utf-8")
            shared_text = (installed_skill / "references" / "shared-storage.md").read_text(encoding="utf-8")
            self.assertIn("Immediately after installing", skill_text)
            self.assertIn("name: codex-claude-project-development", skill_text)
            self.assertIn("# Codex & Claude Project Development", skill_text)
            self.assertIn("Codex", skill_text)
            self.assertIn("Claude", skill_text)
            self.assertIn('sessions ensure --name', skill_text)
            self.assertIn("installed but not connected", onboarding_text)
            self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", onboarding_text)
            self.assertIn("exec.useSecrets", onboarding_text)
            self.assertIn("connected", onboarding_text)
            self.assertIn("verified", onboarding_text)
            self.assertIn("resume Codex & Claude Project Development onboarding", onboarding_text)
            self.assertIn("/workspace/shared/<org-id>/common/acp-projects/<project-id>/", shared_text)
            self.assertIn("Never place Git repositories", shared_text)
            self.assertTrue((installed_skill / "agents" / "openai.yaml").is_file())
            executable = installed_harness / "codex_claude_project_development.py"
            status = subprocess.run([str(executable), "status"], text=True, capture_output=True, check=False)
            self.assertEqual(status.returncode, 0, status.stderr)
            status_data = json.loads(status.stdout)["data"]
            self.assertEqual(status_data["name"], "codex-claude-project-development")
            manifest = json.loads((installed_harness / "harness.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["name"], status_data["name"])
            self.assertEqual(manifest["title"], "Codex & Claude Project Development")
            self.assertEqual(set(manifest["authModel"]), {"type", "storesSecrets", "requiresHumanAccount"})
            supported_arg_types = {"positional", "option", "booleanFlag", "repeatableOption"}
            for command in manifest["commands"].values():
                self.assertTrue(all(item["type"] in supported_arg_types for item in command["argMap"]))
            self.assertEqual(status_data["backend"], "bundled-acpx-named-sessions")
            self.assertFalse(status_data["gatewayCalls"])
            state_root = base / "state"
            state_root.mkdir()
            state = state_root / "state.json"
            onboard = subprocess.run([str(executable), "onboard", "--state-file", str(state), "--state-root", str(state_root), "--agent", "both", "--expected-revision", "0"], text=True, capture_output=True, check=False)
            self.assertEqual(onboard.returncode, 0, onboard.stderr)
            self.assertEqual(json.loads(onboard.stdout)["data"]["agents"], ["claude", "codex"])
            self.assertEqual(stat_mode(state), 0o600)


def stat_mode(path: Path) -> int:
    return os.stat(path).st_mode & 0o777


if __name__ == "__main__":
    unittest.main()
