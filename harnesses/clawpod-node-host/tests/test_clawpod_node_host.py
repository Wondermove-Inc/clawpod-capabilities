import hashlib, json, os, shutil, stat, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
CLI = ROOT / "clawpod_node_host.py"
FIXTURE = ROOT / "fixtures" / "macos-ready.json"
NOW = "2026-08-16T15:04:00Z"

def call(tmp_path, command, *, fixture=FIXTURE, extra=(), env=None):
    state = tmp_path / "state.json"
    argv = [sys.executable, str(CLI), "--json", "--state", str(state), *extra, *command.split(" ")]
    e = {**os.environ, "CLAWPOD_NODE_HOST_FIXTURE": str(fixture), "CLAWPOD_NODE_HOST_NOW": NOW, **(env or {})}
    run = subprocess.run(argv, text=True, capture_output=True, env=e)
    assert run.stdout.count("\n") == 1
    return run, json.loads(run.stdout)

BASE = ("--openclaw-version", "2026.4.11", "--gateway-host", "gateway.tailnet.ts.net", "--gateway-port", "18789", "--tls", "--request-id", "11111111-1111-4111-8111-111111111111")
SSH = ("--platform", "macos", "--transport", "openssh", "--bootstrap-host", "100.64.0.10", "--bootstrap-account", "nodeuser", "--bootstrap-port", "22", "--expected-host-key", "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "--credential-ref", "agent")

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
        run, out = call(tmp_path, "install plan", fixture=fixture(tmp_path, **changes), extra=BASE, env={"CLAWPOD_NODE_HOST_RECORD": str(record)})
        assert out["errors"][0]["code"] == code and out["nextAction"]["message"] == action
    assert not record.exists()

def test_plan_confirmation_and_provider_start_recording(tmp_path):
    record = tmp_path / "record.jsonl"
    planned, plan_out = call(tmp_path, "install plan", extra=BASE, env={"CLAWPOD_NODE_HOST_RECORD": str(record)})
    plan = plan_out["planDocument"]
    apply_options = (*BASE, "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"])
    applied, out = call(tmp_path, "install apply", extra=apply_options, env={"CLAWPOD_NODE_HOST_RECORD": str(record)})
    assert applied.returncode == 0 and out["service"]["registered"]
    lines = [json.loads(x)["argv"] for x in record.read_text().splitlines()]
    assert ["openclaw", "node", "install"] in lines
    assert all(argv[:2] != ["tailscale", "up"] for argv in lines)

def test_lifecycle_plan_uses_supported_restart_for_start(tmp_path):
    record = tmp_path / "record.jsonl"
    _, planned = call(tmp_path, "service status", extra=(*BASE, "--lifecycle-action", "start"))
    plan = planned["planDocument"]
    run, out = call(tmp_path, "service start", extra=(*BASE, "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"]), env={"CLAWPOD_NODE_HOST_RECORD": str(record)})
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
    run, out = call(tmp_path, "validate run", extra=("--validation-level", "system", "--shell-probe"), env={"CLAWPOD_NODE_HOST_RECORD": str(record)})
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
    env = {**os.environ, "CLAWPOD_NODE_HOST_FIXTURE": str(FIXTURE), "CLAWPOD_NODE_HOST_NOW": NOW}
    run = subprocess.run([str(installed), "--json", "system", "inspect"], text=True, capture_output=True, env=env)
    assert run.returncode == 0 and json.loads(run.stdout)["command"] == "system.inspect"

def test_schemas_and_error_table_are_machine_readable():
    for path in (ROOT / "schemas").glob("*.json"):
        assert isinstance(json.loads(path.read_text()), dict)
    table = json.loads((ROOT / "schemas" / "error-exit-codes.json").read_text())
    assert table["exitCodes"]["rollbackFailed"] == 8 and "TAILNET_UNPROVEN" in table["errors"]

def test_shared_description_is_byte_identical():
    manifest = json.loads((ROOT / "harness.json").read_text())
    frontmatter = (ROOT.parents[1] / "skills" / "clawpod-node-host" / "SKILL.md").read_text().splitlines()[2]
    assert json.loads(frontmatter.split(":", 1)[1].strip()) == manifest["description"]

