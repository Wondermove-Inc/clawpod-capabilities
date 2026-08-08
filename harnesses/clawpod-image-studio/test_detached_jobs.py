import datetime as dt
import importlib.util
import json
import os
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("image_studio_detached_test", HERE / "clawpod_image_studio.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def approved(root: Path):
    r = mod.root(str(root))
    rec = {"state": "connected", "pointer": "msp_test_pointer_123456"}
    mod.atomic(r / "connections.json", {"openai": rec})
    request = {
        "operation": "generate",
        "provider": "openai",
        "model": "gpt-image-1",
        "prompt": "detached test prompt",
        "count": 1,
        "output": "tests/out.png",
        "format": "png",
        "options": {},
        "safetyPolicy": "approved test",
        "rightsPolicy": "owned test",
        "publicationPolicy": "not for publication",
        "maxUsd": 0.04,
        "expiresAt": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
    }
    prepared = mod.prepare(request, r)
    return r, {k: v for k, v in prepared.items() if k != "estimate"}


def wait_terminal(r, job_id, seconds=5):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        state = mod.job_status(r, job_id)
        if state["terminal"]:
            return state
        time.sleep(0.03)
    pytest.fail("job did not become terminal")


def test_detached_success_collect_duplicate_and_secret_protection(tmp_path, monkeypatch):
    r, payload = approved(tmp_path)
    canary = "sk-test-detached-secret-canary-123456"
    monkeypatch.setenv("OPENAI_API_KEY", canary)
    monkeypatch.setenv("CLAWPOD_IMAGE_STUDIO_TRANSPORT", "mock-success")
    started_at = time.monotonic()
    started = mod.job_start({**payload, "timeoutSeconds": 60}, r)
    assert time.monotonic() - started_at < 5
    assert started["state"] == "queued"
    assert started["automaticRetry"] is False
    state = wait_terminal(r, started["jobId"])
    assert state["state"] == "succeeded"
    monkeypatch.delenv("OPENAI_API_KEY")
    one = mod.job_collect(r, started["jobId"])
    two = mod.job_collect(r, started["jobId"])
    assert one == two
    assert one["artifacts"][0]["sha256"].startswith("sha256:")
    all_job_bytes = b"".join(p.read_bytes() for p in (r / "jobs" / started["jobId"]).iterdir() if p.is_file())
    assert canary.encode() not in all_job_bytes
    monkeypatch.setenv("OPENAI_API_KEY", canary)
    with pytest.raises(mod.E) as duplicate:
        mod.job_start({**payload, "timeoutSeconds": 60}, r)
    assert duplicate.value.code == "PAID_JOB_EXISTS"


def test_timeout_and_crash_are_ambiguous_without_retry(tmp_path, monkeypatch):
    for index, mode in enumerate(("mock-timeout", "mock-crash")):
        r, payload = approved(tmp_path / str(index))
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real-123456789")
        monkeypatch.setenv("CLAWPOD_IMAGE_STUDIO_TRANSPORT", mode)
        monkeypatch.setenv("CLAWPOD_IMAGE_STUDIO_MOCK_DELAY", "0.01")
        started = mod.job_start({**payload, "timeoutSeconds": 60}, r)
        state = wait_terminal(r, started["jobId"])
        assert state["state"] == "ambiguous"
        assert state["billingState"] == "unknown"
        assert state["automaticRetry"] is False


def test_invalid_inputs_and_local_commands_need_no_credential(tmp_path, monkeypatch):
    r, payload = approved(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real-123456789")
    with pytest.raises(mod.E) as invalid:
        mod.job_start({**payload, "timeoutSeconds": 59}, r)
    assert invalid.value.code == "SCHEMA_VIOLATION"
    with pytest.raises(mod.E):
        mod.job_start({**payload, "timeoutSeconds": 60, "secretRefs": ["forbidden"]}, r)
    monkeypatch.setenv("CLAWPOD_IMAGE_STUDIO_TRANSPORT", "mock-success")
    started = mod.job_start({**payload, "timeoutSeconds": 60}, r)
    wait_terminal(r, started["jobId"])
    monkeypatch.delenv("OPENAI_API_KEY")
    assert mod.job_status(r, started["jobId"])["terminal"]
    assert mod.job_collect(r, started["jobId"])["state"] == "succeeded"
