from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "claude-design" / "SKILL.md"
NATIVE_EXPORT = ROOT / "skills" / "claude-design" / "references" / "native-export.md"
QUALITY_GATES = ROOT / "skills" / "claude-design" / "references" / "quality-gates.md"
LINK_HANDOFF = ROOT / "skills" / "claude-design" / "references" / "link-handoff.md"
DESCRIPTION = "Use for Claude Design create/edit/QA and link-first deck handoff: deliver the verified project link so the user exports PPTX/PDF themselves, and run native file export only when a file is explicitly requested. Use Image Studio for stills, and compose with Desktop only for native OS dialogs."
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
    text = SKILL.read_text() + NATIVE_EXPORT.read_text()
    assert "never use Desktop instead of Browser for ordinary Claude Design DOM work" in text
    assert "native GTK Save File dialog" in text
    assert "then return to Harness/file verification" in text
    assert "Do not use Desktop to click ordinary Claude Design web controls" in text
    assert "compose with Desktop only when visual QA requires rendering in a native viewer" in text


def test_stale_version_and_export_recovery_procedure_is_bounded() -> None:
    text = SKILL.read_text() + NATIVE_EXPORT.read_text()
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


def test_link_first_delivery_is_the_default_and_file_export_is_opt_in() -> None:
    text = SKILL.read_text()
    assert "## The deliverable is the link, not the file" in text
    assert "projects.link.verify" in text
    assert "only when the user explicitly asks for a file" in text
    assert "room artifacts" in text and "markdown/html" in text
    assert "never export files as a workaround for access" in text
    for ref in ("references/link-handoff.md", "references/quality-gates.md", "references/native-export.md"):
        assert ref in text and (ROOT / "skills" / "claude-design" / ref).is_file()
    link = LINK_HANDOFF.read_text()
    assert "Share → Export → PowerPoint" in link and "projects.share.preview" in link
    harness = json.loads((ROOT / "harnesses" / "claude-design" / "harness.json").read_text())
    assert harness["commands"]["projects.link.verify"]["safetyClasses"] == ["readOnly"]
    assert harness["version"] == "0.4.0"
    assert json.loads((ROOT / "skills" / "claude-design" / "capability.json").read_text())["linkedHarness"]["version"] == "0.4.0"


def test_quality_gates_are_deterministic_and_feed_a_bounded_revise_loop() -> None:
    text = SKILL.read_text()
    assert "## Quality gate and revise loop" in text
    assert "projects.qa.layout" in text and "revision_prompt" in text and "projects.iterate" in text
    assert "at most three revise rounds" in text
    gates = QUALITY_GATES.read_text()
    for section in ("## 1. Content gate", "## 2. Structure gate", "## 3. Visual gate"):
        assert section in gates
    for code in ("TEXT_OVERFLOW", "TEXT_OUTSIDE_SHAPE", "OVERLAP", "OFF_CANVAS", "MISALIGNED_EDGE", "UNEVEN_SPACING", "FONT_TOO_SMALL", "TEXT_DENSITY", "INCONSISTENT_SHAPES", "TITLE_DRIFT", "FONT_SIZE_SPRAWL"):
        assert code in gates, code
    assert "Diagram grammar" in gates and "one shape per concept type" in gates
    assert "getBoundingClientRect" in gates and "scrollWidth" in gates
    harness = json.loads((ROOT / "harnesses" / "claude-design" / "harness.json").read_text())
    qa = harness["commands"]["projects.qa.layout"]
    assert qa["safetyClasses"] == ["readOnly"] and qa["inputSchema"]["required"] == ["layoutJson"]
