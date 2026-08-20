#!/usr/bin/env python3
"""Guarded OpenClaw 2026.4.11 node-host lifecycle harness.

Tests and evaluations use a JSON fixture and command recording. Every mutation is
plan-bound; live execution additionally requires the explicit disposable-host gate.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
import os
import platform
import re
import socket
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REQUIRED_VERSION = "2026.4.11"
SCHEMA_VERSION = 1
PLAN_TTL_SECONDS = 900
TAILSCALE_TTL_SECONDS = 300
BOOTSTRAP_TIMEOUT_SECONDS = 20
BOOTSTRAP_TRANSPORTS = {"openssh", "tailscale-ssh", "local"}
MUTATIONS = {
    "install.apply": "S2", "service.start": "S1", "service.stop": "S3",
    "service.restart": "S1", "repair.apply": "S2", "uninstall.apply": "S3",
    "rollback.apply": "S3", "pairing.approve": "S4", "bootstrap.apply": "S2",
    "tailscale.install-apply": "S2", "tailscale.login-apply": "S4",
    "ssh-server.apply": "S2",
}
PLANNERS = {"install.plan", "repair.plan", "uninstall.plan", "rollback.plan"}
ONBOARDING_PLANNERS = {"tailscale.install-plan", "tailscale.login-plan", "ssh-server.plan"}
COMMANDS = {
    "system.inspect", "version.inspect", "tailscale.install-status", "tailscale.status",
    "tailscale.address", "tailscale.same-tailnet", "tailscale.verify", "ssh-server.status", "ssh-server.verify", "service.status",
    "onboarding.status", "pairing.status", "validate.plan", "validate.run",
    "bootstrap.inspect", "bootstrap.plan", "bootstrap.generate", *PLANNERS, *ONBOARDING_PLANNERS, *MUTATIONS,
}
EXIT = {"success": 0, "noop": 0, "invalid": 2, "waiting_user": 3,
        "confirmation_required": 4, "precondition": 5, "failed": 6,
        "partial": 7, "rollback_required": 7, "rollback_failed": 8}
SECRET_PATTERN = re.compile(
    r"(?i)(bearer\s+\S+|(?:token|password|secret|api[_-]?key|auth)[=:]\s*\S+|"
    r"tskey-[A-Za-z0-9_-]+|-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----)",
    re.DOTALL,
)


def now() -> datetime:
    override = os.environ.get("CLAWPOD_NODE_HOST_NOW")
    return datetime.fromisoformat(override.replace("Z", "+00:00")) if override else datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical(value).encode()
    return hashlib.sha256(raw).hexdigest()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): ("[REDACTED]" if re.search(r"(?i)(token|password|secret|auth|private.?key|email|login)", str(k)) else sanitize(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        return SECRET_PATTERN.sub("[REDACTED]", value)
    return value


def default_state_path() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
    else:
        root = Path.home() / "Library" / "Application Support" if sys.platform == "darwin" else Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return root / "clawpod-node-host" / "state.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(sanitize(value), handle, sort_keys=True, separators=(",", ":"))
            handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt": os.chmod(path, 0o600)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


class Harness:
    def __init__(self, args: argparse.Namespace):
        self.a = args
        self.command = f"{args.group}.{args.action}"
        self.state_path = Path(args.state).expanduser() if args.state else default_state_path()
        self.fixture_path = os.environ.get("CLAWPOD_NODE_HOST_FIXTURE")
        self.fixture = load_json(Path(self.fixture_path)) if self.fixture_path else {}
        local_os = "macos" if sys.platform == "darwin" else "windows" if os.name == "nt" else "unsupported"
        self.observed_os = self.fixture.get("os", args.platform_name if args.group == "bootstrap" and args.platform_name else local_os)
        endpoint = {"host": args.gateway_host, "port": args.gateway_port, "tls": args.tls, "tlsFingerprint": args.tls_fingerprint}
        self.target_hash = sha({"os": self.observed_os, "provider": self.provider, "endpoint": endpoint})

    @property
    def provider(self) -> str:
        return "launchd" if self.observed_os == "macos" else "schtasks" if self.observed_os == "windows" else "unsupported"

    def base(self, status: str = "success", ok: bool = True) -> dict[str, Any]:
        ts = self.fixture.get("tailscale", {})
        service = self.fixture.get("service", {})
        pairing = self.fixture.get("pairing", {})
        observed = self.fixture.get("openclaw", {}).get("version")
        return {
            "ok": ok, "command": self.command, "safetyClass": MUTATIONS.get(self.command, "S0"), "status": status,
            "target": {"os": self.observed_os, "idHash": self.target_hash},
            "version": {"required": REQUIRED_VERSION, "observed": observed, "match": observed == REQUIRED_VERSION},
            "tailscale": {"present": bool(ts.get("present")), "authenticated": bool(ts.get("authenticated")),
                          "sameTailnet": bool(ts.get("sameTailnet")), "reachable": bool(ts.get("reachable")),
                          "checkedAt": ts.get("checkedAt")},
            "service": {"provider": self.provider, "registered": bool(service.get("registered")),
                        "running": bool(service.get("running")), "providerOperation": None},
            "pairing": {"known": bool(pairing.get("known")), "paired": bool(pairing.get("paired")), "connected": bool(pairing.get("connected"))},
            "capabilities": {"system": self.fixture.get("capabilities", {}).get("system", "unknown"),
                             "browser": self.fixture.get("capabilities", {}).get("browser", "unknown"),
                             "macApp": self.fixture.get("capabilities", {}).get("macApp", "not_applicable")},
            "bootstrap": {"transport": self.a.transport, "stage": None, "hostKey": {"verified": False}, "credential": {"kind": None}},
            "plan": {"id": None, "expiresAt": None}, "effects": [],
            "nextAction": {"kind": "none", "message": "", "resumeCommand": None},
            "errors": [], "redactions": ["credential", "account-identity", "peer-inventory"],
        }

    def fail(self, code: str, message: str, status: str, exit_kind: str, action: str | None = None) -> tuple[dict[str, Any], int]:
        out = self.base(status, False)
        out["errors"] = [{"code": code, "message": sanitize(message)}]
        if action:
            out["nextAction"] = {"kind": "user", "message": action, "resumeCommand": self.resume_command()}
        return out, EXIT[exit_kind]

    def resume_command(self) -> str:
        return f"clawpod-node-host --json --state <state-path> {self.command.replace('.', ' ')}"

    def validate_inputs(self) -> tuple[dict[str, Any], int] | None:
        if not self.a.json:
            return self.fail("INVALID_INPUT", "--json is required", "failed", "invalid")
        if self.a.target != "local":
            return self.fail("INVALID_INPUT", "--target must be local", "failed", "invalid")
        needs_version = self.command in (set(MUTATIONS) - {"tailscale.install-apply", "tailscale.login-apply", "ssh-server.apply"}) or self.command in PLANNERS
        if needs_version and self.a.openclaw_version != REQUIRED_VERSION:
            return self.fail("VERSION_SPEC_REJECTED", f"only literal {REQUIRED_VERSION} is accepted", "failed", "invalid")
        if self.a.openclaw_version is not None and self.a.openclaw_version != REQUIRED_VERSION:
            return self.fail("VERSION_SPEC_REJECTED", f"only literal {REQUIRED_VERSION} is accepted", "failed", "invalid")
        if self.observed_os not in {"macos", "windows"}:
            return self.fail("UNSUPPORTED_OS", "only macOS and Windows 11 are supported", "failed", "precondition")
        if self.a.tls_fingerprint and not re.fullmatch(r"[a-f0-9]{64}", self.a.tls_fingerprint):
            return self.fail("INVALID_INPUT", "TLS fingerprint must be lowercase SHA-256", "failed", "invalid")
        if self.a.gateway_host and not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", self.a.gateway_host):
            return self.fail("INVALID_INPUT", "Gateway host contains unsupported characters", "failed", "invalid")
        node_version = self.fixture.get("node", {}).get("version")
        if node_version is not None:
            match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(node_version))
            if not match or tuple(map(int, match.groups())) < (22, 14, 0):
                return self.fail("NODE_VERSION_UNSUPPORTED", "Node.js 22.14.0 or newer is required", "failed", "precondition")
        return None

    def onboarding_binding(self, action: str) -> dict[str, Any]:
        ts = self.fixture.get("tailscale", {})
        ssh = self.fixture.get("sshServer", {})
        return {"target": self.target_hash, "action": action, "platform": self.observed_os,
                "tailscalePresent": bool(ts.get("present")), "tailscaleConnected": bool(ts.get("authenticated")),
                "sshInstalled": bool(ssh.get("installed")), "sshEnabled": bool(ssh.get("enabled"))}

    def onboarding_commands(self, action: str) -> list[list[str]]:
        if action == "tailscale.install-apply":
            return [["brew", "install", "--cask", "tailscale"]] if self.observed_os == "macos" else [["winget", "install", "--id", "Tailscale.Tailscale", "--exact", "--silent"]]
        # Use `tailscale login` (never `tailscale up`) and force `--accept-dns=false`
        # so joining the node authenticates without letting MagicDNS overwrite the
        # node's DNS resolver, which can break its networking.
        if action == "tailscale.login-apply": return [["tailscale", "login", "--accept-dns=false"]]
        if action == "ssh-server.apply":
            return [["systemsetup", "-setremotelogin", "on"]] if self.observed_os == "macos" else [["Add-WindowsCapability", "OpenSSH.Server~~~~0.0.1.0"], ["Set-Service", "sshd", "Automatic"], ["Start-Service", "sshd"], ["Set-FirewallScope", "100.64.0.0/10", "fd7a:115c:a1e0::/48"]]
        return []

    def onboarding_plan(self) -> tuple[dict[str, Any], int]:
        action = self.command.replace("-plan", "-apply") if self.command.startswith("tailscale.") else "ssh-server.apply"
        if action == "tailscale.login-apply" and not self.fixture.get("tailscale", {}).get("present"):
            return self.fail("TAILSCALE_NOT_INSTALLED", "Tailscale must be installed before login", "waiting_user", "precondition")
        created = now(); expires = created + timedelta(seconds=PLAN_TTL_SECONDS); request = self.a.request_id or str(uuid.uuid4())
        binding = self.onboarding_binding(action); plan_id = sha(binding)
        challenge = sha({"action": action, "plan": plan_id, "target": self.target_hash, "requestId": request, "expiresAt": iso(expires)})
        plan = {"schemaVersion": 1, "id": plan_id, "action": action, "requestId": request, "createdAt": iso(created), "expiresAt": iso(expires),
                "targetFingerprint": self.target_hash, "desiredStateHash": sha({"action": action}), "preconditionsHash": sha(binding),
                "commands": self.onboarding_commands(action), "confirmationChallenge": challenge}
        state = self.new_state("planned"); state["plan"] = plan; state["onboardingBinding"] = binding; atomic_write(self.state_path, state)
        out = self.base(); out["plan"] = {"id": plan_id, "expiresAt": iso(expires)}; out["planDocument"] = plan
        out["nextAction"] = {"kind": "confirm", "message": "Review and approve this exact onboarding change.", "resumeCommand": None}
        return out, 0

    def onboarding_apply(self) -> tuple[dict[str, Any], int]:
        try: state = load_json(self.state_path)
        except (OSError, ValueError, json.JSONDecodeError): return self.fail("PLAN_REQUIRED", "a fresh onboarding plan is required", "confirmation_required", "confirmation_required")
        plan = state.get("plan", {}); binding = self.onboarding_binding(self.command)
        expected = sha({"action": self.command, "plan": plan.get("id"), "target": self.target_hash, "requestId": plan.get("requestId"), "expiresAt": plan.get("expiresAt")})
        try: expired = datetime.fromisoformat(plan["expiresAt"].replace("Z", "+00:00")) <= now()
        except (KeyError, TypeError, ValueError): expired = True
        if plan.get("action") != self.command or self.a.plan_id != plan.get("id") or self.a.confirm != expected:
            return self.fail("CONFIRMATION_MISMATCH", "approval does not bind the exact onboarding plan", "confirmation_required", "confirmation_required")
        if expired or state.get("onboardingBinding") != binding:
            return self.fail("PLAN_STALE", "onboarding preconditions changed", "confirmation_required", "confirmation_required")
        commands = self.onboarding_commands(self.command)
        for argv in commands: self.record(argv)
        if not self.fixture_path or os.environ.get("CLAWPOD_NODE_HOST_DISPOSABLE_INTEGRATION") != "1":
            out = self.base(); out["effects"] = [{"type": self.command, "observed": True}]
            if self.command == "tailscale.login-apply":
                out["status"] = "waiting_user"; out["nextAction"] = {"kind": "user", "message": "Open the Tailscale login link and complete the browser login, consent, and any MFA — sign in with the same account/tailnet as the Gateway — then rerun tailscale status.", "resumeCommand": "clawpod-node-host --json tailscale status"}
            state["phase"] = "waiting_tailscale" if self.command == "tailscale.login-apply" else "preflight"; state["effects"] = out["effects"]; atomic_write(self.state_path, state)
            return out, 0
        return self.fail("PARTIAL_EFFECT", "live onboarding execution is restricted to the reviewed platform adapter", "rollback_required", "partial")

    def bootstrap_inputs(self) -> tuple[dict[str, Any], int] | None:
        """Validate routing data and opaque runtime references, never credential values."""
        if self.a.platform_name and self.a.platform_name != self.observed_os:
            return self.fail("PLATFORM_MISMATCH", "selected platform differs from the target", "failed", "precondition")
        if self.a.transport not in BOOTSTRAP_TRANSPORTS:
            return self.fail("TRANSPORT_UNAVAILABLE", "select OpenSSH, Tailscale SSH, or local", "waiting_user", "waiting_user")
        if self.a.transport == "local": return None
        try:
            address = ipaddress.ip_address(self.a.bootstrap_host or "")
            if not (address in ipaddress.ip_network("100.64.0.0/10") or address in ipaddress.ip_network("fd7a:115c:a1e0::/48")):
                raise ValueError
        except ValueError:
            return self.fail("INVALID_HOST", "bootstrap host must be a Tailscale IPv4 or IPv6 address", "failed", "invalid")
        if not self.a.bootstrap_account or len(self.a.bootstrap_account) > 64 or not re.fullmatch(r"[A-Za-z0-9_.@-]+", self.a.bootstrap_account):
            return self.fail("INVALID_ACCOUNT", "bootstrap account contains unsupported characters", "failed", "invalid")
        if not self.a.bootstrap_port or not 1 <= self.a.bootstrap_port <= 65535:
            return self.fail("INVALID_PORT", "bootstrap port must be between 1 and 65535", "failed", "invalid")
        if self.a.credential_ref and not re.fullmatch(r"(?:agent|tailscale|(?:password|key|protected)-env:[A-Z][A-Z0-9_]{0,63})", self.a.credential_ref):
            return self.fail("CREDENTIAL_REFERENCE_INVALID", "credential must be agent, tailscale, or a protected runtime environment reference", "failed", "invalid")
        if not self.a.credential_ref:
            return self.fail("CREDENTIAL_REFERENCE_REQUIRED", "select password, key, SSH agent, or Tailscale SSH authentication", "waiting_user", "waiting_user", "Provide the credential through the protected runtime channel and retry.")
        return None

    def credential_kind(self) -> str:
        ref = self.a.credential_ref or ""
        return ref.split("-env:", 1)[0] if "-env:" in ref else ref

    def record_transport(self, argv: list[str], stdin: str = "") -> None:
        redacted = []
        redact_next = False
        for part in argv:
            if redact_next:
                redacted.append("<protected-identity>"); redact_next = False; continue
            redacted.append("<ephemeral-known-hosts>" if "known_hosts" in part else
                            "<account>@<tailscale-ip>" if "@" in part else
                            "<tailscale-ip>" if part == self.a.bootstrap_host else part)
            redact_next = part == "-i"
        path = os.environ.get("CLAWPOD_NODE_HOST_RECORD")
        if path:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(canonical({"argv": redacted, "stdinSha256": sha(stdin.encode()), "stdinBytes": len(stdin.encode())}) + "\n")

    def run_bounded(self, argv: list[str], stdin: str = "", env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        self.record_transport(argv, stdin)
        return subprocess.run(argv, input=stdin, text=True, capture_output=True, timeout=BOOTSTRAP_TIMEOUT_SECONDS,
                              check=False, env=env or os.environ.copy())

    def fixture_failure(self) -> tuple[dict[str, Any], int] | None:
        data = self.fixture.get("bootstrap", {})
        if not data.get("available", {}).get(self.a.transport, True):
            return self.fail("SSH_NOT_FOUND", "selected SSH transport is unavailable", "waiting_user", "waiting_user", "Complete the local OS readiness stage and retry.")
        mapping = {"denied": ("AUTH_FAILED", "protected SSH authentication failed", "precondition"),
                   "timeout": ("BOOTSTRAP_TIMEOUT", "bounded SSH operation timed out", "failed"),
                   "permission": ("PERMISSION_DENIED", "remote permission was denied", "precondition"),
                   "network": ("SSH_UNREACHABLE", "SSH was unreachable over the Tailscale IP", "precondition"),
                   "script": ("REMOTE_SCRIPT_FAILED", "remote readiness script failed", "failed")}
        failure = data.get("failure")
        if data.get("auth") == "denied": failure = "denied"
        if data.get("preflight") == "timeout": failure = "timeout"
        if data.get("permission") == "denied": failure = "permission"
        if failure in mapping:
            code, message, kind = mapping[failure]
            return self.fail(code, message, "waiting_user" if kind == "precondition" else "failed", kind)
        return None

    def acquire_host_key(self) -> tuple[str, str] | tuple[dict[str, Any], int]:
        data = self.fixture.get("bootstrap", {})
        if self.fixture_path:
            key = data.get("hostKey", {})
            line = key.get("line", f"{self.a.bootstrap_host} ssh-ed25519 {base64.b64encode(b'fixture-host-key').decode()}")
            self.record_transport(["ssh-keyscan", "-T", str(BOOTSTRAP_TIMEOUT_SECONDS), "-p", str(self.a.bootstrap_port), self.a.bootstrap_host])
            return line + "\n", key.get("fingerprint", "")
        try:
            scan = self.run_bounded(["ssh-keyscan", "-T", str(BOOTSTRAP_TIMEOUT_SECONDS), "-p", str(self.a.bootstrap_port), self.a.bootstrap_host])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return self.fail("SSH_NOT_FOUND", "host-key acquisition tool was unavailable or timed out", "failed", "precondition")
        lines = [line for line in scan.stdout.splitlines() if line and not line.startswith("#")]
        if scan.returncode or len(lines) != 1:
            return self.fail("HOST_KEY_ACQUISITION_FAILED", "exactly one SSH host key could not be acquired", "failed", "precondition")
        try:
            raw = base64.b64decode(lines[0].split()[2], validate=True)
        except (IndexError, ValueError):
            return self.fail("HOST_KEY_ACQUISITION_FAILED", "acquired SSH host key was malformed", "failed", "precondition")
        fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
        return lines[0] + "\n", fingerprint

    def bootstrap_evidence(self) -> tuple[dict[str, Any], int] | None:
        invalid = self.bootstrap_inputs()
        if invalid or self.a.transport == "local": return invalid
        if not self.a.expected_host_key:
            return self.fail("HOST_KEY_VERIFICATION_REQUIRED", "provide the fingerprint shown locally on the PC", "waiting_user", "waiting_user")
        if not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", self.a.expected_host_key):
            return self.fail("INVALID_HOST_KEY", "host-key fingerprint must use OpenSSH SHA256 form", "failed", "invalid")
        acquired = self.acquire_host_key()
        if isinstance(acquired[0], dict): return acquired  # type: ignore[return-value]
        _line, fingerprint = acquired
        fixture_key = self.fixture.get("bootstrap", {}).get("hostKey", {})
        if fingerprint != self.a.expected_host_key or (self.fixture_path and
                (fixture_key.get("account", self.a.bootstrap_account) != self.a.bootstrap_account or fixture_key.get("host", self.a.bootstrap_host) != self.a.bootstrap_host)):
            return self.fail("HOST_KEY_MISMATCH", "acquired host key does not match the independently verified fingerprint", "failed", "precondition")
        return self.fixture_failure() if self.fixture_path else None

    def readiness_script(self) -> str:
        """Local, human-assisted OS readiness. It intentionally pauses at login/approval gates."""
        if self.observed_os == "macos":
            return """#!/bin/sh