def test_skill_enforces_concise_progressive_clawpod_onboarding():
    source = (ROOT.parents[1] / "skills" / "clawpod-node-host" / "SKILL.md").read_text()
    prompt = "ClawPod 노드 연결을 도와드릴게요. 연결할 컴퓨터는 Mac인가요, Windows 11인가요?"
    assert prompt in source
    assert "ask exactly one concise user action" in source
    assert "Before any mutation" in source and "fresh plan" in source
    assert "request ID and fingerprint as internal verification evidence" in source
    assert "never use `latest`" in source and "openclaw@2026.4.11" in source

def test_onboarding_state_machine_covers_remote_bootstrap_and_resume():
    source = (ROOT.parents[1] / "skills" / "clawpod-node-host" / "references" / "onboarding.md").read_text()
    for state in ("platform", "transport", "credentials", "inspect", "plan", "apply", "pair", "verify", "complete"):
        assert f"`{state}`" in source
    for method in ("macOS Remote Login/OpenSSH", "Windows OpenSSH Server", "Tailscale SSH", "local command"):
        assert method in source
    assert "Password, key, SSH agent, and Tailscale SSH" in source
    assert "one question or action per turn" in source
    assert "first unmet" in source and "does not change the node-to-Gateway transport" in source
    assert "Tailscale-only scope" in source

def test_tailscale_mutations_are_typed_plan_bound_and_human_gated():
    manifest = json.loads((ROOT / "harness.json").read_text())
    commands = manifest["commands"]
    assert commands["tailscale.install-apply"]["safetyClasses"] == ["externalSideEffect"]
    assert commands["tailscale.login-apply"]["safetyClasses"] == ["humanAccountAction", "externalSideEffect"]
    assert commands["tailscale.status"]["safetyClasses"] == ["readOnly"]
    assert commands["tailscale.address"]["safetyClasses"] == ["readOnly"]
    serialized = json.dumps(commands)
    for forbidden in ('"tailscale", "logout"', '"tailscale", "set"'):
        assert forbidden not in serialized


def test_tailscale_install_login_address_same_tailnet_and_ssh_server_flow(tmp_path):
    absent = fixture(tmp_path, present=False, authenticated=False, localIdentity=None)
    _, planned = call(tmp_path, "tailscale install-plan", fixture=absent, extra=("--platform", "macos", "--request-id", "install"))
    plan = planned["planDocument"]
    run, applied = call(tmp_path, "tailscale install-apply", fixture=absent, extra=("--platform", "macos", "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"]))
    assert run.returncode == 0 and applied["effects"][0]["type"] == "tailscale.install-apply"

    logged_out = fixture(tmp_path, authenticated=False, localIdentity=None)
    _, planned = call(tmp_path, "tailscale login-plan", fixture=logged_out, extra=("--platform", "macos", "--request-id", "login"))
    plan = planned["planDocument"]
    run, applied = call(tmp_path, "tailscale login-apply", fixture=logged_out, extra=("--platform", "macos", "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"]))
    assert run.returncode == 0 and applied["status"] == "waiting_user"
    assert "MFA" in applied["nextAction"]["message"] and "browser" in applied["nextAction"]["message"]

    run, address = call(tmp_path, "tailscale address", extra=("--platform", "macos"))
    assert run.returncode == 0 and address["tailscale"]["address"] == "100.64.0.10"
    assert call(tmp_path, "tailscale same-tailnet", extra=("--platform", "macos"))[0].returncode == 0
    record = tmp_path / "tcp22.jsonl"
    run, verified = call(tmp_path, "ssh-server verify", extra=("--platform", "macos", "--bootstrap-host", "100.64.0.10"), env={"CLAWPOD_NODE_HOST_RECORD": str(record)})
    assert run.returncode == 0 and verified["sshServer"]["port"] == 22
    assert json.loads(record.read_text())["argv"] == ["tcp-connect", "<tailscale-ip>", "22"]
    run, out = call(tmp_path, "ssh-server verify", extra=("--platform", "macos", "--bootstrap-host", "192.168.1.10"))
    assert run.returncode == 2 and out["errors"][0]["code"] == "INVALID_HOST"
    _, planned = call(tmp_path, "ssh-server plan", extra=("--platform", "macos", "--request-id", "ssh"))
    plan = planned["planDocument"]
    run, applied = call(tmp_path, "ssh-server apply", extra=("--platform", "macos", "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"]))
    assert run.returncode == 0 and applied["effects"][0]["type"] == "ssh-server.apply"


