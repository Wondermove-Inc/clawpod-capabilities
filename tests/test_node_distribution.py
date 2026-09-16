"""Distribution checks use tiny installer fixtures; no host installation/network."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("node_release", ROOT / "node/prepare_release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class NodeDistributionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.manifest = copy.deepcopy(release.load_manifest())
        for item in self.manifest["artifacts"]:
            data = (item["filename"] + " fixture\n").encode()
            (self.source / item["filename"]).write_bytes(data)
            item["bytes"] = len(data)
            item["sha256"] = hashlib.sha256(data).hexdigest()
        self.destination = self.root / "staged" / "0.1.0"

    def test_canonical_manifest_and_installed_package_agree(self):
        self.assertEqual(release.MANIFEST.read_bytes(), release.BUNDLED.read_bytes())
        run = subprocess.run([sys.executable, str(ROOT / "node/prepare_release.py"), "check"],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_four_targets_have_versioned_public_assets(self):
        manifest = release.load_manifest()
        self.assertEqual({(x["platform"], x["arch"]) for x in manifest["artifacts"]},
                         set(release.TARGETS))
        for item in manifest["artifacts"]:
            self.assertIn("/clawpod-capabilities/releases/download/node-v", item["url"])
            self.assertNotIn("/latest/", item["url"])
        self.assertIs(manifest["signed"], False)
        self.assertEqual(manifest["validation"]["nativeMacOS"], "not-run")
        self.assertEqual(manifest["validation"]["nativeWindows"], "not-run")

    def test_invalid_artifact_signing_metadata(self):
        for update in ({"signed": "true"}, {"notarized": 1}, {"stapled": None},
                       {"signed": False, "notarized": True}, {"notarized": False, "stapled": True}):
            data = copy.deepcopy(self.manifest)
            data["artifacts"][0].update(update)
            path = self.root / "invalid-signing.json"
            path.write_text(json.dumps(data))
            with self.subTest(update=update), self.assertRaises(ValueError):
                release.load_manifest(path)

    def test_registry_installed_harness_uses_its_own_manifest(self):
        spec = importlib.util.spec_from_file_location("node_bootstrap", ROOT / "scripts/bootstrap.py")
        bootstrap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bootstrap)
        entries = json.loads((ROOT / "registry/index.json").read_text())["capabilities"]
        entry = next(x for x in entries if x["type"] == "harness" and x["id"] == "clawpod-node-host")
        skills, harnesses = self.root / "skills", self.root / "harnesses"
        bootstrap.install_one(entry, skills, harnesses, dry_run=False, force=False)
        installed = harnesses / "clawpod-node-host"
        run = subprocess.run([sys.executable, str(installed / "clawpod_node_host.py"),
                              "--json", "installer", "info", "--platform", "linux", "--arch", "x64"],
                             cwd=self.root, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        expected = next(x for x in release.load_manifest()["artifacts"] if x["platform"] == "linux")
        self.assertEqual(result["installer"]["url"], expected["url"])
        self.assertEqual(result["installer"]["sha256"], expected["sha256"])
        self.assertEqual(result["installer"]["manifestSource"], "bundled")

    def test_manifest_rejects_target_version_and_checksum_drift(self):
        for update in ({"url": "https://example.com/installer"},
                       {"filename": "../installer"}, {"sha256": "missing"}, {"bytes": True}):
            data = copy.deepcopy(self.manifest)
            data["artifacts"][0].update(update)
            file = self.root / "invalid.json"
            file.write_text(json.dumps(data))
            with self.subTest(update=update), self.assertRaises(ValueError):
                release.load_manifest(file)

    def test_registry_upgrade_removes_retired_files_from_active_packages(self):
        spec = importlib.util.spec_from_file_location("node_registry_upgrade", ROOT / "harnesses/clawpod-capability-registry/clawpod_capability_registry.py")
        registry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(registry)
        entries = json.loads((ROOT / "registry/index.json").read_text())["capabilities"]

        def fetch(url):
            relative = url.removeprefix(registry.RAW_BASE + "/")
            return (ROOT / relative).read_bytes()

        for kind, retired in (("skill", "references/legacy.md"), ("harness", "schemas/plan.schema.json")):
            entry = next(x for x in entries if x["type"] == kind and x["id"] == "clawpod-node-host")
            target = self.root / kind
            old_file = target / entry["id"] / retired
            old_file.parent.mkdir(parents=True)
            old_file.write_text("old procedure")
            with patch.object(registry, "fetch_bytes", side_effect=fetch):
                result = registry.install_entry(entry, str(target), replace=True, backup=True)
            self.assertFalse(old_file.exists())
            self.assertEqual(result["version"], entry["version"])
            self.assertEqual((Path(result["backup"]) / retired).read_text(), "old procedure")
            active = target / entry["id"]
            if kind == "harness":
                self.assertTrue((active / "agent_tailscale.py").is_file())
                self.assertEqual(set(json.loads((active / "harness.json").read_text())["commands"]),
                                 {"agent.status", "agent.login", "installer.info"})

    def test_optional_installer_source_commit_is_validated(self):
        for value in (None, 123, "not-a-commit", "a" * 39):
            data = copy.deepcopy(self.manifest)
            data["installerSourceCommit"] = value
            file = self.root / "bad-provenance.json"
            file.write_text(json.dumps(data))
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "installer source commit"):
                release.load_manifest(file)
        data = copy.deepcopy(self.manifest)
        data.pop("installerSourceCommit", None)
        file = self.root / "legacy-provenance.json"
        file.write_text(json.dumps(data))
        self.assertEqual(release.load_manifest(file)["version"], data["version"])

    def test_stage_only_distributes_installers_and_sanitized_metadata(self):
        (self.source / "private-report.json").write_text('{"stage":"/private/build/path"}')
        release.stage(self.source, self.destination, self.manifest)
        release.verify_stage(self.destination, self.manifest)
        self.assertEqual(len(list(self.destination.iterdir())), 9)
        self.assertFalse((self.destination / "private-report.json").exists())
        for item in self.manifest["artifacts"]:
            self.assertEqual((self.source / item["filename"]).read_bytes(),
                             (self.destination / item["filename"]).read_bytes())

    def test_last_corrupt_installer_creates_no_partial_release(self):
        item = self.manifest["artifacts"][-1]
        file = self.source / item["filename"]
        data = file.read_bytes()
        file.write_bytes(b"X" + data[1:])
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            release.stage(self.source, self.destination, self.manifest)
        self.assertFalse(self.destination.exists())

    def test_missing_installer_creates_no_partial_release(self):
        (self.source / self.manifest["artifacts"][-1]["filename"]).unlink()
        with self.assertRaisesRegex(ValueError, "Missing regular installer"):
            release.stage(self.source, self.destination, self.manifest)
        self.assertFalse(self.destination.exists())

    def test_restage_is_idempotent_and_preserves_existing_bytes(self):
        release.stage(self.source, self.destination, self.manifest)
        before = {p.name: p.stat().st_mtime_ns for p in self.destination.iterdir()}
        release.stage(self.source, self.destination, self.manifest)
        self.assertEqual(before, {p.name: p.stat().st_mtime_ns for p in self.destination.iterdir()})

    def test_existing_stage_extra_or_changed_files_are_not_overwritten(self):
        release.stage(self.source, self.destination, self.manifest)
        extra = self.destination / "unreviewed.json"
        extra.write_text("keep")
        with self.assertRaisesRegex(ValueError, "extra release files"):
            release.stage(self.source, self.destination, self.manifest)
        self.assertEqual(extra.read_text(), "keep")
        extra.unlink()
        meta = self.destination / "release.json"
        meta.write_text("changed")
        with self.assertRaisesRegex(ValueError, "metadata mismatch"):
            release.stage(self.source, self.destination, self.manifest)
        self.assertEqual(meta.read_text(), "changed")


if __name__ == "__main__":
    unittest.main()
