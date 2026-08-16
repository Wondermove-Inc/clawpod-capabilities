from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "clawpod-org-operations"
FAMILIES = (
    "Delegation or task request",
    "Peer-help request",
    "Upward status or decision",
    "Blocker or escalation",
    "Handoff or shift change",
    "Review or approval request",
    "Incident update",
    "Completion or closure",
    "No-response follow-up",
)


def test_package_is_prose_only_skill_surface() -> None:
    files = {path.relative_to(SKILL).as_posix() for path in SKILL.rglob("*") if path.is_file()}
    assert files == {
        "SKILL.md",
        "agents/openai.yaml",
        "capability.json",
        "references/common-templates.md",
        "references/engineering.md",
        "references/soc-csirt.md",
        "references/sre-incident.md",
        "references/evidence-boundaries.md",
    }
    assert not (ROOT / "harnesses" / "clawpod-org-operations").exists()
    metadata = json.loads((SKILL / "capability.json").read_text())
    assert "linkedHarness" not in metadata


def test_all_nine_families_are_available_in_common_and_each_specialist_pack() -> None:
    common = (SKILL / "references/common-templates.md").read_text()
    assert all(family in common for family in FAMILIES)
    for pack in ("engineering.md", "soc-csirt.md", "sre-incident.md"):
        text = (SKILL / "references" / pack).read_text()
        for number in range(1, 10):
            assert f"{number}. **" in text, (pack, number)


def test_service_neutral_routing_and_local_workboard_boundary_are_explicit() -> None:
    text = (SKILL / "SKILL.md").read_text()
    assert "read the applicable organization or agent `WORKFLOW.md`" in text
    assert "If no applicable `WORKFLOW.md` designates" in text
    assert "Keep Workboard local" in text
    templates = "\n".join(path.read_text() for path in (SKILL / "references").glob("*.md"))
    assert "[system-of-record reference]" in templates


def test_fresh_agent_simulations_do_not_leak_task_service_between_organizations() -> None:
    scenarios = json.loads((ROOT / "tests/fixtures/org_operations_fresh_agent.json").read_text())
    first, second, missing = scenarios
    assert first["expected_service"] == "Linear"
    assert first["expected_pack"] == "Engineering"
    assert second["expected_service"] == "Jira Service Management"
    assert second["expected_pack"] == "SOC/CSIRT"
    assert first["expected_service"] not in second["workflow"]
    assert missing["expected_service"] is None
    assert missing["expected_result"] == "stop_and_ask"


def test_evidence_boundaries_include_sources_limits_and_anti_patterns() -> None:
    text = (SKILL / "references/evidence-boundaries.md").read_text()
    for source in ("Atlassian", "Team Topologies", "GitHub", "Google SRE", "PagerDuty", "NIST", "FIRST", "MITRE"):
        assert source in text
    assert "Design inferences and limits" in text
    assert "Anti-patterns" in text
