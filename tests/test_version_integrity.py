from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMVER = r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?"

# These are deliberately named release-version surfaces.  Do not broaden this
# list to API, schema, protocol, dependency, workflow-policy, or semantic-
# contract versions merely because their names or values contain "version".
RUNTIME_CONSTANTS = {
    "claude-design": ("claude_design.py", "VERSION"),
    "clawpod-image-studio": ("clawpod_image_studio.py", "VERSION"),
    "clawpod-ocr": ("clawpod_ocr.py", "VERSION"),
    "clawpod-video-studio": ("clawpod_video_studio.py", "VERSION"),
    "cloudflare-quick-tunnel-preview": ("cloudflare_quick_tunnel_preview.py", "VERSION"),
    "enterprise-newsletter": ("enterprise_newsletter.py", "VERSION"),
    "memory-graph": ("memory_graph.py", "CONTRACT_VERSION"),
    "resend-email": ("resend_email.py", "VERSION"),
    "youtube-evidence-analysis": ("youtube_evidence_analysis.py", "VERSION"),
}
RUNTIME_LITERALS = {
    "verified-research": ("verified_research.py", r"'provenance':\{'tool':'verified-research','version':'(" + SEMVER + r")'"),
}
PACKAGE_VERSION_SURFACES = {
    "clawpod-cloud-webhooks": (
        ("cli_anything/clawpod_cloud_webhooks/__init__.py", "__version__"),
        ("setup.py", "version"),
    ),
}
GENERATORS = {
    "atlassian": "scripts/generate_schemas.py",
    "github": "scripts/generate_schemas.py",
    "resend-email": "scripts/generate_manifest.py",
    "verified-research": "scripts/generate_schemas.py",
    "youtube-evidence-analysis": "scripts/generate_schemas.py",
}
SELF_REPORTS = {
    "claude-design": ("system.version", []),
    "clawpod-cloud-webhooks": ("system.version", []),
    "clawpod-ocr": ("system.version", []),
    "clawpod-video-studio": ("system.version", []),
    "cloudflare-quick-tunnel-preview": ("status", ["--state-root", "{state_root}"]),
    "enterprise-newsletter": ("status", []),
    "resend-email": ("status", []),
    "youtube-evidence-analysis": ("status", []),
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assigned_string(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            for keyword in node.value.keywords:
                if keyword.arg == name and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    return keyword.value.value
    raise AssertionError(f"{path}: no literal assignment for {name}")


class CandidateFinalVersionIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load(ROOT / "registry/index.json")
        self.entries = {(item["type"], item["id"]): item for item in self.registry["capabilities"]}
        self.ids = sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir())

    def test_all_release_units_have_exact_metadata_and_registry_versions(self) -> None:
        self.assertTrue(self.ids)
        harness_ids = sorted(path.name for path in (ROOT / "harnesses").iterdir() if path.is_dir())
        self.assertTrue(set(harness_ids).issubset(self.ids))
        for capability_id in self.ids:
            skill = load(ROOT / "skills" / capability_id / "capability.json")
            self.assertEqual(self.entries[("skill", capability_id)]["version"], skill["version"], capability_id)
            if capability_id not in harness_ids:
                self.assertNotIn("linkedHarness", skill, capability_id)
                self.assertNotIn("linkedHarness", self.entries[("skill", capability_id)], capability_id)
                continue
            harness = load(ROOT / "harnesses" / capability_id / "capability.json")
            manifest = load(ROOT / "harnesses" / capability_id / "harness.json")
            linked = skill.get("linkedHarness")
            self.assertEqual(linked, {"id": capability_id, "version": harness["version"]}, capability_id)
            self.assertEqual(manifest["version"], harness["version"], capability_id)
            self.assertEqual(self.entries[("skill", capability_id)]["linkedHarness"], linked, capability_id)
            self.assertEqual(self.entries[("harness", capability_id)]["version"], harness["version"], capability_id)

    def test_known_executable_release_versions_equal_manifest(self) -> None:
        for capability_id, (relative, constant) in RUNTIME_CONSTANTS.items():
            package = ROOT / "harnesses" / capability_id
            with self.subTest(capability_id=capability_id, surface=relative):
                self.assertEqual(assigned_string(package / relative, constant), load(package / "harness.json")["version"], capability_id)
        for capability_id, (relative, pattern) in RUNTIME_LITERALS.items():
            package = ROOT / "harnesses" / capability_id
            with self.subTest(capability_id=capability_id, surface=relative):
                match = re.search(pattern, (package / relative).read_text(encoding="utf-8"))
                self.assertIsNotNone(match, capability_id)
                self.assertEqual(match.group(1), load(package / "harness.json")["version"], capability_id)

    def test_package_versions_equal_manifest(self) -> None:
        for capability_id, surfaces in PACKAGE_VERSION_SURFACES.items():
            package = ROOT / "harnesses" / capability_id
            expected = load(package / "harness.json")["version"]
            for relative, name in surfaces:
                with self.subTest(capability_id=capability_id, surface=relative):
                    self.assertEqual(assigned_string(package / relative, name), expected, f"{capability_id}:{relative}")

    def test_current_readme_and_skill_release_declarations_equal_manifest(self) -> None:
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for capability_id in self.ids:
            package = ROOT / "harnesses" / capability_id
            if not package.is_dir():
                continue
            expected = load(package / "harness.json")["version"]
            readme = package / "README.md"
            if readme.exists():
                match = re.search(r"\bVersion (" + SEMVER + r")\b", readme.read_text(encoding="utf-8"))
                if match:
                    with self.subTest(capability_id=capability_id, surface="README.md"):
                        self.assertEqual(match.group(1), expected, f"{capability_id}:README.md current release line")
            skill_text = (ROOT / "skills" / capability_id / "SKILL.md").read_text(encoding="utf-8")
            match = re.search(r"\bHarness (?:v|(?:\(version |version ))(" + SEMVER + r")\)?", skill_text)
            if match:
                with self.subTest(capability_id=capability_id, surface="SKILL.md"):
                    self.assertEqual(match.group(1), expected, f"{capability_id}:SKILL.md linked Harness declaration")
            title = load(package / "harness.json")["title"]
            match = re.search(r"^### " + re.escape(title) + r" (" + SEMVER + r")$", root_readme, re.MULTILINE)
            if match:
                with self.subTest(capability_id=capability_id, surface="root README.md"):
                    self.assertEqual(match.group(1), expected, f"{capability_id}:root README release line")

    def test_manifest_generators_preserve_release_version(self) -> None:
        for capability_id, generator in GENERATORS.items():
            source = ROOT / "harnesses" / capability_id
            with self.subTest(capability_id=capability_id), tempfile.TemporaryDirectory() as directory:
                package = Path(directory) / capability_id
                shutil.copytree(source, package)
                expected = load(package / "capability.json")["version"]
                result = subprocess.run(
                    ["python3", generator], cwd=package, text=True, capture_output=True, check=False
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(load(package / "harness.json")["version"], expected, capability_id)

    def test_credential_free_version_and_status_self_reports_are_exact(self) -> None:
        def release_values(value: object) -> list[str]:
            if isinstance(value, dict):
                return [
                    child
                    for key, item in value.items()
                    for child in (([item] if key in {"version", "capabilityVersion"} and isinstance(item, str) else []) + release_values(item))
                ]
            if isinstance(value, list):
                return [child for item in value for child in release_values(item)]
            return []

        for capability_id, (command, extra) in SELF_REPORTS.items():
            package = ROOT / "harnesses" / capability_id
            manifest = load(package / "harness.json")
            with self.subTest(capability_id=capability_id), tempfile.TemporaryDirectory() as state_root:
                argv = ["python3", manifest["entrypoint"], command, *(item.format(state_root=state_root) for item in extra)]
                result = subprocess.run(argv, cwd=package, text=True, capture_output=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertTrue(report.get("ok"), report)
                values = release_values(report)
                self.assertIn(manifest["version"], values, f"{capability_id} did not self-report its release version")
                self.assertFalse(
                    [value for value in values if re.fullmatch(SEMVER, value) and value != manifest["version"]],
                    f"{capability_id} emitted a conflicting release version: {values}",
                )


if __name__ == "__main__":
    unittest.main()