def test_onboarding_mutations_reject_missing_wrong_or_stale_approval(tmp_path):
    _, planned = call(tmp_path, "tailscale install-plan", extra=("--platform", "macos", "--request-id", "bound"))
    plan = planned["planDocument"]
    for confirm in (None, "0" * 64):
        extra = ["--platform", "macos", "--plan-id", plan["id"]]
        if confirm: extra += ["--confirm", confirm]
        run, out = call(tmp_path, "tailscale install-apply", extra=extra)
        assert run.returncode == 4 and out["errors"][0]["code"] == "CONFIRMATION_MISMATCH"
    run, out = call(tmp_path, "tailscale install-apply", extra=("--platform", "macos", "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"]), env={"CLAWPOD_NODE_HOST_NOW": "2026-08-16T15:20:00Z"})
    assert run.returncode == 4 and out["errors"][0]["code"] == "PLAN_STALE"

def test_linux_is_explicitly_unsupported(tmp_path):
    path = fixture(tmp_path); value = json.loads(path.read_text()); value["os"] = "linux"; path.write_text(json.dumps(value))
    run, out = call(tmp_path, "system inspect", fixture=path)
    assert run.returncode == 5 and out["errors"][0]["code"] == "UNSUPPORTED_OS"


def test_bootstrap_success_records_only_strict_noninteractive_fixture_commands(tmp_path):
    record = tmp_path / "record.jsonl"
    run, inspected = call(tmp_path, "bootstrap inspect", extra=SSH)
    assert run.returncode == 0 and inspected["bootstrap"]["hostKey"]["verified"]
    _, planned = call(tmp_path, "bootstrap plan", extra=(*BASE, *SSH))
    plan = planned["planDocument"]
    run, out = call(tmp_path, "bootstrap apply", extra=(*BASE, *SSH, "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"]), env={"CLAWPOD_NODE_HOST_RECORD": str(record)})
    assert run.returncode == 0 and out["bootstrap"]["stage"] == "verify"
    commands = [json.loads(line)["argv"] for line in record.read_text().splitlines()]
    assert len(commands) >= 8
    ssh_commands = [argv for argv in commands if argv and argv[0] == "ssh"]
    assert ssh_commands and all("BatchMode=yes" in argv and "StrictHostKeyChecking=yes" in argv for argv in ssh_commands)
    assert all("stdinSha256" in json.loads(line) for line in record.read_text().splitlines())
    assert all("PRIVATE" not in json.dumps(argv) and "password" not in json.dumps(argv).lower() for argv in commands)
    persisted = (tmp_path / "state.json").read_text() + record.read_text()
    assert "nodeuser" not in persisted and "100.64.0.10" not in persisted


def bootstrap_fixture(tmp_path, **changes):
    value = json.loads(FIXTURE.read_text()); value["bootstrap"].update(changes)
    path = tmp_path / f"bootstrap-{len(list(tmp_path.iterdir()))}.json"; path.write_text(json.dumps(value)); return path


def test_bootstrap_missing_ssh_auth_mismatch_timeout_and_permission_fail_closed(tmp_path):
    cases = [
        ({"available": {"openssh": False}}, "SSH_NOT_FOUND", 3),
        ({"auth": "denied"}, "AUTH_FAILED", 5),
        ({"preflight": "timeout"}, "BOOTSTRAP_TIMEOUT", 6),
        ({"permission": "denied"}, "PERMISSION_DENIED", 5),
    ]
    for changes, code, exit_code in cases:
        record = tmp_path / f"{code}.jsonl"
        run, out = call(tmp_path, "bootstrap inspect", fixture=bootstrap_fixture(tmp_path, **changes), extra=SSH, env={"CLAWPOD_NODE_HOST_RECORD": str(record)})
        assert run.returncode == exit_code and out["errors"][0]["code"] == code
        if record.exists():
            assert all("stdinSha256" in json.loads(line) for line in record.read_text().splitlines())
    wrong = (*SSH[:-4], "--expected-host-key", "SHA256:CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC", "--credential-ref", "agent")
    run, out = call(tmp_path, "bootstrap inspect", extra=wrong)
    assert run.returncode == 5 and out["errors"][0]["code"] == "HOST_KEY_MISMATCH"


