from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap.py"
SPEC = importlib.util.spec_from_file_location("bootstrap", SCRIPT)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


class BootstrapTests(unittest.TestCase):
    def test_installs_both_bootstrap_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skills = Path(directory) / "skills"
            harnesses = Path(directory) / "harnesses"
            entries = bootstrap.load_entries()

            skill_result = bootstrap.install_one(entries[("skill", "clawpod-capability-registry")], skills, harnesses, dry_run=False, force=False)
            harness_result = bootstrap.install_one(entries[("harness", "clawpod-capability-registry")], skills, harnesses, dry_run=False, force=False)

            self.assertEqual(skill_result["status"], "installed")
            self.assertEqual(harness_result["status"], "installed")
            self.assertTrue((skills / "clawpod-capability-registry" / "SKILL.md").is_file())
            self.assertTrue((harnesses / "clawpod-capability-registry" / "harness.json").is_file())
            self.assertTrue((harnesses / "clawpod-capability-registry" / "clawpod_capability_registry.py").is_file())

            again = bootstrap.install_one(entries[("skill", "clawpod-capability-registry")], skills, harnesses, dry_run=False, force=False)
            self.assertEqual(again["status"], "already-installed")

    def test_force_backs_up_different_installation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skills = Path(directory) / "skills"
            harnesses = Path(directory) / "harnesses"
            destination = skills / "clawpod-capability-registry"
            destination.mkdir(parents=True)
            (destination / "SKILL.md").write_text("modified", encoding="utf-8")
            entry = bootstrap.load_entries()[("skill", "clawpod-capability-registry")]

            with self.assertRaisesRegex(bootstrap.BootstrapError, "different content"):
                bootstrap.install_one(entry, skills, harnesses, dry_run=False, force=False)

            result = bootstrap.install_one(entry, skills, harnesses, dry_run=False, force=True)
            self.assertEqual(result["status"], "installed")
            self.assertIsNotNone(result["backup"])
            self.assertEqual(Path(result["backup"]).joinpath("SKILL.md").read_text(encoding="utf-8"), "modified")

    def test_cli_dry_run_emits_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    str(SCRIPT),
                    "--skills-root",
                    str(Path(directory) / "skills"),
                    "--harnesses-root",
                    str(Path(directory) / "harnesses"),
                    "--dry-run",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual([item["status"] for item in payload["results"]], ["would-install", "would-install"])


if __name__ == "__main__":
    unittest.main()
