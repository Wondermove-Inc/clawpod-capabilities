from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "hwp-desktop" / "SKILL.md"
DESCRIPTION = "Use for opening, editing, saving, and exporting HWP/HWPX files on Linux with HOP through Desktop; use clawpod-ocr only for OCR."


def test_description_and_skill_only_surface_are_exact() -> None:
    text = SKILL.read_text(encoding="utf-8")
    metadata = json.loads((SKILL.parent / "capability.json").read_text(encoding="utf-8"))
    assert f'description: "{DESCRIPTION}"' in text
    assert metadata["description"] == DESCRIPTION
    assert metadata["descriptionSource"] == "skill-frontmatter"
    assert not (ROOT / "harnesses" / "hwp-desktop").exists()


def test_routing_composes_desktop_without_colliding_with_ocr_or_web_editing() -> None:
    contracts = json.loads((ROOT / "tests" / "fixtures" / "routing_contracts.json").read_text(encoding="utf-8"))
    contract = contracts["hwp-desktop"]
    assert {"desktop", "clawpod-ocr"} <= set(contract["adjacent"])
    positives = " ".join(contract["positive"])
    assert "HOP" in positives
    assert "Desktop" in positives
    negatives = " ".join(contract["negative"])
    assert "OCR" in negatives
    assert "browser-based office suite" in negatives
    assert "hwp-desktop" in contracts["desktop"]["adjacent"]
    assert "hwp-desktop" in contracts["clawpod-ocr"]["adjacent"]


def test_app_lifecycle_and_rollback_contract_are_explicit() -> None:
    text = SKILL.read_text(encoding="utf-8")
    for phrase in (
        "/workspace/application/hop",
        "versions/<version>/HOP-linux-<arch>.AppImage",
        "활성 버전: `/workspace/application/hop/current` 심볼릭 링크",
        "provenance.json",
        "원자적으로 이동",
        "이전 활성 버전 하나를 보존해 롤백",
        "명시적으로 승인",
        "기존 버전을 유지",
    ):
        assert phrase in text


def test_action_surface_and_observed_limits_fail_closed() -> None:
    text = SKILL.read_text(encoding="utf-8")
    for phrase in (
        "desktop environment.preflight",
        "원본을 직접 덮어쓰지 말고",
        "HWPX는 현재 저장 지원을 가정하지 않는다",
        "HWP/HWPX 열기, 저장, 재열기 또는 PDF 내보내기를 증명했다고 보고하지 않는다",
        "안전한 대표 문서가 없으면 문서 동작 검증을 건너뛰고",
        "`Alt+F`는 종료가 아니라 창 메뉴를 열었으므로",
        "반복 입력하지 않는다",
    ):
        assert phrase in text
