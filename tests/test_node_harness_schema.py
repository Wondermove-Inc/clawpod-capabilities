"""Node Harness schemas must pass execution preparation, not just discovery."""

import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "harnesses/clawpod-node-host"
# Pinned execution contract in Agent src/agents/harness-lifecycle/run-intent.ts,
# assertSupportedSimpleJsonSchema (audited at a8e3badf22). This is stricter than
# manifest discovery. Update only after verifying the oldest supported runner.
SUPPORTED_KEYS = {"type", "required", "properties", "additionalProperties"}


class NodeHarnessSchemaTests(unittest.TestCase):
    def test_all_command_input_and_output_schemas_support_execution(self):
        manifest = json.loads((PACKAGE / "harness.json").read_text())

        def check(schema, label):
            self.assertIsInstance(schema, dict, label)
            self.assertFalse(set(schema) - SUPPORTED_KEYS,
                             f"{label}: unsupported execution schema keys {set(schema) - SUPPORTED_KEYS}")
            for name, child in schema.get("properties", {}).items():
                check(child, f"{label}.{name}")

        self.assertEqual(set(manifest["commands"]), {"agent.status", "agent.login", "installer.info"})
        for name, command in manifest["commands"].items():
            for field in ("inputSchema", "outputSchema"):
                with self.subTest(command=name, field=field):
                    check(command[field], f"{name}.{field}")

    def test_prepare_and_execute_against_actual_agent_source(self):
        source = os.environ.get("CLAWPOD_AGENT_SOURCE")
        if not source:
            self.skipTest("set CLAWPOD_AGENT_SOURCE for the actual Agent prepare/run integration")
        source = Path(source).resolve()
        result = subprocess.run(
            [str(source / "node_modules/.bin/tsx"),
             str(ROOT / "tests/fixtures/node-harness-runtime.mjs"), str(source), str(ROOT)],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual(evidence, {"preparedCommands": 3, "successfulRuns": 12,
                                   "legacyRejected": 2, "invalidRejected": 5})


if __name__ == "__main__":
    unittest.main()
