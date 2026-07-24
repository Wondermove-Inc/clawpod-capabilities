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
    def test_workflow_empty_existing_file_append_and_idempotence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / "WORKFLOW.md"
            workflow.write_bytes(b"")
            first = cap.activate_workflow_policy(str(workflow))
            after = workflow.read_bytes()
            self.assertTrue(first["changed"])
            self.assertEqual(first["policyStatus"], "active")
            self.assertEqual(first["policyVersion"], cap.WORKFLOW_POLICY_VERSION)
            second = cap.activate_workflow_policy(str(workflow))
            self.assertFalse(second["changed"])
            self.assertEqual(workflow.read_bytes(), after)

    def test_workflow_preserves_sentinel_bytes_before_and_after_replacement(self) -> None:
        before = b"\xef\xbb\xbf# user header\r\nSENTINEL-BEFORE\x00\n"
        after = b"\r\nSENTINEL-AFTER\xff\n"
        old = cap.WORKFLOW_BEGIN + b"\nold managed policy\n" + cap.WORKFLOW_END
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / "WORKFLOW.md"
            workflow.write_bytes(before + old + after)
            result = cap.activate_workflow_policy(str(workflow))
            updated = workflow.read_bytes()
            self.assertTrue(result["changed"])
            self.assertEqual(result["previousPolicyStatus"], "outdated")
            self.assertTrue(updated.startswith(before))
            self.assertTrue(updated.endswith(after))
            self.assertEqual(updated[:len(before)], before)
            self.assertEqual(updated[-len(after):], after)

    def test_workflow_missing_is_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / "WORKFLOW.md"
            with self.assertRaises(cap.CapabilityError) as raised:
                cap.activate_workflow_policy(str(workflow))
            self.assertEqual(raised.exception.code, "workflow_missing")
            self.assertFalse(workflow.exists())

    def test_malformed_workflow_markers_never_mutate(self) -> None:
        malformed = [
            cap.WORKFLOW_BEGIN + b"\nunclosed",
            cap.WORKFLOW_END + b"\n" + cap.WORKFLOW_BEGIN,
            cap.WORKFLOW_BEGIN + b"\n" + cap.WORKFLOW_BEGIN + b"\n" + cap.WORKFLOW_END,
            cap.WORKFLOW_BEGIN + b"\n" + cap.WORKFLOW_END + b"\n" + cap.WORKFLOW_END,
        ]
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / "WORKFLOW.md"
            for payload in malformed:
                workflow.write_bytes(payload)
                with self.assertRaises(cap.CapabilityError) as raised:
                    cap.activate_workflow_policy(str(workflow))
                self.assertEqual(raised.exception.code, "malformed_workflow_markers")
                self.assertEqual(workflow.read_bytes(), payload)

    def test_workflow_status_is_read_only_and_path_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / "WORKFLOW.md"
            workflow.write_bytes(b"user content")
            before = workflow.read_bytes()
            status = cap.inspect_workflow_policy(str(workflow))
            self.assertEqual(status["policyStatus"], "absent")
            self.assertEqual(len(status["workflowPathHash"]), 64)
            self.assertNotIn(str(workflow), json.dumps(status))
            self.assertEqual(workflow.read_bytes(), before)

    def test_unrelated_install_does_not_mutate_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / "WORKFLOW.md"
            workflow.write_bytes(b"unrelated sentinel")
            with patch.object(cap, "install_unit", return_value={"unit": []}) as install:
                result = cap.install_unit_with_onboarding(
                    fixture_entry("1.0.0", b"x"), directory, None, replace=False, workflow=str(workflow)
                )
            install.assert_called_once()
            self.assertEqual(result, {"unit": []})
            self.assertEqual(workflow.read_bytes(), b"unrelated sentinel")

    def test_registry_install_requires_workflow_and_rolls_back_on_onboarding_failure(self) -> None:
        entry = {**fixture_entry("1.0.0", b"x"), "id": "clawpod-capability-registry"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skills"
            destination = root / entry["id"]
            destination.mkdir(parents=True)
            (destination / "old").write_bytes(b"old")
            workflow = Path(directory) / "WORKFLOW.md"
            workflow.write_bytes(b"sentinel")
            with self.assertRaises(cap.CapabilityError) as required:
                cap.install_unit_with_onboarding(entry, str(root), None, replace=True, workflow=None)
            self.assertEqual(required.exception.code, "workflow_path_required")

            def fake_install(*_: object, **__: object) -> dict:
                shutil = __import__("shutil")
                shutil.rmtree(destination)
                destination.mkdir()
                (destination / "new").write_bytes(b"new")
                return {"unit": []}

            with patch.object(cap, "install_unit", side_effect=fake_install), patch.object(
                cap, "atomic_write", side_effect=OSError("disk full")
            ):
                with self.assertRaises(OSError):
                    cap.install_unit_with_onboarding(entry, str(root), None, replace=True, workflow=str(workflow))
            self.assertEqual((destination / "old").read_bytes(), b"old")
            self.assertFalse((destination / "new").exists())
            self.assertEqual(workflow.read_bytes(), b"sentinel")

    def test_registry_install_completes_workflow_onboarding(self) -> None:
        entry = {**fixture_entry("1.0.0", b"x"), "id": "clawpod-capability-registry"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skills"
            workflow = Path(directory) / "WORKFLOW.md"
            workflow.write_bytes(b"owner content\n")
            with patch.object(cap, "install_unit", return_value={"unit": [{"id": entry["id"]}]}):
                result = cap.install_unit_with_onboarding(
                    entry, str(root), None, replace=False, workflow=str(workflow)
                )
            self.assertTrue(result["onboardingComplete"])
            self.assertEqual(result["workflowPolicy"]["policyStatus"], "active")
            self.assertTrue(result["workflowPolicy"]["changed"])
            self.assertTrue(workflow.read_bytes().startswith(b"owner content\n"))

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
