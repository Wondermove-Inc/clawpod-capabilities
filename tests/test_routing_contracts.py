from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "routing_contracts.json"
CLAWPOD_NODE_HOST_DESCRIPTION = (
    "Use when a user wants to connect a Mac or Windows 11 PC to ClawPod as a node. Default flow"
    ": hand the user one complete, credential-free script (Tailscale, openclaw install, gateway"
    " address baked in), then auto-detect and approve the pairing request. Can also drive SSH-b"
    "ased provisioning, verification, recovery, and removal. Use node-connect instead when an a"
    "lready configured node fails to connect or pair."
)


def frontmatter_description(skill: Path) -> str:
    line = next(line for line in skill.read_text(encoding="utf-8").splitlines() if line.startswith("description:"))
    return line.split(":", 1)[1].strip().strip('"\'')


class RoutingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contracts = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.skill_ids = {path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")}

    def test_fixture_covers_every_capability_with_trigger_examples(self) -> None:
        self.assertEqual(set(self.contracts), self.skill_ids)
        self.assertEqual(len(self.contracts), len(self.skill_ids))
        for capability, contract in self.contracts.items():
            self.assertEqual(set(contract), {"positive", "negative", "adjacent"}, capability)
            self.assertGreaterEqual(len(contract["positive"]), 3, capability)
            self.assertGreaterEqual(len(contract["negative"]), 2, capability)
            self.assertTrue(all(isinstance(phrase, str) and phrase.strip() for phrase in contract["positive"]), capability)
            self.assertTrue(all(isinstance(phrase, str) and phrase.strip() for phrase in contract["negative"]), capability)
            self.assertTrue(set(contract["positive"]).isdisjoint(contract["negative"]), capability)

    def test_adjacent_collision_relationships_are_explicit_and_reciprocal(self) -> None:
        for capability, contract in self.contracts.items():
            self.assertTrue(contract["adjacent"], capability)
            for adjacent in contract["adjacent"]:
                self.assertIn(adjacent, self.skill_ids, capability)
                self.assertNotEqual(adjacent, capability)
                self.assertIn(capability, self.contracts[adjacent]["adjacent"], f"{capability} <-> {adjacent}")

    def test_skill_and_harness_share_the_natural_routing_contract(self) -> None:
        for capability, contract in self.contracts.items():
            description = frontmatter_description(ROOT / "skills" / capability / "SKILL.md")
            harness_path = ROOT / "harnesses" / capability / "harness.json"
            if harness_path.is_file():
                harness = json.loads(harness_path.read_text(encoding="utf-8"))
                self.assertEqual(harness["description"], description, capability)
                self.assertEqual(harness["whenToUse"], contract["positive"], capability)
            self.assertNotRegex(description, r"\b(?:WHEN|CAN)\s*:", capability)
            self.assertRegex(description, r"\b(?:Use|use)\b", capability)

    def test_clawpod_node_host_description_is_identical_across_sources(self) -> None:
        capability = "clawpod-node-host"
        description = frontmatter_description(ROOT / "skills" / capability / "SKILL.md")
        harness = json.loads((ROOT / "harnesses" / capability / "harness.json").read_text(encoding="utf-8"))
        skill_metadata = json.loads(
            (ROOT / "skills" / capability / "capability.json").read_text(encoding="utf-8")
        )
        harness_metadata = json.loads(
            (ROOT / "harnesses" / capability / "capability.json").read_text(encoding="utf-8")
        )
        registry = json.loads((ROOT / "registry" / "index.json").read_text(encoding="utf-8"))["capabilities"]
        registry_descriptions = {
            entry["type"]: entry["description"]
            for entry in registry
            if entry["id"] == capability
        }
        self.assertEqual(description, CLAWPOD_NODE_HOST_DESCRIPTION)
        self.assertEqual(harness["description"], description)
        self.assertEqual(skill_metadata["description"], description)
        self.assertEqual(harness_metadata["description"], description)
        self.assertEqual(registry_descriptions, {"skill": description, "harness": description})

    def test_clawpod_node_host_routes_onboarding_and_excludes_node_connect_diagnostics(self) -> None:
        contract = self.contracts["clawpod-node-host"]
        positives = " ".join(contract["positive"])
        negatives = " ".join(contract["negative"])
        for phrase in ("Mac", "Windows 11", "Tailscale", "networking", "SSH", "sign-in", "approve", "recovery", "removal"):
            self.assertIn(phrase, positives)
        for phrase in ("already configured ClawPod node connection failing", "paired node unauthorized", "already configured node fails to pair"):
            self.assertIn(phrase, negatives)
        self.assertIn("Use node-connect instead", CLAWPOD_NODE_HOST_DESCRIPTION)

    def test_desktop_routes_only_native_handoffs_and_names_composition_boundaries(self) -> None:
        description = frontmatter_description(ROOT / "skills" / "desktop" / "SKILL.md")
        for phrase in (
            "native apps or OS dialogs",
            "typed API or DOM",
            "Observe and operate",
            "pointer/keyboard",
            "windows/dialogs",
            "drag/drop",
            "QA, verify, recover",
            "Prefer Browser for DOM",
            "nodes for remote screens",
            "provider APIs for services",
        ):
            self.assertIn(phrase, description)

        for metadata_path in (
            ROOT / "skills" / "desktop" / "capability.json",
            ROOT / "harnesses" / "desktop" / "capability.json",
        ):
            self.assertEqual(json.loads(metadata_path.read_text(encoding="utf-8"))["description"], description)
        desktop_registry_entries = [
            entry for entry in json.loads((ROOT / "registry" / "index.json").read_text(encoding="utf-8"))["capabilities"]
            if entry["id"] == "desktop"
        ]
        self.assertEqual(len(desktop_registry_entries), 2)
        self.assertTrue(all(entry["description"] == description for entry in desktop_registry_entries))

        negatives = " ".join(self.contracts["desktop"]["negative"])
        for collision in ("Browser", "nodes", "provider API"):
            self.assertIn(collision, negatives)


if __name__ == "__main__":
    unittest.main()
