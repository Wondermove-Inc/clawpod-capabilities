import importlib.util
import json
import pathlib

LAB = pathlib.Path(__file__).parents[1] / "precision_lab"
SPEC = importlib.util.spec_from_file_location("precision_benchmark", LAB / "precision_benchmark.py")
BENCH = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(BENCH)


def test_matrix_covers_required_environment_extremes():
    envs = BENCH.load(LAB / "environment-matrix.json")["environments"]
    assert {(e["width"], e["height"]) for e in envs} >= {(1280, 720), (3840, 2160)}
    assert {e["theme"] for e in envs} == {"dark", "light"}
    assert {e["dbusSession"] for e in envs} == {False, True}
    assert len({e["scale"] for e in envs}) >= 4


def test_scenarios_cover_precision_and_interaction_contracts():
    names = set(BENCH.SCENARIOS)
    for required in ("moving-constant-fast", "moving-accelerating", "target-1px", "target-32px", "occlusion", "canvas-image-only", "multi-window-focus-steal", "modal-popup-race", "drag-trajectory", "double-click-timing", "key-chords", "clipboard-dialog", "file-dialog"):
        assert required in names


def test_run_is_deterministic_safe_and_emits_png_evidence(tmp_path):
    first, second = tmp_path/"first", tmp_path/"second"
    assert BENCH.run(first, samples=3, soak_events=320) == 1  # deliberately below duration gate
    assert BENCH.run(second, samples=3, soak_events=320) == 1
    a=json.loads((first/"baseline.json").read_text()); b=json.loads((second/"baseline.json").read_text())
    a["metrics"].pop("benchmarkWallTimeMs"); b["metrics"].pop("benchmarkWallTimeMs")
    assert a == b
    assert a["metrics"]["falseClicks"] == a["metrics"]["unsafeSideEffects"] == 0
    assert a["metrics"]["droppedInputs"] == a["metrics"]["duplicateInputs"] == 0
    assert (first/"contact-sheet.png").read_bytes().startswith(b"\x89PNG")
    assert len(list((first/"frames").glob("*.png"))) == len(BENCH.SCENARIOS)


def test_full_soak_passes_all_thresholds(tmp_path):
    assert BENCH.run(tmp_path/"full", samples=4, soak_events=36000) == 0
    result=json.loads((tmp_path/"full"/"baseline.json").read_text())
    assert result["passed"] and all(result["checks"].values())
    assert result["metrics"]["acceleratedSoak"]["equivalentSeconds"] == 3600
    assert result["publication"] == "prohibited"
    assert "CAPTCHA bypass" in result["excluded"]
