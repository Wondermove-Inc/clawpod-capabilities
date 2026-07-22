from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "clawpod_capability_registry.py"


class EndToEndTests(unittest.TestCase):
    def test_real_canonical_registry_list(self) -> None:
        result = subprocess.run(
            [str(CLI), "list"],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "list")
        self.assertEqual(payload["data"]["repository"], "Wondermove-Inc/clawpod-capabilities")
        self.assertIsInstance(payload["data"]["capabilities"], list)

    def test_not_found_is_structured_json(self) -> None:
        result = subprocess.run(
            [str(CLI), "inspect", "--id", "capability-that-does-not-exist"],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "not_found")


if __name__ == "__main__":
    unittest.main()
