import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ADAPTER = ROOT / "clawpod_cloud_webhooks.py"


def gateway_run(args, tmp_path, response=None, exit_code=0, stderr=""):
    fake = tmp_path / "cli-anything-clawpod-cloud-webhooks"
    payload = response if response is not None else {"ok": True, "argv": []}
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json,sys\n"
        f"payload={payload!r}\n"
        "if 'argv' in payload: payload['argv']=sys.argv[1:]\n"
        "print(json.dumps(payload,separators=(',',':')))\n"
        f"print({stderr!r},file=sys.stderr)\n"
        f"raise SystemExit({exit_code})\n"
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(tmp_path) + os.pathsep + env.get("PATH", "")
    return subprocess.run(
        [sys.executable, str(ADAPTER), *args],
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
    )


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("system.version", ["--json", "system", "version"]),
        ("auth.contract", ["--json", "auth", "contract"]),
    ],
)
def test_gateway_base_argv_commands(command, expected, tmp_path):
    result = gateway_run([command], tmp_path)
    assert result.returncode == 0
    assert json.loads(result.stdout)["argv"] == expected


def test_global_option_is_repositioned_and_resource_id_becomes_positional(tmp_path):
    result = gateway_run(
        ["source.get", "--base-url", "https://example.invalid", "--resource-id", "src-1", "--tenant-id", "tenant-1"],
        tmp_path,
    )
    assert json.loads(result.stdout)["argv"] == [
        "--json", "--base-url", "https://example.invalid", "source", "get", "src-1", "--tenant-id", "tenant-1"
    ]


def test_json_values_are_forwarded_without_reencoding(tmp_path):
    before = '{"name":"old","rules":[1,2]}'
    after = '{"name":"new","rules":[3]}'
    result = gateway_run(
        ["mutation.preview", "--kind", "source", "--resource-id", "src-1", "--tenant-id", "tenant-1", "--before-json", before, "--after-json", after, "--idempotency-key", "idem-1"],
        tmp_path,
    )
    argv = json.loads(result.stdout)["argv"]
    assert argv[1] == "mutation-preview"
    assert argv[argv.index("--before-json") + 1] == before
    assert argv[argv.index("--after-json") + 1] == after


@pytest.mark.parametrize(("value", "present"), [("true", True), ("false", False)])
def test_gateway_boolean_values_become_click_flags(value, present, tmp_path):
    result = gateway_run(
        ["event.verify", "--event-id", "evt-1", "--tenant-id", "tenant-1", "--require-destination-evidence", value],
        tmp_path,
    )
    argv = json.loads(result.stdout)["argv"]
    assert ("--require-destination-evidence" in argv) is present


@pytest.mark.parametrize("args", [[], ["unknown.command"], ["source.get", "--resource-id"]])
def test_malformed_or_unknown_gateway_argv_is_structured(args, tmp_path):
    result = gateway_run(args, tmp_path)
    data = json.loads(result.stdout)
    assert result.returncode == 2
    assert data["ok"] is False
    assert data["error"]["code"] == "adapter_error"


def test_backend_stderr_is_not_exposed(tmp_path):
    secret = "Authorization: Bearer should-not-leak"
    result = gateway_run(["auth.status", "--base-url", "https://example.invalid"], tmp_path, response=None, exit_code=7, stderr=secret)
    data = json.loads(result.stdout)
    assert result.returncode == 7
    assert data["ok"] is True  # stdout is the backend's structured response
    assert secret not in result.stdout


def test_empty_backend_failure_is_structured_and_redacted(tmp_path):
    fake = tmp_path / "cli-anything-clawpod-cloud-webhooks"
    fake.write_text("#!/bin/sh\necho 'cookie=should-not-leak' >&2\nexit 9\n")
    fake.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(tmp_path) + os.pathsep + env.get("PATH", "")
    result = subprocess.run([sys.executable, str(ADAPTER), "system.version"], text=True, capture_output=True, env=env)
    data = json.loads(result.stdout)
    assert result.returncode == 9
    assert data == {"ok": False, "error": {"code": "cli_error", "message": "CLI execution failed"}}
    assert "should-not-leak" not in result.stdout