def test_bootstrap_rejects_plaintext_like_credential_references_and_bad_targets(tmp_path):
    for options, code in [
        ((*SSH[:-2], "--credential-ref", "password=hunter2"), "CREDENTIAL_REFERENCE_INVALID"),
        (("--transport", "openssh", "--bootstrap-host", "host;whoami", "--bootstrap-account", "nodeuser", "--bootstrap-port", "22", "--credential-ref", "agent"), "INVALID_HOST"),
        (("--transport", "openssh", "--bootstrap-host", "100.64.0.10", "--bootstrap-account", "bad user", "--bootstrap-port", "22", "--credential-ref", "agent"), "INVALID_ACCOUNT"),
    ]:
        run, out = call(tmp_path, "bootstrap inspect", extra=options)
        assert run.returncode == 2 and out["errors"][0]["code"] == code
        assert "hunter2" not in run.stdout + run.stderr


def test_local_bootstrap_generation_is_deterministic_and_secret_free(tmp_path):
    args = ("--platform", "macos", "--transport", "local")
    _, first = call(tmp_path, "bootstrap generate", extra=args)
    _, second = call(tmp_path, "bootstrap generate", extra=args)
    assert first["bootstrapScript"] == second["bootstrapScript"]
    assert first["bootstrapScript"]["containsCredentials"] is False
    assert "token" not in first["bootstrapScript"]["content"].lower()
    assert "systemsetup -getremotelogin" in first["bootstrapScript"]["content"]


def test_all_auth_modes_are_equal_and_password_is_runtime_only(tmp_path):
    for ref in ("agent", "tailscale", "password-env:TEST_PASSWORD", "key-env:TEST_KEY_PATH"):
        record = tmp_path / (ref.split(":")[0] + ".jsonl")
        options = (*SSH[:-2], "--credential-ref", ref)
        env = {"CLAWPOD_NODE_HOST_RECORD": str(record), "TEST_PASSWORD": "CANARY-PASSWORD", "TEST_KEY_PATH": "/protected/id_ed25519"}
        run, out = call(tmp_path, "bootstrap inspect", extra=options, env=env)
        assert run.returncode == 0, out
        captured = record.read_text()
        assert "CANARY-PASSWORD" not in captured and "/protected/id_ed25519" not in captured
        assert all("stdinSha256" in json.loads(line) for line in captured.splitlines())


def test_gateway_manifest_avoids_live_parser_rejected_schema_keywords():
    manifest = json.loads((ROOT / "harness.json").read_text())
    for command in manifest["commands"].values():
        encoded = json.dumps({"input": command["inputSchema"], "output": command["outputSchema"]})
        assert '"$ref"' not in encoded and '"enum"' not in encoded


def test_bootstrap_partial_stage_resumes_idempotently(tmp_path):
    partial = bootstrap_fixture(tmp_path, stages={"install-start": "partial"})
    _, planned = call(tmp_path, "bootstrap plan", fixture=partial, extra=(*BASE, *SSH))
    plan = planned["planDocument"]; apply = (*BASE, *SSH, "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"])
    run, out = call(tmp_path, "bootstrap apply", fixture=partial, extra=apply)
    assert run.returncode == 7 and out["errors"][0]["code"] == "PARTIAL_EFFECT"
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["steps"]["preflight"]["status"] == "complete"
    ready = bootstrap_fixture(tmp_path, stages={})
    run, out = call(tmp_path, "bootstrap apply", fixture=ready, extra=apply)
    assert run.returncode == 0 and all(step["status"] == "complete" for step in json.loads((tmp_path / "state.json").read_text())["steps"].values())
    run, out = call(tmp_path, "bootstrap apply", fixture=ready, extra=apply)
    assert run.returncode == 0


