"""App distribution contract: offline selection, valid endpoints, and sign-in isolation."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def run_info(tmp_path, *options, package=ROOT):
    env = {**os.environ, "CLAWPOD_NODE_HOST_FIXTURE": str(tmp_path / "missing-fixture.json"), "CLAWPOD_NODE_HOST_RECORD": str(tmp_path / "record.jsonl")}
    run = subprocess.run([sys.executable, str(package / "clawpod_node_host.py"), "--json", "installer", "info", *options], cwd=tmp_path, env=env, text=True, capture_output=True)
    assert run.stdout.count("\n") == 1, run.stderr
    assert not (tmp_path / "state.json").exists()
    assert not (tmp_path / "record.jsonl").exists()
    return run, json.loads(run.stdout)


@pytest.mark.parametrize("platform,arch,suffix", [("linux", "x64", "linux-x64.deb"), ("macos", "arm64", "darwin-arm64.pkg"), ("macos", "x64", "darwin-x64.pkg"), ("windows", "x64", "win32-x64.exe")])
def test_selects_real_manifest_artifact_without_legacy_preflight(tmp_path, platform, arch, suffix):
    run, out = run_info(tmp_path, "--platform", platform, "--arch", arch)
    assert run.returncode == 0 and out["ok"]
    manifest = json.loads((ROOT / "installer-manifest.json").read_text())
    artifact = next(item for item in manifest["artifacts"] if item["platform"] == platform and item["arch"] == arch)
    assert all(out["installer"][key] == value for key, value in artifact.items())
    assert out["installer"]["filename"].endswith(suffix)
    assert out["installer"]["version"] == manifest["version"]
    assert out["installer"]["runtimeVersion"] == manifest["runtimeVersion"]
    expected_validation = dict(manifest["validation"])
    expected_validation["desktopStartup"] = expected_validation.pop("desktopLoginStartup")
    assert out["installer"]["validation"] == expected_validation
    assert out["installer"]["remoteAvailability"] == "unchecked"
    assert out["effects"] == [] and out["safetyClass"] == "S0"
    assert not {"tailscale", "service", "pairing", "version"}.intersection(out)
    assert "Start node" in out["guidance"]["operations"]["start"]
    assert "Reconnect" in out["guidance"]["operations"]["restart"]
    assert "Agent Control UI" in out["guidance"]["operations"]["status"]
    assert "~/.openclaw" in out["guidance"]["stateCompatibility"]
    assert "agent and computer Tailscale sign-in" in out["guidance"]["network"]


@pytest.mark.parametrize("options,code", [((), "INSTALLER_TARGET_REQUIRED"), (("--platform", "macos"), "INSTALLER_TARGET_REQUIRED"), (("--platform", "linux", "--arch", "arm64"), "INSTALLER_TARGET_UNSUPPORTED"), (("--platform", "windows", "--arch", "arm64"), "INSTALLER_TARGET_UNSUPPORTED")])
def test_target_must_describe_supported_user_computer(tmp_path, options, code):
    run, out = run_info(tmp_path, *options)
    assert run.returncode == 2 and out["errors"][0]["code"] == code


@pytest.mark.parametrize("url,normalized,opt_in", [
    ("wss://gateway.example.com:18789/", "wss://gateway.example.com:18789", False),
    ("wss://gateway.tailnet.ts.net", "wss://gateway.tailnet.ts.net", False),
    ("ws://192.168.1.10:18789", "ws://192.168.1.10:18789", False),
    ("ws://computer.local:18789", "ws://computer.local:18789", False),
    ("ws://localhost:18789", "ws://localhost:18789", False),
    ("ws://100.64.0.10", "ws://100.64.0.10", False),
    ("ws://[::ffff:100.64.1.2]", "ws://[::ffff:6440:102]", False),
    ("wss://[2001:db8::1]:18789", "wss://[2001:db8::1]:18789", False),
    ("ws://[fd00::1]:18789", "ws://[fd00::1]:18789", False),
    ("ws://127.1", "ws://127.0.0.1", False),
    ("ws://2130706433", "ws://127.0.0.1", False),
    ("ws://0x7f000001", "ws://127.0.0.1", False),
    ("ws://0177.0.0.1", "ws://127.0.0.1", False),
    ("ws://%31%32%37.1", "ws://127.0.0.1", False),
    ("ws://192.168.257", "ws://192.168.1.1", False),
    ("ws://127.0.0.1.", "ws://127.0.0.1", False),
    ("wss://gateway_name", "wss://gateway_name", False),
    ("WSS://GATEWAY.EXAMPLE.COM", "wss://gateway.example.com", False),
    ("wss://gateway.0xg", "wss://gateway.0xg", False),
    ("wss://gateway..example", "wss://gateway..example", False),
    ("wss://-gateway.example", "wss://-gateway.example", False),
    ("wss://" + "a" * 64 + ".example", "wss://" + "a" * 64 + ".example", False),
    ("wss://gateway.example.com:", "wss://gateway.example.com", False),
    ("wss://gateway.example.com:443", "wss://gateway.example.com", False),
    ("wss://straße.example", "wss://straße.example", False),
    ("wss://stra%C3%9Fe.example", "wss://straße.example", False),
    ("wss://xn--strae-oqa.example", "wss://xn--strae-oqa.example", False),
])
def test_gateway_root_matches_app_transport_contract(tmp_path, url, normalized, opt_in):
    run, out = run_info(tmp_path, "--platform", "linux", "--arch", "x64", "--gateway-url", url)
    assert run.returncode == 0
    assert out["gateway"] == {"url": normalized, "privateWsOptInRequired": opt_in}


@pytest.mark.parametrize("host,accepted", [
    ("10.0.0.0", True), ("10.255.255.255", True),
    ("172.16.0.0", True), ("172.31.255.255", True),
    ("192.168.0.0", True), ("192.168.255.255", True),
    ("100.64.0.0", True), ("100.127.255.255", True),
    ("[fc00::1]", True), ("[fdff:ffff:ffff:ffff:ffff:ffff:ffff:ffff]", True),
    ("[fe80::1]", True), ("[febf::1]", True),
    ("[::ffff:192.168.1.2]", True), ("[fd7a:115c:a1e0::1]", True),
    ("9.255.255.255", False), ("11.0.0.0", False),
    ("172.15.255.255", False), ("172.32.0.0", False),
    ("192.167.255.255", False), ("192.169.0.0", False),
    ("100.63.255.255", False), ("100.128.0.0", False),
    ("[fbff::1]", False), ("[fe00::1]", False), ("[fec0::1]", False),
    ("[::]", False), ("[ff02::1]", False), ("[::ffff:8.8.8.8]", False),
])
def test_private_address_boundaries_need_no_opt_in(tmp_path, host, accepted):
    run, out = run_info(tmp_path, "--platform", "macos", "--arch", "arm64",
                        "--gateway-url", f"ws://{host}:18789")
    assert out["ok"] is accepted
    if accepted:
        assert run.returncode == 0
        assert out["gateway"]["privateWsOptInRequired"] is False
    else:
        assert run.returncode == 2
        assert out["errors"][0]["code"] == "INVALID_GATEWAY_URL"


@pytest.mark.parametrize("url", [
    "wss://1.2.3.999", "wss://1.2.3.4.5", "wss://gateway.123", "wss://gateway.09", "wss://1.2.3.08", "wss://4294967296", "wss://256.1", "wss://1..1", "wss://0x100000000", "wss://gateway%2fexample", "wss://gateway%00example", "wss://gateway%zzexample", "wss://[fe80::1%25eth0]", "wss://[fe80::1%eth0]",
    "https://gateway.example.com", "wss://gateway.example.com/dashboard", "wss://gateway.example.com/a/..", "wss://gateway.example.com/%2e/", "wss://gateway.example.com?token=CANARY-SECRET", "wss://gateway.example.com#CANARY-SECRET", "wss://user:CANARY-SECRET@gateway.example.com", "wss://@gateway.example.com", "wss://gateway.example.com?", "wss://gateway.example.com#", "wss://gateway.example.com:0", "wss://gateway.example.com:65536", "wss://gateway.example.com\\dashboard", "wss://gate\nway.example.com", "ws://gateway.example.com", "ws://gateway.tailnet.ts.net", "", "wss://[broken",
])
def test_rejects_bad_gateway_without_echoing_credentials(tmp_path, url):
    run, out = run_info(tmp_path, "--platform", "macos", "--arch", "arm64", "--gateway-url", url)
    assert run.returncode == 2 and out["errors"][0]["code"] == "INVALID_GATEWAY_URL"
    assert "CANARY-SECRET" not in run.stdout + run.stderr


def standalone_package(tmp_path):
    package = tmp_path / "installed-harness"
    package.mkdir()
    for filename in ("clawpod_node_host.py", "installer.py", "installer-manifest.json"):
        shutil.copyfile(ROOT / filename, package / filename)
    return package


def test_standalone_package_needs_no_repo_or_cli_runtime(tmp_path):
    package = standalone_package(tmp_path)
    run, out = run_info(tmp_path, "--platform", "windows", "--arch", "x64", package=package)
    assert run.returncode == 0 and out["installer"]["manifestSource"] == "bundled"


@pytest.mark.parametrize("damage", ["missing", "json", "download", "checksum", "duplicate", "size", "metadata", "provenance", "provenance-type"])
def test_invalid_packaged_manifest_reports_stable_failure(tmp_path, damage):
    package = standalone_package(tmp_path)
    path = package / "installer-manifest.json"
    value = json.loads(path.read_text())
    if damage == "missing":
        path.unlink()
    elif damage == "json":
        path.write_text("not JSON")
    else:
        if damage == "download":
            value["artifacts"][0]["url"] += "?token=CANARY-SECRET"
        elif damage == "checksum":
            value["artifacts"][0]["sha256"] = None
        elif damage == "duplicate":
            value["artifacts"][0] = value["artifacts"][1]
        elif damage == "size":
            value["artifacts"][0]["bytes"] = True
        elif damage == "provenance":
            value["installerSourceCommit"] = "CANARY-SECRET"
        elif damage == "provenance-type":
            value["installerSourceCommit"] = None
        else:
            value["validation"]["nativeMacOS"] = "CANARY-SECRET"
        path.write_text(json.dumps(value))
    run, out = run_info(tmp_path, "--platform", "linux", "--arch", "x64", package=package)
    assert run.returncode == 6 and out["errors"][0]["code"] == "INSTALLER_MANIFEST_INVALID"
    assert "CANARY-SECRET" not in run.stdout + run.stderr


def test_manifest_arg_map_invokes_command_with_app_native_output(tmp_path):
    contract = json.loads((ROOT / "harness.json").read_text())["commands"]["installer.info"]
    assert contract["safetyClasses"] == ["readOnly"]
    values = {"platform": "macos", "arch": "x64", "gatewayUrl": "wss://gateway.example.com"}
    argv = [sys.executable, str(ROOT / "clawpod_node_host.py"), *contract["baseArgv"]]
    for item in contract["argMap"]:
        argv.extend((item["flag"], values[item["arg"]]))
    run = subprocess.run(argv, cwd=tmp_path, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    assert all(key in out for key in contract["outputSchema"]["required"])
    assert out["installer"]["arch"] == "x64"


def test_linux_option_does_not_enable_legacy_enrollment(tmp_path):
    run = subprocess.run([sys.executable, str(ROOT / "clawpod_node_host.py"), "--json", "enroll", "generate", "--platform", "linux", "--gateway-host", "gateway.example.com"], cwd=tmp_path, text=True, capture_output=True)
    assert run.returncode == 2 and "enrollScript" not in json.loads(run.stdout)


@pytest.mark.parametrize("update,expected", [({}, False), ({"signed": True}, True), ({"signed": False}, False)])
def test_selected_artifact_signing_overrides_release_default(tmp_path, update, expected):
    package = standalone_package(tmp_path)
    path = package / "installer-manifest.json"
    value = json.loads(path.read_text())
    value["signed"] = not expected if update else False
    value["artifacts"][0].update(update)
    path.write_text(json.dumps(value))
    run, out = run_info(tmp_path, "--platform", "linux", "--arch", "x64", package=package)
    assert run.returncode == 0
    assert out["installer"]["signed"] is expected


@pytest.mark.parametrize("update", [{"signed": "true"}, {"notarized": 1}, {"stapled": None}, {"notarized": True, "signed": False}, {"stapled": True, "notarized": False}])
def test_invalid_artifact_signing_metadata(tmp_path, update):
    package = standalone_package(tmp_path)
    path = package / "installer-manifest.json"
    value = json.loads(path.read_text())
    value["artifacts"][0].update(update)
    path.write_text(json.dumps(value))
    run, out = run_info(tmp_path, "--platform", "linux", "--arch", "x64", package=package)
    assert run.returncode == 6
    assert out["errors"][0]["code"] == "INSTALLER_MANIFEST_INVALID"
