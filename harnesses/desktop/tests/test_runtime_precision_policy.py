import datetime as dt
import json
import os
import pathlib
import stat
import subprocess
import importlib.util


CLI = pathlib.Path(__file__).parents[1] / "desktop.py"
SPEC = importlib.util.spec_from_file_location("desktop_harness", CLI)
DESKTOP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DESKTOP)


def make_backend(tmp_path, observe_rows, *, verify="ok"):
    path = tmp_path / "precision-backend"
    log = tmp_path / "backend.jsonl"
    rows = repr(observe_rows)
    body = f'''#!/usr/bin/env python3
import json, pathlib, sys, time
log=pathlib.Path({str(log)!r})
with log.open("a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")
if sys.argv[1:3] == ["observe", "--json"]:
 rows={rows}; count=sum(1 for line in log.read_text().splitlines() if json.loads(line)[:2] == ["observe", "--json"])
 print(json.dumps(rows[min(count-1,len(rows)-1)]))
elif sys.argv[1:2] == ["verify"] and {verify!r} == "timeout": time.sleep(2)
'''
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path, log


def invoke(command, payload, backend, run_root, key="precision", extra=()):
    argv = [str(CLI), command, "--input", json.dumps(payload), "--idempotency-key", key,
            "--run-root", str(run_root), *extra]
    result = subprocess.run(argv, text=True, capture_output=True,
                            env={**os.environ, "DESKTOP_SYSTEM_CLI": str(backend),
                                 "DESKTOP_RUNS_ROOT": str(run_root.parent)})
    return result, json.loads(result.stdout)


def approve(tmp_path, command, payload, backend, run_root, key="precision"):
    result, output = invoke(command, payload, backend, run_root, key, ("--dry-run",))
    assert result.returncode == 0
    receipt = tmp_path / (key + "-approval.json")
    receipt.write_text(json.dumps({
        "requestDigest": output["result"]["requestDigest"],
        "expiresAt": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)).isoformat(),
    }))
    return receipt


def payload(kind="accessibility"):
    target = {"kind": kind, "windowId": "win-1", "observedRevision": 7,
              "targetDigest": "target-v7"}
    if kind == "accessibility": target["nodeId"] = "node-9"
    if kind == "image": target.update(templateHash="sha256:template", screenshotDigest="sha256:screen", visualRegion=[0,0,10,10], confidence=.99)
    if kind == "coordinate": target.update(x=10, y=11, screenshotDigest="sha256:screen", visualRegion=[0,0,10,10], monitor="DP-1", scale=1.25)
    return {"target": target, "postcondition": {"kind": "state", "equals": "open"}}


def calls(log):
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def test_accessibility_target_is_observed_and_postcondition_confirmed(tmp_path):
    observed = {"revision": 7, "targetDigest": "target-v7", "windowId": "win-1", "focused": True}
    backend, log = make_backend(tmp_path, [observed])
    run_root = tmp_path / "run"
    body = payload(); receipt = approve(tmp_path, "pointer.click", body, backend, run_root)
    result, output = invoke("pointer.click", body, backend, run_root, extra=("--approval-file", str(receipt)))
    assert result.returncode == 0 and output["result"]["postconditionConfirmed"] is True
    assert [row[0] for row in calls(log)] == ["observe", "click", "verify"]


def test_stale_target_gets_only_bounded_reobservation_and_no_click(tmp_path):
    stale = {"revision": 8, "targetDigest": "moved", "windowId": "win-1", "focused": True}
    backend, log = make_backend(tmp_path, [stale, stale])
    run_root = tmp_path / "run"
    body = payload(); receipt = approve(tmp_path, "pointer.click", body, backend, run_root)
    result, output = invoke("pointer.click", body, backend, run_root, extra=("--approval-file", str(receipt)))
    assert result.returncode == 20 and output["error"]["code"] == "STALE_TARGET"
    assert [row[0] for row in calls(log)] == ["observe", "observe"]


def test_visual_fallback_is_explicit_and_loses_to_accessibility(tmp_path):
    observed = {"revision": 7, "targetDigest": "target-v7", "windowId": "win-1", "focused": True, "accessibilityMatch": True}
    backend, log = make_backend(tmp_path, [observed])
    run_root = tmp_path / "run"
    body = payload("image"); body["visionFallbackSupported"] = True
    receipt = approve(tmp_path, "image.click", body, backend, run_root)
    result, output = invoke("image.click", body, backend, run_root, extra=("--approval-file", str(receipt)))
    assert result.returncode == 31 and output["error"]["code"] == "ACCESSIBILITY_TARGET_AVAILABLE"
    assert [row[0] for row in calls(log)] == ["observe"]


