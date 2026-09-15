from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "routing_contracts.json"
CLAWPOD_NODE_HOST_DESCRIPTION = 'Use when a user wants to connect a Linux, macOS, or Windows computer to ClawPod. Guide agent and computer Tailscale sign-in, select the standalone ClawPod Node installer, provide Gateway connection values, verify device pairing, guide desktop permissions, and explain app recovery or removal. Use node-connect when available for an already configured node that fails to connect or pair.'


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
        for phrase in ("Linux", "Mac", "Apple Silicon", "Intel", "Windows 11", "standalone installer", "Gateway setup", "device pairing", "Tailscale", "same tailnet", "recovery", "removal"):
            self.assertIn(phrase, positives)
        for phrase in ("already configured ClawPod node connection failing", "paired node unauthorized", "already configured node fails to pair"):
            self.assertIn(phrase, negatives)
        self.assertIn("Use node-connect when available", CLAWPOD_NODE_HOST_DESCRIPTION)


if __name__ == "__main__":
    unittest.main()