set -eu
umask 077
if [ "${OPENCLAW_BOOTSTRAP_REVOKE:-0}" = 1 ]; then sudo systemsetup -setremotelogin off; exit 0; fi
TS=$(command -v tailscale 2>/dev/null || true)
[ -n "$TS" ] || for c in /Applications/Tailscale.app/Contents/MacOS/Tailscale "$HOME/Applications/Tailscale.app/Contents/MacOS/Tailscale"; do [ -x "$c" ] && TS="$c" && break; done
[ -n "$TS" ] || { echo 'ACTION: install Tailscale for macOS, then rerun'; exit 20; }
"$TS" status >/dev/null 2>&1 || { echo 'ACTION: open Tailscale and complete login, then rerun'; exit 21; }
TS_IP=$("$TS" ip -4 | head -n 1); test -n "$TS_IP"
sudo systemsetup -getremotelogin | grep -qi 'On' || { echo 'ACTION: enable System Settings > General > Sharing > Remote Login, then rerun'; exit 22; }
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
printf 'TAILSCALE_IP=%s\nREADY=remote-login\n' "$TS_IP"
"""
        return r"""$ErrorActionPreference = 'Stop'
if ($env:OPENCLAW_BOOTSTRAP_REVOKE -eq '1') { Disable-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue; Stop-Service sshd -ErrorAction SilentlyContinue; exit 0 }
$ts = Get-Command tailscale.exe -ErrorAction SilentlyContinue
if (-not $ts) { Write-Output 'ACTION: install Tailscale for Windows, then rerun'; exit 20 }
tailscale status | Out-Null
$ip = (tailscale ip -4 | Select-Object -First 1)
$cap = Get-WindowsCapability -Online | Where-Object Name -Like 'OpenSSH.Server*'
if ($cap.State -ne 'Installed') { Add-WindowsCapability -Online -Name $cap.Name | Out-Null }
Set-Service sshd -StartupType Automatic; Start-Service sshd
$rule = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
if (-not $rule) { $rule = New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 }
$rule | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -RemoteAddress 100.64.0.0/10
ssh-keygen -lf "$env:ProgramData\ssh\ssh_host_ed25519_key.pub"
Write-Output "TAILSCALE_IP=$ip"; Write-Output 'READY=openssh'
"""

    def bootstrap_script(self) -> str:
        endpoint = self.a.gateway_host or "gateway.tailnet.ts.net"
        port = self.a.gateway_port or 18789
        if self.observed_os == "macos":
            return f"""#!/bin/sh
