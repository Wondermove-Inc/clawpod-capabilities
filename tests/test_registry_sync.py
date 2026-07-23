from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RegistrySyncTests(unittest.TestCase):
    def run_sync(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(ROOT / "scripts" / "sync_registry.py"), "--root", str(root), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )

    def copy_repository(self, directory: str) -> Path:
        copy = Path(directory) / "repo"
        shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        return copy

    def test_repository_registry_is_synchronized(self) -> None:
        result = self.run_sync(ROOT, "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("is synchronized", result.stdout)

    def test_all_skill_packages_declare_exact_linked_harness_versions(self) -> None:
        registry=json.loads((ROOT / "registry" / "index.json").read_text(encoding="utf-8"))
        entries={(e["type"],e["id"],e["version"]) for e in registry["capabilities"]}
        skills=[e for e in registry["capabilities"] if e["type"]=="skill"]
        self.assertTrue(skills)
        for skill in skills:
            linked=skill.get("linkedHarness")
            self.assertEqual(set(linked or {}),{"id","version"})
            self.assertIn(("harness",linked["id"],linked["version"]),entries)
        registry_skill=next(e for e in skills if e["id"]=="clawpod-capability-registry")
        self.assertEqual(registry_skill["version"],"0.2.1")
        self.assertEqual(registry_skill["linkedHarness"]["version"],"0.2.1")
        atlassian=next(e for e in skills if e["id"]=="atlassian")
        self.assertNotEqual(atlassian["version"],atlassian["linkedHarness"]["version"])

    def test_changed_package_file_makes_registry_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copy = self.copy_repository(directory)
            skill = copy / "skills" / "clawpod-capability-registry" / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\n", encoding="utf-8")

            stale = self.run_sync(copy, "--check")
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("registry/index.json is stale", stale.stderr)

            update = self.run_sync(copy)
            self.assertEqual(update.returncode, 0, update.stderr)
            self.assertEqual(self.run_sync(copy, "--check").returncode, 0)

    def test_new_package_directory_is_discovered_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copy = self.copy_repository(directory)
            package = copy / "skills" / "example-skill"
            package.mkdir()
            (package / "SKILL.md").write_text(
                "---\nname: example-skill\ndescription: Use for testing automatic registry discovery of a new skill package.\n---\n\n# Example\n",
                encoding="utf-8",
            )
            (package / "capability.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "version": "1.0.0",
                        "description": "Example capability used to verify automatic registry package discovery.",
                        "compatibility": {"openclaw": ">=2026.4.0", "platforms": ["linux"]},
                        "safety": {"risk": "read-only", "approvalRequired": False},
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_sync(copy)
            self.assertEqual(result.returncode, 0, result.stderr)
            registry = json.loads((copy / "registry" / "index.json").read_text(encoding="utf-8"))
            entry = next(item for item in registry["capabilities"] if item["id"] == "example-skill")
            self.assertEqual(entry["type"], "skill")
            self.assertEqual(entry["files"][0]["path"], "SKILL.md")
            self.assertEqual(len(entry["files"][0]["sha256"]), 64)

    def test_package_without_metadata_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copy = self.copy_repository(directory)
            package = copy / "skills" / "missing-metadata"
            package.mkdir()
            (package / "SKILL.md").write_text(
                "---\nname: missing-metadata\ndescription: This package intentionally omits registry metadata for testing.\n---\n",
                encoding="utf-8",
            )

            result = self.run_sync(copy)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing file", result.stderr)


if __name__ == "__main__":
    unittest.main()
