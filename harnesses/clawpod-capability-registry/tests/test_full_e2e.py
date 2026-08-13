from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
CLI = ROOT / "clawpod_capability_registry.py"
SPEC=importlib.util.spec_from_file_location("registry_e2e",CLI);assert SPEC and SPEC.loader
cap=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(cap)


class EndToEndTests(unittest.TestCase):
    SYNOLOGY_VERSION="0.1.5"

    def test_fresh_agent_workflow_onboarding_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / "WORKFLOW.md"
            workflow.write_bytes(b"# Agent workflow\n\nuser-owned sentinel\n")
            activated = subprocess.run(
                [str(CLI), "workflow-activate", "--workflow-path", str(workflow)],
                check=True, capture_output=True, text=True,
            )
            activation = json.loads(activated.stdout)
            self.assertTrue(activation["ok"])
            self.assertTrue(activation["data"]["changed"])
            self.assertEqual(activation["data"]["policyStatus"], "active")
            status = subprocess.run(
                [str(CLI), "workflow-status", "--workflow-path", str(workflow)],
                check=True, capture_output=True, text=True,
            )
            evidence = json.loads(status.stdout)["data"]
            self.assertEqual(evidence["policyVersion"], cap.WORKFLOW_POLICY_VERSION)
            self.assertFalse(evidence["changed"])
            self.assertTrue(workflow.read_bytes().startswith(b"# Agent workflow\n\nuser-owned sentinel\n"))

    def test_fresh_agent_missing_workflow_returns_structured_failure_without_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / "WORKFLOW.md"
            result = subprocess.run(
                [str(CLI), "workflow-activate", "--workflow-path", str(workflow)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            failure = json.loads(result.stdout)
            self.assertEqual(failure["error"]["code"], "workflow_missing")
            self.assertFalse(workflow.exists())

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

    def test_same_version_skill_and_harness_install_validate_to_typed_roots(self) -> None:
        registry=json.loads((REPOSITORY_ROOT/"registry/index.json").read_text(encoding="utf-8"))
        entries=[entry for entry in registry["capabilities"] if entry["id"]=="synology-smb-storage" and entry["version"]==self.SYNOLOGY_VERSION]
        self.assertEqual({entry["type"] for entry in entries},{"skill","harness"})

        def fetch_local(url:str,**_:object)->bytes:
            relative=url.removeprefix(cap.RAW_BASE+"/")
            return (REPOSITORY_ROOT/relative).read_bytes()

        parser=cap.build_parser()
        with tempfile.TemporaryDirectory() as directory,patch.object(cap,"entries",return_value=entries),patch.object(cap,"fetch_bytes",side_effect=fetch_local):
            base=Path(directory)
            ambiguous=parser.parse_args(["install","--id","synology-smb-storage","--version",self.SYNOLOGY_VERSION,"--target-root",str(base/"ambiguous")])
            with self.assertRaises(cap.CapabilityError) as raised:cap.run(ambiguous)
            self.assertEqual(raised.exception.code,"ambiguous_type")
            self.assertFalse((base/"ambiguous").exists())

            harness_root=base/"standalone-harnesses"
            harness_args=parser.parse_args(["install","--id","synology-smb-storage","--version",self.SYNOLOGY_VERSION,"--type","harness","--target-root",str(harness_root)])
            harness_result=cap.run(harness_args)["unit"][0]
            self.assertEqual(harness_result["type"],"harness")
            self.assertEqual(Path(harness_result["destination"]),harness_root/"synology-smb-storage")
            harness_provenance=json.loads((Path(harness_result["destination"])/cap.PROVENANCE_FILE).read_text())
            self.assertEqual(harness_provenance["type"],"harness")
            harness_validation=cap.run(parser.parse_args(["validate","--id","synology-smb-storage","--version",self.SYNOLOGY_VERSION,"--type","harness","--target-root",str(harness_root)]))["unit"][0]
            self.assertEqual(harness_validation["type"],"harness")
            self.assertEqual(Path(harness_validation["destination"]),harness_root/"synology-smb-storage")

            skill_root=base/"skills";linked_harness_root=base/"linked-harnesses"
            installed_harness=Path(harness_result["destination"])
            installed_manifest=json.loads((installed_harness/"harness.json").read_text())
            self.assertEqual(len(installed_manifest["commands"]),13)
            self.assertTrue({"file.list","file.get","file.put"}.isdisjoint(installed_manifest["commands"]))
            supported={"type"}
            for command in installed_manifest["commands"].values():
                for schema in command["inputSchema"].get("properties",{}).values():
                    self.assertLessEqual(set(schema),supported)
            prepared=installed_manifest["commands"]["system.preflight"]["baseArgv"]
            exercised=subprocess.run(
                [str(installed_harness/installed_manifest["entrypoint"]),*prepared],
                check=True,capture_output=True,text=True,
            )
            self.assertTrue(json.loads(exercised.stdout)["ok"])

            skill_args=parser.parse_args(["install","--id","synology-smb-storage","--version",self.SYNOLOGY_VERSION,"--type","skill","--skills-root",str(skill_root),"--harnesses-root",str(linked_harness_root)])
            skill_result=cap.run(skill_args)
            self.assertEqual({item["type"] for item in skill_result["unit"]},{"skill","harness"})
            destinations={item["type"]:Path(item["destination"]) for item in skill_result["unit"]}
            self.assertEqual(destinations["skill"],skill_root/"synology-smb-storage")
            self.assertEqual(destinations["harness"],linked_harness_root/"synology-smb-storage")
            skill_validation=cap.run(parser.parse_args(["validate","--id","synology-smb-storage","--version",self.SYNOLOGY_VERSION,"--type","skill","--skills-root",str(skill_root),"--harnesses-root",str(linked_harness_root)]))
            self.assertEqual({item["type"] for item in skill_validation["unit"]},{"skill","harness"})


if __name__ == "__main__":
    unittest.main()