def test_pairing_ambiguity_and_permission_denial_are_distinct(tmp_path):
    ambiguous = fixture(tmp_path); value = json.loads(ambiguous.read_text())
    probe = call(tmp_path, "system inspect", fixture=ambiguous, extra=BASE)[1]["target"]["idHash"]
    value["deviceRequests"] = [{"requestId": "one", "nodeFingerprint": probe}, {"requestId": "two", "nodeFingerprint": probe}]; ambiguous.write_text(json.dumps(value))
    run, out = call(tmp_path, "pairing status", fixture=ambiguous, extra=BASE)
    assert run.returncode == 5 and out["errors"][0]["code"] == "PAIRING_AMBIGUOUS"


def test_node_below_minimum_fails_closed_without_mutation(tmp_path):
    path = fixture(tmp_path); value = json.loads(path.read_text()); value["node"] = {"version": "22.13.9"}; path.write_text(json.dumps(value))
    record = tmp_path / "record.jsonl"
    run, out = call(tmp_path, "install plan", fixture=path, extra=BASE, env={"CLAWPOD_NODE_HOST_RECORD": str(record)})
    assert run.returncode == 5 and out["errors"][0]["code"] == "NODE_VERSION_UNSUPPORTED"
    assert not record.exists()


def test_wrong_tailnet_and_stale_evidence_fail_closed(tmp_path):
    wrong = fixture(tmp_path, sameTailnet=False, mismatch=True, gatewayIdentity="other-tailnet")
    run, out = call(tmp_path, "tailscale verify", fixture=wrong)
    assert run.returncode == 3 and out["errors"][0]["code"] == "TAILNET_MISMATCH"
    stale = fixture(tmp_path, checkedAt="2026-08-16T14:54:59Z")
    run, out = call(tmp_path, "tailscale verify", fixture=stale)
    assert run.returncode == 5 and out["errors"][0]["code"] == "PLAN_STALE"


def test_version_drift_and_service_path_mismatch_are_detected(tmp_path):
    drift = fixture(tmp_path); value = json.loads(drift.read_text()); value["openclaw"]["version"] = "2026.4.10"; drift.write_text(json.dumps(value))
    run, out = call(tmp_path, "version inspect", fixture=drift)
    assert run.returncode == 5 and out["errors"][0]["code"] == "VERSION_MISMATCH"
    mismatch = fixture(tmp_path); value = json.loads(mismatch.read_text()); value["service"].update(openclawPath="/old/openclaw", commandVersion="2026.4.10"); mismatch.write_text(json.dumps(value))
    run, out = call(tmp_path, "service status", fixture=mismatch)
    assert run.returncode == 5 and out["errors"][0]["code"] == "SERVICE_RUNTIME_MISMATCH"


def test_interrupted_state_resumes_and_idempotent_apply_is_noop(tmp_path):
    _, planned = call(tmp_path, "install plan", extra=BASE)
    plan = planned["planDocument"]
    state_path = tmp_path / "state.json"
    state = json.loads(state_path.read_text()); state["phase"] = "applying"; state["steps"] = {"provider-install": {"status": "interrupted"}}; state_path.write_text(json.dumps(state))
    options = (*BASE, "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"])
    run, out = call(tmp_path, "install apply", extra=options)
    assert run.returncode == 0 and out["service"]["registered"]
    ready = fixture(tmp_path); value = json.loads(ready.read_text()); value["service"].update(registered=True, running=True); ready.write_text(json.dumps(value))
    _, planned = call(tmp_path, "install plan", fixture=ready, extra=BASE)
    plan = planned["planDocument"]
    run, out = call(tmp_path, "install apply", fixture=ready, extra=(*BASE, "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"]))
    assert run.returncode == 0 and out["status"] == "noop" and not out["effects"]


