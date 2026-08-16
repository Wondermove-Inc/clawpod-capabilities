"""Release-version invariants for every connected Skill/Harness capability.

Only the distributable capability release is compared here.  Schema, API,
protocol, dependency, upstream/IP, workflow-policy, and semantic-contract
versions intentionally have independent lifecycles and are out of scope.
"""

from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMVER = r"[0-9]+\.[0-9]+\.[0-9]+"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assigned_string(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = ast.literal_eval(node.value)
                    if isinstance(value, str):
                        return value
    raise AssertionError(f"{path.relative_to(ROOT)} has no string {name}")


class ReleaseVersionIntegrityTests(unittest.TestCase):
    def test_all_connected_release_surfaces_are_aligned(self) -> None:
        registry = load(ROOT / "registry/index.json")["capabilities"]
        entries = {(item["type"], item["id"]): item for item in registry}
        skill_ids = sorted(path.parent.name for path in (ROOT / "skills").glob("*/capability.json"))
        self.assertEqual(20, len(skill_ids), "connected-capability inventory changed")

        failures: list[str] = []

        def expect(capability_id: str, surface: str, actual: str, expected: str) -> None:
            if actual != expected:
                failures.append(f"{capability_id}: {surface}={actual}, release={expected}")

        for capability_id in skill_ids:
            skill = load(ROOT / "skills" / capability_id / "capability.json")
            harness_dir = ROOT / "harnesses" / capability_id
            package = load(harness_dir / "capability.json")
            manifest = load(harness_dir / "harness.json")
            release = package["version"]
            skill_entry = entries[("skill", capability_id)]
            harness_entry = entries[("harness", capability_id)]

            expect(capability_id, "harness manifest", manifest["version"], release)
            expect(capability_id, "Harness Registry entry", harness_entry["version"], release)
            expect(capability_id, "Skill Registry entry", skill_entry["version"], skill["version"])
            expect(capability_id, "Skill linkedHarness", skill["linkedHarness"]["version"], release)
            expect(capability_id, "Registry linkedHarness", skill_entry["linkedHarness"]["version"], release)

            readme = harness_dir / "README.md"
            if readme.is_file():
                match = re.search(rf"\bVersion ({SEMVER})\b", readme.read_text(encoding="utf-8"), re.I)
                if match:
                    expect(capability_id, "README current release", match.group(1), release)

            entrypoint = harness_dir / manifest["entrypoint"]
            runtime_name = "VERSION"
            if capability_id == "clawpod-cloud-webhooks":
                runtime_name = "__version__"
                entrypoint = harness_dir / "cli_anything/clawpod_cloud_webhooks/__init__.py"
            elif capability_id == "memory-graph":
                # CONTRACT_VERSION is the legacy release identifier.  The explicitly
                # named semantic/inference/assertion contract versions are excluded.
                runtime_name = "CONTRACT_VERSION"
            try:
                runtime = assigned_string(entrypoint, runtime_name)
            except AssertionError:
                runtime = None
            if runtime is not None:
                expect(capability_id, f"runtime {runtime_name}", runtime, release)

            setup = harness_dir / "setup.py"
            if setup.is_file():
                match = re.search(rf"\bversion=[\"']({SEMVER})[\"']", setup.read_text(encoding="utf-8"))
                self.assertIsNotNone(match, f"{setup.relative_to(ROOT)} must declare a literal version")
                expect(capability_id, "setup.py", match.group(1), release)

            for generator in sorted((harness_dir / "scripts").glob("generate_*.py")):
                matches = re.findall(rf"[\"']version[\"']\s*:\s*[\"']({SEMVER})[\"']", generator.read_text(encoding="utf-8"))
                if matches:
                    for value in set(matches):
                        expect(capability_id, f"generator {generator.name}", value, release)

        self.assertFalse(failures, "release-version drift:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
