import json, os, pathlib, stat, subprocess, tempfile, time

CLI = pathlib.Path(__file__).parents[1] / "desktop.py"
RUNS = pathlib.Path("/workspace/desktop-runs")


def backend(tmp_path, body):
    path = tmp_path / "backend"
    path.write_text("#!/usr/bin/env python3\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def run(command, payload=None, *, env=None, extra=()):
    argv = [str(CLI), command, "--input", json.dumps(payload or {})] + list(extra)
    result = subprocess.run(argv, text=True, capture_output=True, env={**os.environ, **(env or {})})
    return result, json.loads(result.stdout)


def test_timeout_is_bounded_and_retryable(tmp_path):
    mock = backend(tmp_path, "import time; time.sleep(2)\n")
    started = time.monotonic()
    result, output = run("ui.observe", env={"DESKTOP_SYSTEM_CLI": mock}, extra=("--timeout-ms", "1"))
    assert time.monotonic() - started < 1.5
    assert result.returncode == 21
    assert output["error"]["code"] == "TIMEOUT" and output["retry"]["retryable"]


def test_backend_crash_and_stale_target_have_no_false_success(tmp_path):
    mock = backend(tmp_path, "import sys; print('stale target', file=sys.stderr); raise SystemExit(3)\n")
    result, output = run("ui.find", {"args": ["moved-window"]}, env={"DESKTOP_SYSTEM_CLI": mock})
    assert result.returncode == 20
    assert output["status"] == "failed" and output["error"]["code"] == "TARGET_NOT_FOUND"


def test_atspi_loss_is_classified_retryable(tmp_path):
    mock = backend(tmp_path, "import sys; print('registry unavailable', file=sys.stderr); raise SystemExit(4)\n")
    result, output = run("ui.observe", env={"DESKTOP_SYSTEM_CLI": mock})
    assert result.returncode == 24
    assert output["error"]["code"] == "AT_SPI_UNAVAILABLE"
    assert output["error"]["retryable"] is True


def test_backend_echo_cannot_exfiltrate_named_secret(tmp_path):
    mock = backend(tmp_path, "print('token=super-secret-value')\n")
    result, output = run("ui.observe", {"token": "super-secret-value"}, env={"DESKTOP_SYSTEM_CLI": mock})
    assert result.returncode == 0
    serialized = json.dumps(output)
    assert "super-secret-value" not in serialized
    assert "[REDACTED]" in serialized


def test_coordinate_action_requires_preview_and_never_hits_backend(tmp_path):
    marker = tmp_path / "called"
    mock = backend(tmp_path, f"from pathlib import Path; Path({str(marker)!r}).write_text('unsafe')\n")
    result, output = run("image.click", {"args": ["--allow-coordinate"]}, env={"DESKTOP_SYSTEM_CLI": mock}, extra=("--idempotency-key", "coord"))
    assert result.returncode == 30 and output["error"]["code"] == "APPROVAL_REQUIRED"
    assert not marker.exists()


def test_captcha_refusal_precedes_backend_and_artifact_creation(tmp_path):
    marker = tmp_path / "called"
    mock = backend(tmp_path, f"from pathlib import Path; Path({str(marker)!r}).write_text('unsafe')\n")
    result, output = run("ui.find", {"label": "Verify you are human"}, env={"DESKTOP_SYSTEM_CLI": mock})
    assert result.returncode == 32 and output["error"]["code"] == "HUMAN_VERIFICATION"
    assert not marker.exists()


def test_revision_conflict_and_idempotency_conflict_are_side_effect_free(tmp_path):
    run_root = RUNS / ("adversarial-" + next(tempfile._get_candidate_names()))
    try:
        base = ("--run-root", str(run_root), "--idempotency-key", "same", "--dry-run")
        assert run("task.plan", {"workflow": "text-editor"}, extra=base)[0].returncode == 0
        # Dry-run must not create state or consume an idempotency key.
        assert not (run_root / "state.json").exists()
        result, output = run("task.plan", {"workflow": "file-picker"}, extra=("--run-root", str(run_root), "--idempotency-key", "next", "--expected-revision", "9", "--dry-run"))
        assert result.returncode == 41 and output["error"]["code"] == "REVISION_CONFLICT"
        assert not (run_root / "state.json").exists()
    finally:
        if run_root.exists():
            import shutil; shutil.rmtree(run_root)


def test_internal_app_matrix_dry_runs_are_redacted_and_non_mutating(tmp_path):
    workflows = ["browser-native", "file-manager", "text-editor", "settings", "file-picker", "download", "clipboard", "drag-drop", "window-focus", "multi-window"]
    for index, workflow in enumerate(workflows):
        result, output = run("task.plan", {"workflow": workflow, "password": "matrix-secret"}, extra=("--idempotency-key", f"wf-{index}", "--dry-run"))
        assert result.returncode == 0 and output["result"]["wouldExecute"]
        assert "matrix-secret" not in json.dumps(output)