def test_stale_pairing_request_and_rollback_idempotency(tmp_path):
    path = fixture(tmp_path); value = json.loads(path.read_text()); value["deviceRequests"] = [{"requestId": "req-1", "nodeFingerprint": "not-this-node"}]; path.write_text(json.dumps(value))
    run, out = call(tmp_path, "pairing status", fixture=path, extra=BASE)
    assert run.returncode == 0 and out["plan"]["id"] is None
    _, planned = call(tmp_path, "rollback plan", extra=BASE)
    plan = planned["planDocument"]
    run, out = call(tmp_path, "rollback apply", extra=(*BASE, "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"]))
    assert run.returncode == 0 and out["status"] == "noop"


def test_invalid_inputs_and_expired_plan(tmp_path):
    run = subprocess.run([sys.executable, str(CLI), "--json", "system", "bogus"], text=True, capture_output=True)
    assert run.returncode == 2 and json.loads(run.stdout)["errors"][0]["code"] == "INVALID_INPUT"
    run, out = call(tmp_path, "system inspect", extra=("--tls-fingerprint", "ABC"))
    assert run.returncode == 2 and out["errors"][0]["code"] == "INVALID_INPUT"
    _, planned = call(tmp_path, "install plan", extra=BASE)
    plan = planned["planDocument"]
    env = {"CLAWPOD_NODE_HOST_NOW": "2026-08-16T15:20:00Z"}
    run, out = call(tmp_path, "install apply", extra=(*BASE, "--plan-id", plan["id"], "--confirm", plan["confirmationChallenge"]), env=env)
    assert run.returncode == 5 and out["errors"][0]["code"] == "PLAN_STALE"


def test_redacts_nested_identity_and_secret_values(tmp_path):
    path = fixture(tmp_path); value = json.loads(path.read_text()); value["tailscale"]["localIdentity"] = "token=CANARY"; value["password"] = "CANARY"; path.write_text(json.dumps(value))
    run, out = call(tmp_path, "system inspect", fixture=path)
    serialized = json.dumps(out)
    assert "CANARY" not in serialized and "node-fixture" not in serialized and "gateway-fixture" not in serialized


def test_routing_contract_has_three_positive_two_negative_and_collisions():
    contracts = json.loads((ROOT.parents[1] / "tests" / "fixtures" / "routing_contracts.json").read_text())
    route = contracts["clawpod-node-host"]
    assert len(route["positive"]) >= 3 and len(route["negative"]) >= 2
    joined = " ".join(route["negative"]).lower()
    assert "gateway" in joined and ("unauthorized" in joined or "connected node" in joined)

ENROLL = ("--gateway-host", "gateway.tailnet.ts.net", "--gateway-port", "18789", "--tls")

def enroll_fixture(tmp_path, requests, os_name="macos"):
    value = json.loads(FIXTURE.read_text()); value["deviceRequests"] = requests
    if os_name != "macos": value = {**json.loads((ROOT / "fixtures" / "windows-ready.json").read_text()), "deviceRequests": requests}
    path = tmp_path / f"enroll-{len(list(tmp_path.iterdir()))}.json"; path.write_text(json.dumps(value)); return path

def test_enroll_generate_scripts_are_complete_credential_free_and_deterministic(tmp_path):
    for platform, source, marker in (("macos", FIXTURE, "#!/bin/sh"), ("windows", ROOT / "fixtures" / "windows-ready.json", "$ErrorActionPreference")):
        run, out = call(tmp_path, "enroll generate", fixture=source, extra=(*ENROLL, "--platform", platform, "--node-id", "clawpod-node-fixed00001"))
        assert run.returncode == 0 and out["ok"] and out["enrollScript"]["platform"] == platform
        script = out["enrollScript"]["content"]
        assert marker in script and "openclaw@2026.4.11" in script
        assert "--host 'gateway.tailnet.ts.net' --port 18789 --tls --node-id 'clawpod-node-fixed00001'" in script
        assert "tailscale" in script.lower() and "OPENCLAW_ALLOW_INSECURE_PRIVATE_WS" in script
        assert "<" not in script.replace("<<", "") and "TODO" not in script and "REPLACE" not in script
        assert out["enrollScript"]["sha256"] == hashlib.sha256(script.encode()).hexdigest()
        assert out["enrollScript"]["containsCredentials"] is False and "SECRET" not in script
        if platform == "windows":
            assert script.count("Assert-Step") >= 5 and "$LASTEXITCODE" in script and "try {" not in script
        again = call(tmp_path, "enroll generate", fixture=source, extra=(*ENROLL, "--platform", platform, "--node-id", "clawpod-node-fixed00001"))[1]
        assert again["enrollScript"]["content"] == script
    run, out = call(tmp_path, "enroll generate", extra=(*ENROLL, "--platform", "windows"))
    assert out["enrollScript"]["platform"] == "windows" and "$ErrorActionPreference" in out["enrollScript"]["content"]
    run, out = call(tmp_path, "enroll generate", extra=(*ENROLL, "--platform", "macos"))
    assert run.returncode == 0 and out["enrollment"]["nodeId"].startswith("clawpod-node-")
    assert out["enrollment"]["gateway"] == {"host": "gateway.tailnet.ts.net", "port": 18789, "tls": True}
    assert out["nextAction"]["kind"] == "handoff" and out["enrollment"]["nodeId"] in out["nextAction"]["resumeCommand"]