def test_focus_is_reobserved_before_action(tmp_path):
    base = {"revision": 7, "targetDigest": "target-v7", "windowId": "win-1"}
    backend, log = make_backend(tmp_path, [{**base, "focused": False}, {**base, "focused": True}])
    run_root = tmp_path / "run"
    body = payload(); receipt = approve(tmp_path, "pointer.click", body, backend, run_root)
    result, _ = invoke("pointer.click", body, backend, run_root, extra=("--approval-file", str(receipt)))
    assert result.returncode == 0
    assert [row[0] for row in calls(log)] == ["observe", "focus", "observe", "click", "verify"]


def test_uncertain_click_is_never_replayed_with_same_idempotency_key(tmp_path):
    observed = {"revision": 7, "targetDigest": "target-v7", "windowId": "win-1", "focused": True}
    backend, log = make_backend(tmp_path, [observed], verify="timeout")
    run_root = tmp_path / "run"
    body = payload(); receipt = approve(tmp_path, "pointer.click", body, backend, run_root)
    flags = ("--approval-file", str(receipt), "--timeout-ms", "30")
    first, output = invoke("pointer.click", body, backend, run_root, extra=flags)
    assert first.returncode == 40 and output["error"]["code"] == "OUTCOME_UNKNOWN"
    second, output = invoke("pointer.click", body, backend, run_root, extra=flags)
    assert second.returncode == 40 and output["error"]["code"] == "OUTCOME_UNKNOWN"
    assert [row[0] for row in calls(log)].count("click") == 1


def test_precision_pointer_actions_do_not_deadlock_at_same_position(monkeypatch):
    monkeypatch.setattr(DESKTOP.shutil, "which", lambda _: "/usr/bin/xdotool")
    coordinate = {"kind": "coordinate", "x": 10, "y": 11}
    image = {"kind": "image", "visualRegion": [20, 30, 40, 10]}
    trajectory = {"points": [[1, 2], [3, 4], [5, 6]]}
    argvs = [
        DESKTOP.safe_pointer_argv(coordinate, "keyboard.type", ["display"]),
        DESKTOP.safe_pointer_argv(coordinate, "pointer.click"),
        DESKTOP.safe_pointer_argv(image, "image.click"),
        DESKTOP.safe_pointer_argv(coordinate, "pointer.drag-drop", trajectory=trajectory),
    ]
    assert all("--sync" not in argv for argv in argvs)
    assert argvs[0][-1] == "display"
    assert argvs[2][1:4] == ["mousemove", "40", "35"]
    assert argvs[3][-2:] == ["mouseup", "1"]


def test_coordinate_keyboard_postcondition_uses_bounded_visual_readback(monkeypatch):
    class Result:
        returncode = 0
        stdout = "win-1\n"
    monkeypatch.setattr(DESKTOP.shutil, "which", lambda _: "/usr/bin/xdotool")
    monkeypatch.setattr(DESKTOP.subprocess, "run", lambda *a, **k: Result())
    geometry = {"X": 1, "Y": 2, "WIDTH": 300, "HEIGHT": 200}
    monkeypatch.setattr(DESKTOP, "xwindow_geometry", lambda _: geometry)
    post = {"searchFieldText": "display", "windowBoundsUnchanged": True}
    target = {"windowId": "win-1"}
    confirmed, proof = DESKTOP.verify_effect(post, target, geometry, before_visual="before", after_visual="after")
    assert confirmed is True and proof["searchRegionChanged"] is True and proof["typedLiteral"] == "display"
    confirmed, proof = DESKTOP.verify_effect(post, target, geometry, before_visual="same", after_visual="same")
    assert confirmed is False and proof["searchRegionChanged"] is False


def test_drag_trajectory_is_linear_and_bounded(tmp_path):
    observed = {"revision": 7, "targetDigest": "target-v7", "windowId": "win-1", "focused": True}
    backend, log = make_backend(tmp_path, [observed])
    run_root = tmp_path / "run"
    body = payload(); body["drag"] = {"start": [0, 2], "end": [10, 12], "steps": 2, "durationMs": 200}
    receipt = approve(tmp_path, "pointer.drag-drop", body, backend, run_root)
    result, output = invoke("pointer.drag-drop", body, backend, run_root, extra=("--approval-file", str(receipt)))
    assert result.returncode == 0
    assert output["result"]["trajectory"]["points"] == [[0.0, 2.0], [5.0, 7.0], [10.0, 12.0]]
    drag_call = next(row for row in calls(log) if row[0] == "pointer-drag-drop")
    assert "--trajectory-json" in drag_call
