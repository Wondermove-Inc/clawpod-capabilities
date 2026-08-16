import hashlib, json, os, shutil, stat, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
CLI = ROOT / "openclaw_node_host.py"
FIXTURE = ROOT / "fixtures" / "macos-ready.json"
NOW = "2026-08-16T15:04:00Z"

def call(tmp_path, command, *, fixture=FIXTURE, extra=(), env=None):
    state = tmp_path / "state.json"
    argv = [sys.executable, str(CLI), "--json", "--state", str(state), *extra, *command.split(" ")]
    e = {**os.environ, "OPENCLAW_NODE_HOST_FIXTURE": str(fixture), "OPENCLAW_NODE_HOST_NOW": NOW, **(env or {})}
    run = subprocess.run(argv, text=True, capture_output=True, env=e)
    assert run.stdout.count("\n") == 1
    return run, json.loads(run.stdout)

BASE = ("--openclaw-version", "2026.4.11", "--gateway-host", "gateway.tailnet.ts.net", "--gateway-port", "18789", "--tls", "--request-id", "11111111-1111-4111-8111-111111111111")

def test_only_literal_version_is_accepted(tmp_path):
    rejected = [None, "latest", "next", "^2026.4.11", "~2026.4.11", ">=2026.4.11", "2026.4.x", "https://invalid/x", "npm:alias"]
    for version in rejected:
        options = ["--gateway-host", "gateway.tailnet.ts.net", "--gateway-port", "18789"]
        if version is not None: options[:0] = ["--openclaw-version", version]
        run, out = call(tmp_path, "install plan", extra=options)
        assert run.returncode == 2 and out["errors"][0]["code"] == "VERSION_SPEC_REJECTED"
    assert call(tmp_path, "install plan", extra=BASE)[0].returncode == 0

def fixture(tmp_path, **tailscale):
    value = json.loads(FIXTURE.read_text()); value["tailscale"].update(tailscale)
    path = tmp_path / (str(len(list(tmp_path.iterdir()))) + ".json"); path.write_text(json.dumps(value)); return path

def test_tailscale_fail_closed_actions_and_no_mutation(tmp_path):
    record = tmp_path / "record.jsonl"
    cases = [
        ({"present": False}, "TAILSCALE_NOT_INSTALLED", "Install Tailscale on this node, sign in to the same account/tailnet as the Gateway, then rerun this command."),
        ({"authenticated": False}, "TAILSCALE_NOT_AUTHENTICATED", "Sign in to Tailscale on this node using the same account/tailnet as the Gateway, then rerun this command."),
        ({"sameTailnet": False, "gatewayIdentity": None}, "TAILNET_UNPROVEN", "Move or sign this node into the Gateway’s tailnet, then rerun this command."),
        ({"reachable": False}, "GATEWAY_UNREACHABLE", "Restore Tailscale reachability to gateway.tailnet.ts.net:18789, then rerun this command."),
    ]
    for changes, code, action in cases:
        run, out = call(tmp_path, "install plan", fixture=fixture(tmp_path, **changes), extra=BASE, env={"OPENCLAW_NODE_HOST_RECORD": str(record)})
        assert out["errors"][0]["code"] == code and out["nextAction"]["message"] == action
    assert not record.exists()

def test_plan_confirmation_and_provider_start_recording(tmp_path):
    record = tmp_path / "record.jsonl"
    planned, plan_out = call(tmp_path, "install plan", extra=BASE, env={"OPENCLAW_NODE_HOST_RECORD": str(record)})
    plan = plan_out["planDocument"]
    apply_options = (*BASE, "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"])
    applied, out = call(tmp_path, "install apply", extra=apply_options, env={"OPENCLAW_NODE_HOST_RECORD": str(record)})
    assert applied.returncode == 0 and out["service"]["registered"]
    lines = [json.loads(x)["argv"] for x in record.read_text().splitlines()]
    assert ["openclaw", "node", "install"] in lines
    assert all(argv[:2] != ["tailscale", "up"] for argv in lines)

