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
        skill = entries[("skill", "acp-project-continuity")]
        harness = entries[("harness", "acp-project-continuity")]
        self.assertEqual(skill["linkedHarness"], {"id": "acp-project-continuity", "version": "0.1.0"})
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
            self.assertIn("Codex", skill_text)
            self.assertIn("Claude", skill_text)
            self.assertIn('resumeSessionId', skill_text)
            self.assertIn("installed but not connected", onboarding_text)
            self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", onboarding_text)
            self.assertIn("protected memory-secret", onboarding_text)
            self.assertIn("connected", onboarding_text)
            self.assertIn("verified", onboarding_text)
            self.assertIn("resume ACP Project Continuity onboarding", onboarding_text)
            self.assertIn("/workspace/shared/<org-id>/common/acp-projects/<project-id>/", shared_text)
            self.assertIn("Never place Git repositories", shared_text)
            self.assertTrue((installed_skill / "agents" / "openai.yaml").is_file())
            executable = installed_harness / "acp_project_continuity.py"
            status = subprocess.run([str(executable), "status"], text=True, capture_output=True, check=False)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertTrue(json.loads(status.stdout)["data"]["pureLocal"])
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
