from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "claude-design" / "SKILL.md"
DESCRIPTION = "Use for Claude Design create/edit/QA/export and project/native export work; use Image Studio for stills, and compose with Desktop only for native OS dialogs."
DESKTOP_COMPOSITION_POSITIVE = (
    "Use the native GTK Save File dialog to save this Claude Design PDF to an exact path",
    "Complete Claude Design export after Chrome print preview opens an OS save dialog",
    "Open the exported deck in a native viewer only because Browser and file checks cannot complete visual QA",
)
DESKTOP_COMPOSITION_NEGATIVE = {
    "browser": "Edit ordinary Claude Design web controls through the Browser DOM",
    "claude-design-harness": "Plan and verify the export with the paired Claude Design Harness",
    "nodes": "Inspect an already paired remote Claude Design screen with nodes",
    "clawpod-image-studio": "Generate a standalone product photo with Image Studio",
}


def test_claude_design_routing_examples_and_adjacent_collisions() -> None:
    contracts = json.loads((ROOT / "tests" / "fixtures" / "routing_contracts.json").read_text())
    contract = contracts["claude-design"]
    assert len(contract["positive"]) >= 3
    assert len(contract["negative"]) >= 2
    assert {"clawpod-image-studio", "clawpod-video-studio"} <= set(contract["adjacent"])
    assert "standalone product photo" in " ".join(contract["negative"]).lower()
    assert "localized video" in " ".join(contract["negative"]).lower()


def test_desktop_composition_is_selective() -> None:
    positives = " ".join(DESKTOP_COMPOSITION_POSITIVE).lower()
    negatives = DESKTOP_COMPOSITION_NEGATIVE
    assert len(DESKTOP_COMPOSITION_POSITIVE) >= 3
    assert "gtk save file" in positives
    assert "os save dialog" in positives
    assert "native viewer" in positives
    assert set(negatives) == {"browser", "claude-design-harness", "nodes", "clawpod-image-studio"}
    assert "browser dom" in negatives["browser"].lower()
    assert "paired claude design harness" in negatives["claude-design-harness"].lower()
    assert "paired remote" in negatives["nodes"].lower()
    assert "standalone product photo" in negatives["clawpod-image-studio"].lower()


def test_claude_design_description_is_exact_on_linked_surfaces() -> None:
    skill_text = SKILL.read_text()
    assert f'description: "{DESCRIPTION}"' in skill_text
    assert json.loads((ROOT / "skills" / "claude-design" / "capability.json").read_text())["description"] == DESCRIPTION
    assert json.loads((ROOT / "harnesses" / "claude-design" / "capability.json").read_text())["description"] == DESCRIPTION
    assert json.loads((ROOT / "harnesses" / "claude-design" / "harness.json").read_text())["description"] == DESCRIPTION


def test_desktop_handoff_returns_to_typed_verification() -> None:
    text = SKILL.read_text()
    assert "never use Desktop instead of Browser for ordinary Claude Design DOM work" in text
    assert "native GTK Save File dialog" in text
    assert "then return to Harness/file verification" in text
    assert "Do not use Desktop to click ordinary Claude Design web controls" in text
    assert "compose with Desktop only when visual QA requires rendering in a native viewer" in text


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
