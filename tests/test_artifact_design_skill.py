"""Contract-pinning tests for the artifact-design Skill.

The Skill encodes facts verified against the ClawPod admin-api and portal
source (artifact field limits, the save-then-artifact_refs flow, the sandboxed
iframe renderer). These tests keep those facts from silently drifting out of
the package.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "artifact-design"
REFERENCES = SKILL_DIR / "references"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class ArtifactDesignSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = read(SKILL_DIR / "SKILL.md")
        cls.contract = read(REFERENCES / "publishing-contract.md")
        cls.skeleton = read(REFERENCES / "html-skeleton.md")
        cls.choosing = read(REFERENCES / "choosing-the-type.md")
        cls.checklist = read(REFERENCES / "checklist.md")
        cls.everything = "\n".join(read(p) for p in sorted(SKILL_DIR.rglob("*.md")))

    def test_package_is_skill_only_and_write_safe(self) -> None:
        metadata = json.loads(read(SKILL_DIR / "capability.json"))
        self.assertNotIn("linkedHarness", metadata)
        self.assertFalse((ROOT / "harnesses" / "artifact-design").exists())
        self.assertEqual(metadata["safety"], {"risk": "write-safe", "approvalRequired": False})
        self.assertEqual(metadata["descriptionSource"], "skill-frontmatter")

    def test_every_referenced_support_file_exists(self) -> None:
        for match in re.finditer(r"\]\((references/[^)]+)\)", self.skill):
            self.assertTrue((SKILL_DIR / match.group(1)).is_file(), match.group(1))
        for name in ("publishing-contract", "design-fundamentals", "html-skeleton", "choosing-the-type", "markdown-craft", "checklist", "examples"):
            self.assertIn(f"references/{name}.md", self.skill, name)

    def test_publishing_contract_pins_verified_api_facts(self) -> None:
        for fact in (
            "POST /internal/chat-rooms/:roomId/artifacts",
            "/internal/messages",
            "X-Gateway-Token",
            "from_agent_id",
            "artifact_refs",
            "^[A-Za-z0-9][A-Za-z0-9_.-]*$",
            "1–120",
            "1–200 chars",
            "200,000",
            "`markdown` or `html`",
            "Max **5**",
            "cannot both be set",
            "expectedVersion",
            "409",
            "latestVersion",
            "404",
            "403",
            "240 chars",
            "Content-addressed no-op",
            "NO_REPLY",
        ):
            self.assertIn(fact, self.contract, fact)

    def test_pointer_flow_is_the_standard_and_inline_is_legacy(self) -> None:
        self.assertIn("supersedes", self.contract)
        self.assertIn("Legacy mode: inline `artifacts`", self.contract)
        self.assertIn("artifact_refs", self.skill)
        self.assertIn("Never send `artifacts` and `artifact_refs` in the same message", self.skill)

    def test_html_guidance_matches_the_sandboxed_iframe_renderer(self) -> None:
        for fact in ('sandbox=""', "No JavaScript runs", "prefers-color-scheme", "70 vh", "cdn.jsdelivr.net", "Google Fonts is blocked", "end of `<body>`"):
            self.assertIn(fact, self.skeleton, fact)
        self.assertNotIn("<script>", self.skeleton.split("## Skeleton")[1].split("```")[1])
        self.assertNotIn("fonts.googleapis.com", self.everything)
        self.assertNotIn("localStorage works", self.everything)
        self.assertIn("Does not run", self.choosing)

    def test_markers_and_paths_are_named_as_plain_text_traps(self) -> None:
        for trap in ("[embed ref=...]", "/workspace/...", "plain text"):
            self.assertIn(trap, self.contract, trap)
        self.assertIn("never become artifacts", self.skill)

    def test_checklist_covers_theme_preview_and_payload_gates(self) -> None:
        for gate in ("no `<script>`", "prefers-color-scheme: dark", "end of `<body>`", "artifact_refs", "NO_REPLY", "expectedVersion", "1–120", "1–200"):
            self.assertIn(gate, self.checklist, gate)

    def test_description_routes_away_from_adjacent_capabilities(self) -> None:
        description = next(line for line in self.skill.splitlines() if line.startswith("description:"))
        for capability in ("Claude Design", "Image Studio", "Video Studio"):
            self.assertIn(capability, description)
        self.assertIn("artifact_refs", description)


if __name__ == "__main__":
    unittest.main()
