from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "claude-design" / "SKILL.md"
DESCRIPTION = "Use when creating, editing, QAing, or exporting in Claude Design. Can manage projects and native exports; use Image Studio for standalone images."


def test_claude_design_routing_examples_and_adjacent_collisions() -> None:
    contracts = json.loads((ROOT / "tests" / "fixtures" / "routing_contracts.json").read_text())
    contract = contracts["claude-design"]
    assert len(contract["positive"]) >= 3
    assert len(contract["negative"]) >= 2
    assert {"clawpod-image-studio", "clawpod-video-studio"} <= set(contract["adjacent"])
    assert "standalone product photo" in " ".join(contract["negative"]).lower()
    assert "localized video" in " ".join(contract["negative"]).lower()


def test_claude_design_description_is_exact_on_linked_surfaces() -> None:
    skill_text = SKILL.read_text()
    assert f'description: "{DESCRIPTION}"' in skill_text
    assert json.loads((ROOT / "skills" / "claude-design" / "capability.json").read_text())["description"] == DESCRIPTION
    assert json.loads((ROOT / "harnesses" / "claude-design" / "capability.json").read_text())["description"] == DESCRIPTION
    assert json.loads((ROOT / "harnesses" / "claude-design" / "harness.json").read_text())["description"] == DESCRIPTION


def test_stale_version_and_export_recovery_procedure_is_bounded() -> None:
    text = SKILL.read_text()
    required = (
        "pin the source of truth",
        "prohibited stale markers",
        "stop and re-ground before exporting",
        "retry once after a fresh project-list read",
        "After two identical failures, stop blind retries",
        "Never create multiple duplicate projects",
        "verify that exactly one new file appears",
        "Do not repeatedly click export",
        "rerun the pinned-version/stale-marker check across all slides",
        "create a retry Workboard card",
        "explicitly run Workboard dispatch",
    )
    for phrase in required:
        assert phrase in text
