import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ADAPTER_PATH = ROOT / "clawpod_cloud_webhooks.py"
SPEC = importlib.util.spec_from_file_location("clawpod_webhooks_adapter", ADAPTER_PATH)
ADAPTER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ADAPTER)


def cli_args(gateway_args):
    """Return only the argv received by the local Click module."""
    return ADAPTER.translate(gateway_args)[3:]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("system.version", ["--json", "system", "version"]),
        ("auth.contract", ["--json", "auth", "contract"]),
    ],
)
def test_gateway_base_argv_commands(command, expected):
    assert cli_args([command]) == expected


def test_local_module_is_used_instead_of_global_console_script():
    translated = ADAPTER.translate(["system.version"])
    assert translated[:3] == [
        sys.executable,
        "-m",
        "cli_anything.clawpod_cloud_webhooks.clawpod_cloud_webhooks_cli",
    ]
    assert "cli-anything-clawpod-cloud-webhooks" not in translated


def test_global_option_is_repositioned_and_resource_id_becomes_positional():
    assert cli_args(
        ["source.get", "--base-url", "https://example.invalid", "--resource-id", "src-1", "--tenant-id", "tenant-1"]
    ) == ["--json", "--base-url", "https://example.invalid", "source", "get", "src-1", "--tenant-id", "tenant-1"]


def test_json_values_are_forwarded_without_reencoding():
    before = '{"name":"old","rules":[1,2]}'
    after = '{"name":"new","rules":[3]}'
    argv = cli_args(
        ["mutation.preview", "--kind", "source", "--resource-id", "src-1", "--tenant-id", "tenant-1", "--before-json", before, "--after-json", after, "--idempotency-key", "idem-1"]
    )
    assert argv[1] == "mutation-preview"
    assert argv[argv.index("--before-json") + 1] == before
    assert argv[argv.index("--after-json") + 1] == after


@pytest.mark.parametrize(("value", "present"), [("true", True), ("false", False)])
def test_gateway_boolean_values_become_click_flags(value, present):
    argv = cli_args(
        ["event.verify", "--event-id", "evt-1", "--tenant-id", "tenant-1", "--require-destination-evidence", value]
    )
    assert ("--require-destination-evidence" in argv) is present


@pytest.mark.parametrize("args", [[], ["unknown.command"], ["source.get", "--resource-id"]])
def test_malformed_or_unknown_gateway_argv_is_structured(args, capsys):
    assert ADAPTER.main(args) == 2
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False
    assert data["error"]["code"] == "adapter_error"


def test_backend_stderr_is_not_exposed(monkeypatch, capsys):
    secret = "Authorization: Bearer should-not-leak"
    monkeypatch.setattr(
        ADAPTER.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 7, stdout='{"ok":false,"error":{"code":"backend"}}', stderr=secret),
    )
    assert ADAPTER.main(["auth.status", "--base-url", "https://example.invalid"]) == 7
    output = capsys.readouterr().out
    assert secret not in output
    assert json.loads(output)["ok"] is False


def test_empty_backend_failure_is_structured_and_redacted(monkeypatch, capsys):
    monkeypatch.setattr(
        ADAPTER.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 9, stdout="", stderr="cookie=should-not-leak"),
    )
    assert ADAPTER.main(["system.version"]) == 9
    data = json.loads(capsys.readouterr().out)
    assert data == {"ok": False, "error": {"code": "cli_error", "message": "CLI execution failed"}}


def test_real_self_contained_adapter_subprocess():
    result = subprocess.run([sys.executable, str(ADAPTER_PATH), "system.version"], text=True, capture_output=True, timeout=10)
    data = json.loads(result.stdout)
    assert result.returncode == 0
    assert data["ok"] is True
    assert data["capability"]["version"] == "0.1.2"