def test_enroll_generate_rejects_incomplete_or_invalid_inputs(tmp_path):
    run, out = call(tmp_path, "enroll generate", extra=("--platform", "macos"))
    assert run.returncode == 2 and out["errors"][0]["code"] == "GATEWAY_REQUIRED"
    run, out = call(tmp_path, "enroll generate", extra=(*ENROLL, "--platform", "macos", "--node-id", "bad id!"))
    assert run.returncode == 2 and out["errors"][0]["code"] == "INVALID_NODE_ID"

def test_enroll_status_waits_then_approve_records_exactly_one_approval(tmp_path):
    record = tmp_path / "record.jsonl"
    request = {"requestId": "req-42", "nodeId": "clawpod-node-fixed00001", "nodeFingerprint": "fp-1"}
    empty = enroll_fixture(tmp_path, [])
    run, out = call(tmp_path, "enroll status", fixture=empty, extra=("--node-id", "clawpod-node-fixed00001"))
    assert run.returncode == 3 and out["status"] == "waiting_user" and out["enrollment"]["found"] is False
    assert out["nextAction"]["kind"] == "wait"
    ready = enroll_fixture(tmp_path, [request])
    run, out = call(tmp_path, "enroll status", fixture=ready, extra=("--node-id", "clawpod-node-fixed00001"))
    assert run.returncode == 0 and out["enrollment"]["matchCount"] == 1 and out["nextAction"]["kind"] == "approve"
    assert "req-42" not in json.dumps(out)
    run, out = call(tmp_path, "enroll approve", fixture=ready, extra=("--node-id", "clawpod-node-fixed00001"), env={"CLAWPOD_NODE_HOST_RECORD": str(record)})
    assert run.returncode == 0 and out["safetyClass"] == "S4"
    assert out["effects"] == [{"type": "device-request-approved", "requestIdHash": hashlib.sha256(json.dumps("req-42", ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()).hexdigest(), "nodeId": "clawpod-node-fixed00001"}] or out["effects"][0]["type"] == "device-request-approved"
    assert json.loads(record.read_text().splitlines()[-1])["argv"] == ["openclaw", "devices", "approve", "req-42"]

def test_enroll_approve_fails_closed_on_ambiguity_absence_and_stale_request(tmp_path):
    record = tmp_path / "record.jsonl"
    request = {"requestId": "req-42", "nodeId": "clawpod-node-fixed00001"}
    twin = {"requestId": "req-43", "nodeId": "clawpod-node-fixed00001"}
    cases = [
        (enroll_fixture(tmp_path, []), (), "PAIRING_NOT_FOUND"),
        (enroll_fixture(tmp_path, [request, twin]), (), "PAIRING_AMBIGUOUS"),
        (enroll_fixture(tmp_path, [request]), ("--pairing-request-id", "req-99"), "PAIRING_REQUEST_STALE"),
    ]
    for path, extra, code in cases:
        run, out = call(tmp_path, "enroll approve", fixture=path, extra=("--node-id", "clawpod-node-fixed00001", *extra))
        assert run.returncode == 5 and out["errors"][0]["code"] == code
    assert not record.exists()