set -eu
umask 077
if [ "${{OPENCLAW_NODE_ROLLBACK:-0}}" = 1 ]; then openclaw node stop || true; openclaw node uninstall || true; npm uninstall --global openclaw; exit 0; fi
TS=$(command -v tailscale 2>/dev/null || true); [ -n "$TS" ] || for c in /Applications/Tailscale.app/Contents/MacOS/Tailscale "$HOME/Applications/Tailscale.app/Contents/MacOS/Tailscale"; do [ -x "$c" ] && TS="$c" && break; done; [ -n "$TS" ]; "$TS" status >/dev/null; "$TS" ip -4 | grep -Eq '^100\\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\\.'
sudo systemsetup -getremotelogin | grep -qi 'On'; npm view openclaw@{REQUIRED_VERSION} version | grep -qx '{REQUIRED_VERSION}'
npm install --global openclaw@{REQUIRED_VERSION}
test "$(openclaw --version)" = '{REQUIRED_VERSION}'
export OPENCLAW_ALLOW_INSECURE_PRIVATE_WS=1
openclaw node install --host '{endpoint}' --port {port}{' --tls' if self.a.tls else ''}
openclaw node restart
openclaw node status
"""
        return f"""$ErrorActionPreference = 'Stop'
if ($env:OPENCLAW_NODE_ROLLBACK -eq '1') {{ openclaw node stop; openclaw node uninstall; npm uninstall --global openclaw; exit 0 }}
tailscale status | Out-Null
if (-not (Get-Service sshd -ErrorAction SilentlyContinue)) {{ throw 'sshd unavailable' }}
if ((npm view openclaw@{REQUIRED_VERSION} version).Trim() -ne '{REQUIRED_VERSION}') {{ throw 'version resolution mismatch' }}
npm install --global openclaw@{REQUIRED_VERSION}
if ((openclaw --version).Trim() -ne '{REQUIRED_VERSION}') {{ throw 'installed version mismatch' }}
$env:OPENCLAW_ALLOW_INSECURE_PRIVATE_WS = '1'
openclaw node install --host '{endpoint}' --port {port}{' --tls' if self.a.tls else ''}
openclaw node restart
openclaw node status
"""

    def bootstrap_readonly(self) -> tuple[dict[str, Any], int]:
        gate = self.bootstrap_evidence()
        if gate: return gate
        out = self.base()
        data = self.fixture.get("bootstrap", {})
        out["bootstrap"] = {"transport": self.a.transport, "stage": "preflight", "hostKey": {"verified": self.a.transport != "local"},
                            "credential": {"kind": "tailscale" if self.a.transport == "tailscale-ssh" else "agent" if self.a.credential_ref == "agent" else "protected-reference" if self.a.credential_ref else "none"},
                            "preflight": {"noninteractive": True, "timeoutSeconds": BOOTSTRAP_TIMEOUT_SECONDS, "result": data.get("preflight", "ready")}}
        if self.command == "bootstrap.generate":
            script = self.readiness_script(); out["bootstrapScript"] = {"sha256": sha(script.encode()), "content": script, "containsCredentials": False}
        elif self.a.transport != "local":
            result = self.ssh_script("printf OPENCLAW_SSH_READY", fixture_stage="preflight")
            if isinstance(result, tuple): return result
        return out, 0

    def ssh_script(self, script: str, fixture_stage: str) -> subprocess.CompletedProcess[str] | tuple[dict[str, Any], int]:
        acquired = self.acquire_host_key()
        if isinstance(acquired[0], dict): return acquired  # type: ignore[return-value]
        known_line, fingerprint = acquired
        if fingerprint != self.a.expected_host_key:
            return self.fail("HOST_KEY_MISMATCH", "SSH host key changed before execution", "failed", "precondition")
        fd, known_path = tempfile.mkstemp(prefix="openclaw-known_hosts-")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle: handle.write(known_line)
            target = f"{self.a.bootstrap_account}@{self.a.bootstrap_host}"
            options = ["-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={known_path}", "-o", "GlobalKnownHostsFile=/dev/null",
                       "-o", "ConnectTimeout=10", "-o", "ConnectionAttempts=1", "-p", str(self.a.bootstrap_port)]
            kind = self.credential_kind(); env = os.environ.copy()
            if self.a.transport == "tailscale-ssh" or kind == "tailscale":
                argv = ["tailscale", "ssh", target]
            else:
                options += ["-o", "BatchMode=no" if kind in {"password", "protected"} else "BatchMode=yes"]
                argv = ["ssh", *options]
                if kind == "key":
                    name = self.a.credential_ref.split(":", 1)[1]
                    identity = env.get(name)
                    if not identity: return self.fail("CREDENTIAL_UNAVAILABLE", "protected key reference is unavailable", "waiting_user", "precondition")
                    argv += ["-i", identity, "-o", "IdentitiesOnly=yes"]
                argv += [target]
                if kind in {"password", "protected"}:
                    name = self.a.credential_ref.split(":", 1)[1]
                    password = env.pop(name, None)
                    if password is None: return self.fail("CREDENTIAL_UNAVAILABLE", "protected password is unavailable", "waiting_user", "precondition")
                    env["SSHPASS"] = password; argv = ["sshpass", "-e", *argv]
            argv += ["sh", "-s"] if self.observed_os == "macos" else ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "-"]
            if self.fixture_path:
                self.record_transport(argv, script)
                failure = self.fixture.get("bootstrap", {}).get("stages", {}).get(fixture_stage)
                if failure in {"failed", "partial"}:
                    return self.fail("PARTIAL_EFFECT", f"remote stage {fixture_stage} had a partial effect", "rollback_required", "partial")
                return subprocess.CompletedProcess(argv, 0, "OPENCLAW_SSH_READY", "")
            try:
                completed = self.run_bounded(argv, script, env)
            except FileNotFoundError:
                return self.fail("SSH_NOT_FOUND", "required SSH or protected password helper was not found", "failed", "precondition")
            except subprocess.TimeoutExpired:
                return self.fail("BOOTSTRAP_TIMEOUT", "bounded SSH operation timed out", "failed", "failed")
            finally:
                env.pop("SSHPASS", None)
            if completed.returncode:
                stderr = completed.stderr.lower()
                if "permission denied" in stderr: code = "AUTH_FAILED"
                elif "host key" in stderr: code = "HOST_KEY_MISMATCH"
                elif "timed out" in stderr or "no route" in stderr or "refused" in stderr: code = "SSH_UNREACHABLE"
                else: code = "REMOTE_SCRIPT_FAILED"
                return self.fail(code, "noninteractive SSH stage failed", "failed", "precondition" if code != "REMOTE_SCRIPT_FAILED" else "failed")
            return completed
        finally:
            try: os.unlink(known_path)
            except FileNotFoundError: pass

    def bootstrap_plan(self) -> tuple[dict[str, Any], int]:
        gate = self.bootstrap_evidence()
        if gate: return gate
        created = now(); expires = created + timedelta(seconds=PLAN_TTL_SECONDS)
        script_hash = sha(self.bootstrap_script().encode())
        binding = {"target": self.target_hash, "transport": self.a.transport, "hostHash": sha(self.a.bootstrap_host),
                   "accountHash": sha(self.a.bootstrap_account), "port": self.a.bootstrap_port, "hostKey": self.a.expected_host_key,
                   "scriptHash": script_hash, "platform": self.observed_os}
        plan_id = sha(binding); request = self.a.request_id or str(uuid.uuid4())
        challenge = sha({"action": "bootstrap.apply", "plan": plan_id, "target": self.target_hash, "requestId": request, "expiresAt": iso(expires)})
        plan = {"schemaVersion": 1, "id": plan_id, "action": "bootstrap.apply", "requestId": request, "createdAt": iso(created), "expiresAt": iso(expires),
                "targetFingerprint": self.target_hash, "desiredStateHash": script_hash, "preconditionsHash": sha(binding),
                "commands": [["ssh", "<strict-host-key-and-noninteractive-options>", "<user-bound-target>", "<deterministic-script>"]] if self.a.transport != "local" else [["user-run-local", "<deterministic-script>"]],
                "confirmationChallenge": challenge}
        state = self.new_state("planned"); state["plan"] = plan; state["bootstrap"] = {"binding": binding, "stage": "planned", "scriptHash": script_hash}; atomic_write(self.state_path, state)
        out = self.base(); out["plan"] = {"id": plan_id, "expiresAt": iso(expires)}; out["planDocument"] = plan
        out["nextAction"] = {"kind": "confirm", "message": "Approve this exact target-bound bootstrap plan.", "resumeCommand": None}
        return out, 0

    def bootstrap_apply(self) -> tuple[dict[str, Any], int]:
        gate = self.bootstrap_evidence()
        if gate: return gate
        try: state = load_json(self.state_path)
        except (OSError, ValueError, json.JSONDecodeError): return self.fail("PLAN_REQUIRED", "a fresh bootstrap plan is required", "confirmation_required", "confirmation_required")
        plan = state.get("plan", {})
        expected = sha({"action": "bootstrap.apply", "plan": plan.get("id"), "target": self.target_hash, "requestId": plan.get("requestId"), "expiresAt": plan.get("expiresAt")})
        if plan.get("action") != "bootstrap.apply" or self.a.plan_id != plan.get("id") or self.a.confirm != expected:
            return self.fail("CONFIRMATION_MISMATCH", "approval does not bind the exact bootstrap plan", "confirmation_required", "confirmation_required")
        try: expired = datetime.fromisoformat(plan["expiresAt"].replace("Z", "+00:00")) <= now()
        except (KeyError, TypeError, ValueError): expired = True
        binding = state.get("bootstrap", {}).get("binding", {})
        current = {"target": self.target_hash, "transport": self.a.transport, "hostHash": sha(self.a.bootstrap_host), "accountHash": sha(self.a.bootstrap_account),
                   "port": self.a.bootstrap_port, "hostKey": self.a.expected_host_key, "scriptHash": sha(self.bootstrap_script().encode()), "platform": self.observed_os}
        if expired or binding != current: return self.fail("PLAN_STALE", "bootstrap target or evidence changed", "confirmation_required", "confirmation_required")
        stages = state.setdefault("steps", {})
        ordered = ["preflight", "install-start", "pairing-ready", "verify"]
        fixture_stages = self.fixture.get("bootstrap", {}).get("stages", {})
        for stage in ordered:
            if stages.get(stage, {}).get("status") == "complete": continue
            if self.a.transport != "local":
                scripts = {"preflight": "command -v tailscale >/dev/null 2>&1 || Get-Command tailscale.exe | Out-Null",
                           "install-start": self.bootstrap_script(),
                           "pairing-ready": "openclaw node status",
                           "verify": "openclaw --version && openclaw node status"}
                result = self.ssh_script(scripts[stage], fixture_stage=stage)
                if isinstance(result, tuple):
                    stages[stage] = {"status": fixture_stages.get(stage, "failed")}; state["phase"] = "rollback_required"; state["lastError"] = {"code": result[0]["errors"][0]["code"], "stage": stage}; atomic_write(self.state_path, state)
                    result[0]["nextAction"] = {"kind": "user", "message": "Retry this idempotent stage, or run rollback and revoke SSH access.", "resumeCommand": self.resume_command()}
                    return result
            stages[stage] = {"status": "complete"}; state["bootstrap"]["stage"] = stage; atomic_write(self.state_path, state)
        state["phase"] = "preflight"; state["lastError"] = None; atomic_write(self.state_path, state)
        out = self.base(); out["effects"] = [{"type": "bootstrap-complete", "observed": True}]; out["bootstrap"] = {"transport": self.a.transport, "stage": "verify", "hostKey": {"verified": self.a.transport != "local"}, "credential": {"kind": "protected-reference"}}
        return out, 0

    def tailscale_gate(self, reachability: bool = True) -> tuple[dict[str, Any], int] | None:
        ts = self.fixture.get("tailscale", {})
        if not ts.get("present"):
            return self.fail("TAILSCALE_NOT_INSTALLED", "Tailscale CLI was not found", "waiting_user", "waiting_user", "Install Tailscale on this node, sign in to the same account/tailnet as the Gateway, then rerun this command.")
        if not ts.get("authenticated") or not ts.get("localIdentity"):
            return self.fail("TAILSCALE_NOT_AUTHENTICATED", "authenticated local Tailscale identity was not proven", "waiting_user", "waiting_user", "Sign in to Tailscale on this node using the same account/tailnet as the Gateway, then rerun this command.")
        if not ts.get("sameTailnet") or not ts.get("gatewayIdentity"):
            code = "TAILNET_MISMATCH" if ts.get("mismatch") else "TAILNET_UNPROVEN"
            return self.fail(code, "Gateway same-tailnet membership was not proven", "waiting_user", "waiting_user", "Move or sign this node into the Gateway’s tailnet, then rerun this command.")
        try:
            checked = datetime.fromisoformat(str(ts.get("checkedAt", "")).replace("Z", "+00:00"))
            stale = (now() - checked).total_seconds() > TAILSCALE_TTL_SECONDS or (now() - checked).total_seconds() < -1
        except ValueError:
            stale = True
        if stale:
            return self.fail("PLAN_STALE", "Tailscale verification evidence is older than five minutes", "failed", "precondition")
        if reachability and not ts.get("reachable"):
            endpoint = f"{self.a.gateway_host}:{self.a.gateway_port}" if self.a.gateway_host else "configured Gateway endpoint"
            return self.fail("GATEWAY_UNREACHABLE", f"Tailscale peer reachability failed for {endpoint}", "waiting_user", "precondition", f"Restore Tailscale reachability to {endpoint}, then rerun this command.")
        return None

    def desired(self) -> dict[str, Any]:
        return {"version": REQUIRED_VERSION, "provider": self.provider, "runtime": "node", "host": self.a.gateway_host,
                "port": self.a.gateway_port, "tls": self.a.tls, "tlsFingerprint": self.a.tls_fingerprint,
                "displayName": self.a.display_name, "nodeId": self.a.node_id,
                "browserProxy": {"mode": self.a.browser_proxy, "allowProfiles": self.a.allow_profile or []}}

    def make_plan(self) -> tuple[dict[str, Any], int]:
        gate = self.tailscale_gate()
        if gate: return gate
        if not self.a.gateway_host or not self.a.gateway_port:
            return self.fail("INVALID_INPUT", "Gateway host and port are required", "failed", "invalid")
        observed = self.fixture.get("openclaw", {}).get("version")
        resolved = self.fixture.get("npm", {}).get("resolvedVersion")
        if self.command in {"install.plan", "repair.plan"} and resolved != REQUIRED_VERSION:
            return self.fail("VERSION_MISMATCH", "literal npm spec did not independently resolve to the required version", "failed", "precondition")
        desired = self.desired()
        created = now(); expires = created + timedelta(seconds=PLAN_TTL_SECONDS)
        safety = {"target": self.target_hash, "desired": desired, "identity": self.fixture.get("tailscale", {}).get("localIdentity"),
                  "provider": self.provider, "observedVersion": observed, "tailscaleCheckedAt": self.fixture.get("tailscale", {}).get("checkedAt")}
        plan_id = sha(safety)
        action = self.command.split(".")[0] + ".apply"
        request = self.a.request_id or str(uuid.uuid4())
        confirmation = sha({"action": action, "plan": plan_id, "target": self.target_hash, "requestId": request, "expiresAt": iso(expires)})
        plan = {"schemaVersion": 1, "id": plan_id, "action": action, "requestId": request, "createdAt": iso(created), "expiresAt": iso(expires),
                "targetFingerprint": self.target_hash, "desiredStateHash": sha(desired), "preconditionsHash": sha(safety),
                "commands": self.conceptual_commands(action), "confirmationChallenge": confirmation}
        state = self.new_state("planned"); state["plan"] = plan; atomic_write(self.state_path, state)
        out = self.base("success"); out["plan"] = {"id": plan_id, "expiresAt": iso(expires)}
        out["nextAction"] = {"kind": "confirm", "message": "Review the redacted plan and confirm the exact action.", "resumeCommand": None}
        out["planDocument"] = plan
        return out, 0

    def conceptual_commands(self, action: str) -> list[list[str]]:
        if action == "install.apply": return [["npm", "install", "--global", f"openclaw@{REQUIRED_VERSION}"], ["openclaw", "node", "install", "<redacted-endpoint-options>"]]
        if action == "repair.apply": return [["openclaw", "node", "install", "<redacted-endpoint-options>"]]
        if action in {"uninstall.apply", "rollback.apply"}: return [["openclaw", "node", "stop"], ["openclaw", "node", "uninstall"]]
        return []

    def new_state(self, phase: str) -> dict[str, Any]:
        return {"schemaVersion": 1, "flowId": str(uuid.uuid4()), "targetFingerprint": self.target_hash,
                "desiredStateHash": sha(self.desired()), "phase": phase, "steps": {}, "plan": {"id": None, "expiresAt": None},
                "pairing": {"requestIdHash": None, "approved": False}, "effects": [], "lastError": None, "updatedAt": iso(now())}

    def apply(self) -> tuple[dict[str, Any], int]:
        reachability = self.command != "service.stop"
        gate = self.tailscale_gate(reachability=reachability)
        if gate: return gate
        try: state = load_json(self.state_path)
        except (OSError, ValueError, json.JSONDecodeError):
            return self.fail("PLAN_REQUIRED", "a fresh compatible plan is required", "confirmation_required", "confirmation_required")
        plan = state.get("plan", {})
        if not self.a.plan_id or plan.get("id") != self.a.plan_id or plan.get("action") != self.command:
            return self.fail("PLAN_REQUIRED", "plan is missing or bound to another action", "confirmation_required", "confirmation_required")
        try: expired = datetime.fromisoformat(plan["expiresAt"].replace("Z", "+00:00")) <= now()
        except (KeyError, TypeError, ValueError): expired = True
        if expired or state.get("targetFingerprint") != self.target_hash or state.get("desiredStateHash") != sha(self.desired()):
            return self.fail("PLAN_STALE", "plan inputs or observation window changed", "confirmation_required", "confirmation_required")
        expected = sha({"action": self.command, "plan": plan["id"], "target": self.target_hash,
                        "requestId": plan["requestId"], "expiresAt": plan["expiresAt"]})
        if not self.a.confirm:
            return self.fail("CONFIRMATION_REQUIRED", "exact plan-bound confirmation is required", "confirmation_required", "confirmation_required")
        if self.a.confirm != expected or (self.a.request_id and self.a.request_id != plan["requestId"]):
            return self.fail("CONFIRMATION_MISMATCH", "confirmation does not bind this action, target, plan, and request", "confirmation_required", "confirmation_required")
        if not self.fixture_path or os.environ.get("CLAWPOD_NODE_HOST_DISPOSABLE_INTEGRATION") != "1":
            return self.simulate(state, plan)
        return self.live_mutation(state, plan)

    def record(self, argv: list[str]) -> None:
        path = os.environ.get("CLAWPOD_NODE_HOST_RECORD")
        if path:
            with open(path, "a", encoding="utf-8") as handle: handle.write(canonical({"argv": argv}) + "\n")

    def simulate(self, state: dict[str, Any], plan: dict[str, Any]) -> tuple[dict[str, Any], int]:
        service = self.fixture.setdefault("service", {})
        effect = None
        if self.command in {"install.apply", "repair.apply"}:
            if service.get("registered") and service.get("running") and self.fixture.get("openclaw", {}).get("version") == REQUIRED_VERSION:
                status = "noop"
            else:
                self.record(["openclaw", "node", "install"]); service.update(registered=True, running=True); effect = "service-installed"; status = "success"
        elif self.command in {"service.start", "service.restart"}:
            if self.command == "service.start": operation = "restart"  # 2026.4.11 has no node start
            else: operation = "restart"
            self.record(["openclaw", "node", operation]); status = "noop" if service.get("running") else "success"; service["running"] = True; effect = None if status == "noop" else "service-started"
        elif self.command == "service.stop":
            self.record(["openclaw", "node", "stop"]); status = "success" if service.get("running") else "noop"; service["running"] = False; effect = None if status == "noop" else "service-stopped"
        elif self.command in {"uninstall.apply", "rollback.apply"}:
            if not service.get("registered"): status = "noop"
            else:
                self.record(["openclaw", "node", "stop"]); self.record(["openclaw", "node", "uninstall"])
                service.update(registered=False, running=False); status = "success"; effect = "service-uninstalled"
        else: return self.pairing_apply(state, plan)
        out = self.base(status); out["service"].update(registered=bool(service.get("registered")), running=bool(service.get("running")))
        if self.command == "service.start": out["service"]["providerOperation"] = "restart"
        if effect: out["effects"] = [{"type": effect, "observed": True}]
        state["effects"] = state.get("effects", []) + out["effects"]; state["phase"] = "installed" if service.get("registered") else "preflight"; state["updatedAt"] = iso(now()); atomic_write(self.state_path, state)
        return out, 0

    def pairing_apply(self, state: dict[str, Any], plan: dict[str, Any]) -> tuple[dict[str, Any], int]:
        requests = self.fixture.get("deviceRequests", [])
        matches = [r for r in requests if r.get("nodeFingerprint") == self.target_hash]
        if len(matches) != 1: return self.fail("PAIRING_AMBIGUOUS", "exactly one current matching device request is required", "failed", "precondition")
        request_id = matches[0].get("requestId")
        if not request_id or (self.a.pairing_request_id and self.a.pairing_request_id != request_id):
            return self.fail("PAIRING_REQUEST_STALE", "pairing request is stale or changed", "failed", "precondition")
        self.record(["openclaw", "devices", "approve", request_id])
        state["pairing"] = {"requestIdHash": sha(request_id), "approved": True}; state["phase"] = "paired"; atomic_write(self.state_path, state)
        out = self.base(); out["effects"] = [{"type": "device-request-approved", "requestIdHash": sha(request_id)}]
        return out, 0

    def live_mutation(self, state: dict[str, Any], plan: dict[str, Any]) -> tuple[dict[str, Any], int]:
        # Deliberately narrow: provider CLI remains the sole service implementation.
        argv = self.conceptual_commands(self.command)[-1] if self.command in {"install.apply", "repair.apply", "uninstall.apply", "rollback.apply"} else ["openclaw", "node", "restart" if self.command in {"service.start", "service.restart"} else "stop"]
        if any("<" in part for part in argv): return self.fail("SERVICE_MUTATION_FAILED", "live endpoint option construction is unavailable pending pinned provider fixture review", "failed", "failed")
        self.record(argv)
        timeout = float(os.environ.get("CLAWPOD_NODE_HOST_COMMAND_TIMEOUT", "60"))
        attempts = max(1, min(int(os.environ.get("CLAWPOD_NODE_HOST_RETRY_ATTEMPTS", "2")), 3))
        completed = None
        for attempt in range(attempts):
            try:
                completed = subprocess.run(argv, text=True, capture_output=True, timeout=timeout, check=False)
            except subprocess.TimeoutExpired:
                if attempt + 1 == attempts:
                    return self.fail("SERVICE_MUTATION_TIMEOUT", f"provider command timed out after {attempts} attempts", "failed", "failed")
                continue
            if completed.returncode == 0:
                return self.simulate(state, plan)
        return self.fail("SERVICE_MUTATION_FAILED", sanitize(completed.stderr if completed else "provider command failed"), "failed", "failed")

    def readonly(self) -> tuple[dict[str, Any], int]:
        out = self.base()
        ts = self.fixture.get("tailscale", {})
        if self.command == "tailscale.install-status":
            out["tailscale"]["installReady"] = bool(ts.get("present")); return out, 0
        if self.command == "tailscale.status":
            if not ts.get("present"): return self.fail("TAILSCALE_NOT_INSTALLED", "Tailscale CLI was not found", "waiting_user", "precondition")
            out["tailscale"]["loginState"] = "authenticated" if ts.get("authenticated") else "login_required"; return out, 0
        if self.command == "tailscale.address":
            address = ts.get("address")
            if not ts.get("authenticated"): return self.fail("TAILSCALE_NOT_AUTHENTICATED", "Tailscale login is required before address discovery", "waiting_user", "precondition")
            if not address:
                address = self.fixture.get("bootstrap", {}).get("hostKey", {}).get("host")
            try:
                parsed = ipaddress.ip_address(address or "")
                if not (parsed in ipaddress.ip_network("100.64.0.0/10") or parsed in ipaddress.ip_network("fd7a:115c:a1e0::/48")): raise ValueError
            except ValueError: return self.fail("INVALID_HOST", "no valid Tailscale address was observed", "failed", "precondition")
            out["tailscale"]["address"] = address; return out, 0
        if self.command == "tailscale.same-tailnet":
            gate = self.tailscale_gate(reachability=False); return gate or (out, 0)
        if self.command == "ssh-server.status":
            ssh = self.fixture.get("sshServer", {})
            out["sshServer"] = {"installed": bool(ssh.get("installed", self.observed_os == "macos")), "enabled": bool(ssh.get("enabled")), "tailscaleOnly": bool(ssh.get("tailscaleOnly"))}
            return out, 0
        if self.command == "ssh-server.verify":
            ssh = self.fixture.get("sshServer", {})
            address = self.a.bootstrap_host or self.fixture.get("tailscale", {}).get("address")
            try:
                parsed = ipaddress.ip_address(address or "")
                if not (parsed in ipaddress.ip_network("100.64.0.0/10") or parsed in ipaddress.ip_network("fd7a:115c:a1e0::/48")): raise ValueError
            except ValueError: return self.fail("INVALID_HOST", "TCP 22 verification requires a Tailscale IP", "failed", "invalid")
            self.record(["tcp-connect", "<tailscale-ip>", "22"])
            if not ssh.get("port22Reachable", ssh.get("enabled")):
                return self.fail("SSH_UNREACHABLE", "TCP port 22 is not reachable through the selected Tailscale IP", "waiting_user", "precondition")
            out["sshServer"] = {"port": 22, "tailscaleAddressHash": sha(address), "reachable": True}; return out, 0
        if self.command == "tailscale.verify":
            gate = self.tailscale_gate()
            return gate or (out, 0)
        if self.command == "version.inspect" and self.fixture.get("openclaw", {}).get("version") not in {None, REQUIRED_VERSION}:
            return self.fail("VERSION_MISMATCH", "installed OpenClaw does not match required version", "failed", "precondition")
        if self.command == "onboarding.status":
            try: out["onboarding"] = sanitize(load_json(self.state_path))
            except (OSError, ValueError, json.JSONDecodeError): out["onboarding"] = None
        if self.command == "pairing.status":
            gate = self.tailscale_gate()
            if gate: return gate
            requests = [r for r in self.fixture.get("deviceRequests", []) if r.get("nodeFingerprint") == self.target_hash]
            if len(requests) > 1: return self.fail("PAIRING_AMBIGUOUS", "more than one current device request matches the target", "failed", "precondition")
            if len(requests) == 1:
                created = now(); expires = created + timedelta(seconds=PLAN_TTL_SECONDS); request = self.a.request_id or str(uuid.uuid4())
                safety = {"target": self.target_hash, "requestIdHash": sha(requests[0].get("requestId")), "provider": self.provider}
                plan_id = sha(safety); challenge = sha({"action": "pairing.approve", "plan": plan_id, "target": self.target_hash, "requestId": request, "expiresAt": iso(expires)})
                plan = {"schemaVersion": 1, "id": plan_id, "action": "pairing.approve", "requestId": request, "createdAt": iso(created), "expiresAt": iso(expires), "targetFingerprint": self.target_hash, "desiredStateHash": sha(self.desired()), "preconditionsHash": sha(safety), "commands": [["openclaw", "devices", "approve", "<exact-current-request-id>"]], "confirmationChallenge": challenge}
                state = self.new_state("waiting_pairing"); state["plan"] = plan; state["pairing"]["requestIdHash"] = sha(requests[0].get("requestId")); atomic_write(self.state_path, state)
                out["plan"] = {"id": plan_id, "expiresAt": iso(expires)}; out["pairingRequest"] = {"requestIdHash": sha(requests[0].get("requestId")), "nodeFingerprint": self.target_hash}; out["confirmationChallenge"] = challenge
        if self.command == "service.status":
            service = self.fixture.get("service", {})
            command_path = self.fixture.get("openclaw", {}).get("path")
            service_path = service.get("openclawPath")
            service_version = service.get("commandVersion")
            if (service_path and command_path and service_path != command_path) or (service_version and service_version != REQUIRED_VERSION):
                return self.fail("SERVICE_RUNTIME_MISMATCH", "service OpenClaw path or version differs from the inspected command", "failed", "precondition", "Create and confirm a repair plan to rebind the user-scoped service to the exact required command.")
        if self.command == "service.status" and self.a.lifecycle_action:
            gate = self.tailscale_gate(reachability=self.a.lifecycle_action != "stop")
            if gate: return gate
            action = f"service.{self.a.lifecycle_action}"; created = now(); expires = created + timedelta(seconds=PLAN_TTL_SECONDS); request = self.a.request_id or str(uuid.uuid4())
            safety = {"target": self.target_hash, "action": action, "provider": self.provider, "service": self.fixture.get("service", {}), "identity": self.fixture.get("tailscale", {}).get("localIdentity")}
            plan_id = sha(safety); challenge = sha({"action": action, "plan": plan_id, "target": self.target_hash, "requestId": request, "expiresAt": iso(expires)})
            operation = "restart" if self.a.lifecycle_action in {"start", "restart"} else "stop"
            plan = {"schemaVersion": 1, "id": plan_id, "action": action, "requestId": request, "createdAt": iso(created), "expiresAt": iso(expires), "targetFingerprint": self.target_hash, "desiredStateHash": sha(self.desired()), "preconditionsHash": sha(safety), "commands": [["openclaw", "node", operation]], "confirmationChallenge": challenge}
            state = self.new_state("planned"); state["plan"] = plan; atomic_write(self.state_path, state)
            out["plan"] = {"id": plan_id, "expiresAt": iso(expires)}; out["planDocument"] = plan; out["nextAction"] = {"kind": "confirm", "message": "Review and confirm the exact lifecycle action.", "resumeCommand": None}
        if self.command == "validate.plan":
            try:
                state = load_json(self.state_path); plan = state.get("plan", {}); out["plan"] = {"id": plan.get("id"), "expiresAt": plan.get("expiresAt")}
            except (OSError, ValueError, json.JSONDecodeError): return self.fail("PLAN_REQUIRED", "no plan is available", "failed", "precondition")
        if self.command == "validate.run":
            gate = self.tailscale_gate()
            if gate: return gate
            if self.a.validation_level == "system": self.record(["openclaw", "nodes", "invoke", "--method", "system.which"])
            if self.a.shell_probe: self.record(["openclaw", "exec", "--host", "node", "--", "<harmless-probe>"])
            wanted = self.a.validation_level
            good = wanted == "preflight" or (wanted == "service" and out["service"]["registered"] and out["service"]["running"]) or (wanted == "connection" and out["pairing"]["connected"]) or (wanted in {"system", "browser"} and out["capabilities"][wanted] == "passed")
            if not good: return self.fail("VALIDATION_FAILED", f"{wanted} validation did not pass", "failed", "failed")
        return out, 0

    def run(self) -> tuple[dict[str, Any], int]:
        invalid = self.validate_inputs()
        if invalid: return invalid
        if self.command in {"bootstrap.inspect", "bootstrap.generate"}: return self.bootstrap_readonly()
        if self.command == "bootstrap.plan": return self.bootstrap_plan()
        if self.command == "bootstrap.apply": return self.bootstrap_apply()
        if self.command in ONBOARDING_PLANNERS: return self.onboarding_plan()
        if self.command in {"tailscale.install-apply", "tailscale.login-apply", "ssh-server.apply"}: return self.onboarding_apply()
        if self.command in PLANNERS: return self.make_plan()
        if self.command in MUTATIONS: return self.apply()
        return self.readonly()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clawpod-node-host")
    p.add_argument("--json", action="store_true"); p.add_argument("--state"); p.add_argument("--target", default="local")
    p.add_argument("--openclaw-version"); p.add_argument("--gateway-host"); p.add_argument("--gateway-port", type=int, choices=range(1, 65536))
    p.add_argument("--tls", action="store_true"); p.add_argument("--tls-fingerprint"); p.add_argument("--request-id"); p.add_argument("--plan-id"); p.add_argument("--confirm")
    p.add_argument("--display-name"); p.add_argument("--node-id"); p.add_argument("--browser-proxy", choices=("enabled", "disabled"), default="disabled"); p.add_argument("--allow-profile", action="append")
    p.add_argument("--pairing-request-id"); p.add_argument("--lifecycle-action", choices=("start", "stop", "restart")); p.add_argument("--validation-level", choices=("preflight", "service", "connection", "system", "browser"), default="preflight"); p.add_argument("--shell-probe", action="store_true")
    p.add_argument("--platform", dest="platform_name", choices=("macos", "windows")); p.add_argument("--transport", choices=sorted(BOOTSTRAP_TRANSPORTS))
    p.add_argument("--bootstrap-host"); p.add_argument("--bootstrap-account"); p.add_argument("--bootstrap-port", type=int)
    p.add_argument("--expected-host-key"); p.add_argument("--credential-ref")
    p.add_argument("group", choices=sorted({c.split(".")[0] for c in COMMANDS})); p.add_argument("action")
    return p


def main() -> int:
    try:
        args = parser().parse_args()
        command = f"{args.group}.{args.action}"
        if command not in COMMANDS: raise ValueError(f"unsupported command: {command}")
        output, code = Harness(args).run()
    except (ValueError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        output = {"ok": False, "command": "unknown", "safetyClass": "S0", "status": "failed", "errors": [{"code": "INVALID_INPUT", "message": sanitize(str(exc))}], "redactions": ["credential", "account-identity", "peer-inventory"]}; code = 2
    print(canonical(sanitize(output)))
    return code


if __name__ == "__main__": raise SystemExit(main())
