"""Harness entrypoints are spawned directly by the Gateway, so the committed file mode matters."""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HarnessEntrypointTests(unittest.TestCase):
    def entrypoints(self):
        for manifest in sorted(ROOT.glob("harnesses/*/harness.json")):
            entry = json.loads(manifest.read_text(encoding="utf-8"))["entrypoint"]
            yield (manifest.parent / entry).resolve().relative_to(ROOT).as_posix()

    def test_entrypoints_start_with_a_shebang(self):
        for path in self.entrypoints():
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).read_bytes().startswith(b"#!"), path)

    @unittest.skipUnless(shutil.which("git") and (ROOT / ".git").exists(), "git checkout required")
    def test_entrypoints_are_committed_executable(self):
        for path in self.entrypoints():
            with self.subTest(path=path):
                listed = subprocess.run(["git", "ls-files", "-s", "--", path], cwd=ROOT, capture_output=True, text=True, check=True).stdout
                self.assertTrue(listed.startswith("100755 "), f"{path} is committed as {listed.split()[:1]}; run git update-index --chmod=+x")


if __name__ == "__main__":
    unittest.main()
