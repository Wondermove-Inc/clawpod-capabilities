from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "hwp-desktop" / "SKILL.md"
DESCRIPTION = "Use for opening, editing, saving, and exporting HWP/HWPX files on Linux with HOP through Desktop; use clawpod-ocr only for OCR."


def test_description_and_skill_only_surface_are_exact() -> None:
    text = SKILL.read_text(encoding="utf-8")
    metadata = json.loads((SKILL.parent / "capability.json").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "registry" / "index.json").read_text(encoding="utf-8"))
    entry = next(item for item in registry["capabilities"] if item["id"] == "hwp-desktop")
    assert f'description: "{DESCRIPTION}"' in text
    assert metadata["description"] == entry["description"] == DESCRIPTION
    assert len(DESCRIPTION.encode("utf-8")) <= 160
    assert "Hancom Docs" not in text
    assert not (ROOT / "harnesses" / "hwp-desktop").exists()


def test_routing_composes_desktop_without_colliding_with_ocr_or_web_office() -> None:
    contracts = json.loads((ROOT / "tests" / "fixtures" / "routing_contracts.json").read_text(encoding="utf-8"))
    contract = contracts["hwp-desktop"]
    assert {"desktop", "clawpod-ocr"} <= set(contract["adjacent"])
    positives = " ".join(contract["positive"])
    assert all(phrase in positives for phrase in ("HOP", "Desktop", "HWP", "HWPX", "PDF"))
    negatives = " ".join(contract["negative"])
    assert all(phrase in negatives for phrase in ("OCR only", "browser-based office suite", "unrelated native"))


def test_core_routes_complete_practical_surface_to_progressive_references() -> None:
    text = SKILL.read_text(encoding="utf-8")
    for phrase in (
        "파일·세션", "탐색과 편집", "서식", "표", "쪽/구역", "머리말/꼬리말",
        "삽입/개체", "보기/도구", "Save", "PDF export", "Print",
        "observe → focus/context → action → dialog review → postcondition → recovery",
        "references/feature-inventory.md", "references/document-operations.md", "references/app-lifecycle.md",
    ):
        assert phrase in text


def test_verified_upstream_inventory_covers_all_command_families() -> None:
    inventory = (SKILL.parent / "references" / "feature-inventory.md").read_text(encoding="utf-8")
    for phrase in (
        "608d54bbc75af4142bc69c2c2b50c0c217b45731", "f137b4c9468eaff5bb43e25108e9c9d39a2ed15b",
        "New Window", "Open Recent", "file association", "multi-window", "undo/redo",
        "find/find again/find-replace", "character ratio/spacing", "style dialog/apply style",
        "merge/split", "formula/block formula", "page and column breaks", "Header/Footer",
        "equation/create/edit", "bookmark", "footnote", "arrange front/back", "group/ungroup",
        "grid and grid settings", "form mode", "options",
    ):
        assert phrase.lower() in inventory.lower()


def test_desktop_recipes_cover_complete_operations_and_recovery() -> None:
    docs = (SKILL.parent / "references" / "document-operations.md").read_text(encoding="utf-8")
    for phrase in (
        "모든 명령의 공통 recipe", "Open/Recent/File association", "Drag/drop", "Multi-window",
        "Save/Save As/HWP/HWPX", "Export PDF", "Print", "Close/Quit",
        "선택, 입력, 클립보드", "Compare Documents", "문자, 문단, 스타일", "표",
        "쪽, 구역, 머리말/꼬리말", "삽입과 개체", "보기와 도구", "충실도와 복구",
        "autosave/recovery", "재개 조건",
    ):
        assert phrase in docs


def test_app_lifecycle_covers_status_update_rollback_repair_and_failures() -> None:
    app = (SKILL.parent / "references" / "app-lifecycle.md").read_text(encoding="utf-8")
    for phrase in (
        "/workspace/application/hop", "provenance.json", "status", "bootstrap/update",
        "Rollback과 repair", "원자 교체", "FUSE/AppImage", "WebKitGTK",
        "display/D-Bus/AT-SPI", "IME", "font", "crash",
    ):
        assert phrase in app
