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

    def test_empty_registry_is_valid(self) -> None:
        result = self.run_validator(ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validated 0 capability entries", result.stdout)

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


if __name__ == "__main__":
    unittest.main()
