from __future__ import annotations

import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "clawpod_capability_registry.py"
SPEC=importlib.util.spec_from_file_location("registry_e2e",CLI);assert SPEC and SPEC.loader
cap=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(cap)


class EndToEndTests(unittest.TestCase):
    def test_local_list_shape_without_network(self) -> None:
        fixture={"id":"example","type":"skill","version":"1.0.0","description":"Local deterministic fixture.","path":"skills/example","compatibility":{"openclaw":">=2026.4.0"},"safety":{"risk":"read-only","approvalRequired":False},"files":[{"path":"SKILL.md","sha256":"0"*64}]}
        with patch.object(cap,"entries",return_value=[fixture]):
            args=cap.build_parser().parse_args(["list"])
            result=cap.run(args)
        self.assertEqual(result["repository"],"Wondermove-Inc/clawpod-capabilities")
        self.assertEqual(result["capabilities"][0]["type"],"skill")
        self.assertEqual(result["capabilities"][0]["fileCount"],1)

    def test_not_found_is_structured_json(self) -> None:
        # `inspect` reaches selection before any filesystem mutation; replace the
        # canonical read with an empty deterministic registry to prohibit network.
        with patch.object(cap,"entries",return_value=[]):
            args=cap.build_parser().parse_args(["inspect","--id","missing","--type","skill"])
            with self.assertRaises(cap.CapabilityError) as raised:
                cap.run(args)
        self.assertEqual(raised.exception.code,"not_found")


if __name__ == "__main__":
    unittest.main()