def test_lifecycle_plan_uses_supported_restart_for_start(tmp_path):
    record = tmp_path / "record.jsonl"
    _, planned = call(tmp_path, "service status", extra=(*BASE, "--lifecycle-action", "start"))
    plan = planned["planDocument"]
    run, out = call(tmp_path, "service start", extra=(*BASE, "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"]), env={"OPENCLAW_NODE_HOST_RECORD": str(record)})
    assert run.returncode == 0 and out["service"]["providerOperation"] == "restart"
    assert json.loads(record.read_text().splitlines()[0])["argv"] == ["openclaw", "node", "restart"]

def test_confirmation_is_action_and_plan_bound(tmp_path):
    _, out = call(tmp_path, "install plan", extra=BASE)
    plan = out["planDocument"]
    run, failed = call(tmp_path, "install apply", extra=(*BASE, "--plan-id", plan["id"], "--confirm", "0" * 64))
    assert run.returncode == 4 and failed["errors"][0]["code"] == "CONFIRMATION_MISMATCH"

def test_secret_canary_never_appears(tmp_path):
    canary = "password=CANARY-PLAINTEXT"
    bad = fixture(tmp_path); value = json.loads(bad.read_text()); value["diagnostic"] = canary; bad.write_text(json.dumps(value))
    run, _ = call(tmp_path, "system inspect", fixture=bad, env={"OPENCLAW_GATEWAY_TOKEN": canary})
    assert "CANARY-PLAINTEXT" not in run.stdout + run.stderr

def test_system_probe_uses_nodes_invoke_and_shell_uses_exec_host_node(tmp_path):
    record = tmp_path / "record.jsonl"
    run, out = call(tmp_path, "validate run", extra=("--validation-level", "system", "--shell-probe"), env={"OPENCLAW_NODE_HOST_RECORD": str(record)})
    assert run.returncode == 0
    lines = [json.loads(x)["argv"] for x in record.read_text().splitlines()]
    assert ["openclaw", "nodes", "invoke", "--method", "system.which"] in lines
    assert ["openclaw", "exec", "--host", "node", "--", "<harmless-probe>"] in lines
    assert not any("system.run" in argv for argv in lines)

def test_mac_and_windows_provider_fixtures_are_user_scoped(tmp_path):
    for name, provider in (("macos-ready.json", "launchd"), ("windows-ready.json", "schtasks")):
        run, out = call(tmp_path, "system inspect", fixture=ROOT / "fixtures" / name)
        assert run.returncode == 0 and out["service"]["provider"] == provider
    source = CLI.read_text()
    assert "LaunchDaemon" not in source and "Windows Service" not in source

def test_offline_installer_exposes_command_and_subprocess_runs_it(tmp_path):
    bindir = tmp_path / "bin"
    install = subprocess.run([sys.executable, str(ROOT / "scripts" / "install.py"), "--bin-dir", str(bindir)], text=True, capture_output=True, check=True)
    installed = Path(install.stdout.strip())
    env = {**os.environ, "OPENCLAW_NODE_HOST_FIXTURE": str(FIXTURE), "OPENCLAW_NODE_HOST_NOW": NOW}
    run = subprocess.run([str(installed), "--json", "system", "inspect"], text=True, capture_output=True, env=env)
    assert run.returncode == 0 and json.loads(run.stdout)["command"] == "system.inspect"

def test_schemas_and_error_table_are_machine_readable():
    for path in (ROOT / "schemas").glob("*.json"):
        assert isinstance(json.loads(path.read_text()), dict)
    table = json.loads((ROOT / "schemas" / "error-exit-codes.json").read_text())
    assert table["exitCodes"]["rollbackFailed"] == 8 and "TAILNET_UNPROVEN" in table["errors"]

def test_shared_description_is_byte_identical():
    manifest = json.loads((ROOT / "harness.json").read_text())
    frontmatter = (ROOT.parents[1] / "skills" / "openclaw-node-host" / "SKILL.md").read_text().splitlines()[2]
    assert json.loads(frontmatter.split(":", 1)[1].strip()) == manifest["description"]

def test_no_tailscale_mutating_command_graph():
    manifest = json.loads((ROOT / "harness.json").read_text())
    serialized = json.dumps(manifest["commands"])
    for forbidden in ('"tailscale", "up"', '"tailscale", "login"', '"tailscale", "logout"', '"tailscale", "set"'):
        assert forbidden not in serialized
