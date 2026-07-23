from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "clawpod_capability_registry.py"
SPEC = importlib.util.spec_from_file_location("clawpod_capability", MODULE_PATH)
assert SPEC and SPEC.loader
cap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cap)


def fixture_entry(version: str, payload: bytes) -> dict:
    return {
        "id": "example-skill",
        "type": "skill",
        "version": version,
        "description": "Example capability used by tests.",
        "path": "skills/example-skill",
        "compatibility": {"openclaw": ">=2026.4.0"},
        "safety": {"risk": "write-safe", "approvalRequired": True},
        "files": [{"path": "SKILL.md", "sha256": hashlib.sha256(payload).hexdigest()}],
    }


class CoreTests(unittest.TestCase):
    def test_rejects_noncanonical_url(self) -> None:
        with self.assertRaisesRegex(cap.CapabilityError, "non-canonical"):
            cap.fetch_bytes("https://example.com/index.json")

    def test_choose_latest_and_exact_version(self) -> None:
        items = [fixture_entry("0.1.0", b"old"), fixture_entry("0.2.0", b"new")]
        with patch.object(cap, "entries", return_value=items):
            self.assertEqual(cap.choose("example-skill")["version"], "0.2.0")
            self.assertEqual(cap.choose("example-skill", "0.1.0")["version"], "0.1.0")

    def test_choose_requires_type_when_ids_collide(self) -> None:
        skill=fixture_entry("0.1.0",b"skill")
        harness={**skill,"type":"harness","path":"harnesses/example-skill"}
        with patch.object(cap,"entries",return_value=[skill,harness]):
            with self.assertRaisesRegex(cap.CapabilityError,"both skill and harness"):
                cap.choose("example-skill")
            self.assertEqual(cap.choose("example-skill",capability_type="harness")["type"],"harness")

    def test_linked_unit_install_validate_and_partial_rollback(self) -> None:
        skill_payload=b"skill"; harness_manifest=json.dumps({"entrypoint":"run.py"}).encode(); run=b"#!/usr/bin/env python3\n"
        skill={**fixture_entry("0.1.0",skill_payload),"linkedHarness":{"id":"example-skill","version":"0.2.0"}}
        harness={"id":"example-skill","type":"harness","version":"0.2.0","description":"Example harness used by tests.","path":"harnesses/example-skill","compatibility":{"openclaw":">=2026.4.0"},"safety":{"risk":"write-safe","approvalRequired":True},"files":[{"path":"harness.json","sha256":hashlib.sha256(harness_manifest).hexdigest()},{"path":"run.py","sha256":hashlib.sha256(run).hexdigest()}]}
        payloads={"SKILL.md":skill_payload,"harness.json":harness_manifest,"run.py":run}
        def fetch(url:str,**_:object)->bytes:return payloads[url.rsplit('/',1)[-1]]
        with tempfile.TemporaryDirectory() as sroot,tempfile.TemporaryDirectory() as hroot:
            with patch.object(cap,"entries",return_value=[skill,harness]),patch.object(cap,"fetch_bytes",side_effect=fetch):
                result=cap.install_unit(skill,sroot,hroot,replace=False)
                self.assertTrue(result["transactional"]);self.assertEqual(len(cap.validate_unit(skill,sroot,hroot)["unit"]),2)
            shutil_path=Path(hroot)/"example-skill"/"run.py"; before=shutil_path.read_bytes()
            bad={**harness,"files":[*harness["files"][:-1],{"path":"run.py","sha256":"0"*64}]}
            with patch.object(cap,"entries",return_value=[skill,bad]),patch.object(cap,"fetch_bytes",side_effect=fetch):
                with self.assertRaises(cap.CapabilityError):cap.install_unit(skill,sroot,hroot,replace=True)
            self.assertEqual(shutil_path.read_bytes(),before)

    def test_linked_unit_requires_both_roots(self) -> None:
        skill={**fixture_entry("0.1.0",b"x"),"linkedHarness":{"id":"example-skill","version":"0.2.0"}}
        harness={**fixture_entry("0.2.0",b"x"),"type":"harness"}
        with patch.object(cap,"entries",return_value=[skill,harness]):
            with self.assertRaisesRegex(cap.CapabilityError,"both --skills-root"):
                cap.install_unit(skill,"/tmp/skills",None,replace=False)

    def test_rejects_unsafe_package_path(self) -> None:
        with self.assertRaises(cap.CapabilityError):
            cap.validate_relative_path("../secret")

    def test_install_validate_update_and_rollback(self) -> None:
        old = b"---\nname: example-skill\ndescription: old\n---\n"
        new = b"---\nname: example-skill\ndescription: new\n---\n"
        old_entry = fixture_entry("0.1.0", old)
        new_entry = fixture_entry("0.2.0", new)

        def fetch_old(url: str, **_: object) -> bytes:
            self.assertTrue(url.startswith(cap.RAW_BASE + "/"))
            return old

        def fetch_new(url: str, **_: object) -> bytes:
            self.assertTrue(url.startswith(cap.RAW_BASE + "/"))
            return new

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(cap, "fetch_bytes", side_effect=fetch_old):
                installed = cap.install_entry(old_entry, directory, replace=False, backup=False)
            self.assertEqual(installed["verifiedFiles"], 1)
            self.assertEqual(cap.validate_installation(old_entry, directory)["checked"], ["SKILL.md"])

            with self.assertRaisesRegex(cap.CapabilityError, "already exists"):
                with patch.object(cap, "fetch_bytes", side_effect=fetch_old):
                    cap.install_entry(old_entry, directory, replace=False, backup=False)

            with patch.object(cap, "fetch_bytes", side_effect=fetch_new):
                updated = cap.install_entry(new_entry, directory, replace=True, backup=True)
            self.assertIsNotNone(updated["backup"])
            self.assertEqual(cap.validate_installation(new_entry, directory)["checked"], ["SKILL.md"])

            result = cap.rollback_installation("example-skill", directory, None)
            self.assertEqual(Path(result["destination"]).joinpath("SKILL.md").read_bytes(), old)

    def test_harness_install_makes_entrypoint_executable(self) -> None:
        manifest = json.dumps({"entrypoint": "run.py"}).encode()
        entrypoint = b"#!/usr/bin/env python3\n"
        entry = {
            "id": "example-harness",
            "type": "harness",
            "version": "0.1.0",
            "description": "Example harness used by tests.",
            "path": "harnesses/example-harness",
            "compatibility": {"openclaw": ">=2026.4.0"},
            "safety": {"risk": "write-safe", "approvalRequired": True},
            "files": [
                {"path": "harness.json", "sha256": hashlib.sha256(manifest).hexdigest()},
                {"path": "run.py", "sha256": hashlib.sha256(entrypoint).hexdigest()},
            ],
        }
        payloads = {"harness.json": manifest, "run.py": entrypoint}

        def fetch(url: str, **_: object) -> bytes:
            return payloads[url.rsplit("/", 1)[-1]]

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(cap, "fetch_bytes", side_effect=fetch):
                cap.install_entry(entry, directory, replace=False, backup=False)
            mode = (Path(directory) / "example-harness" / "run.py").stat().st_mode
            self.assertTrue(mode & 0o111)

    def test_validation_detects_modified_file(self) -> None:
        payload = b"original"
        entry = fixture_entry("0.1.0", payload)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "example-skill"
            destination.mkdir()
            (destination / "SKILL.md").write_bytes(b"modified")
            with self.assertRaisesRegex(cap.CapabilityError, "modified files"):
                cap.validate_installation(entry, directory)

    def test_provenance_contains_no_secret_fields(self) -> None:
        entry = fixture_entry("0.1.0", b"content")
        record = cap.provenance(entry, entry["files"])
        encoded = json.dumps(record).lower()
        self.assertNotIn("token", encoded)
        self.assertNotIn("password", encoded)


if __name__ == "__main__":
    unittest.main()
