from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ValidatorTests(unittest.TestCase):
    def run_validator(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "scripts/validate.py"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_repository_registry_is_valid(self) -> None:
        result = self.run_validator(ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validated 2 capability entries", result.stdout)

    def test_invalid_entry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "repo"
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            index = copy / "registry" / "index.json"
            data = json.loads(index.read_text(encoding="utf-8"))
            data["capabilities"] = [{"id": "Bad Name"}]
            index.write_text(json.dumps(data), encoding="utf-8")

            result = self.run_validator(copy)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing fields", result.stderr)

    def test_skill_frontmatter_name_must_match_registry_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "repo"
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            skill = copy / "skills" / "clawpod-capability-registry" / "SKILL.md"
            text = skill.read_text(encoding="utf-8")
            skill.write_text(text.replace("name: clawpod-capability-registry", "name: wrong-name", 1), encoding="utf-8")

            result = self.run_validator(copy)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match SKILL.md name", result.stderr)


if __name__ == "__main__":
    unittest.main()
