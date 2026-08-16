#!/usr/bin/env python3
"""Guarded OpenClaw 2026.4.11 node-host lifecycle harness.

Default execution is observation-only. Tests and evaluations use a JSON fixture and
command recording; real mutations require the explicit disposable-host gate.
"""
from __future__ import annotations

import argparse
import hashlib
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
MUTATIONS = {
    "install.apply": "S2", "service.start": "S1", "service.stop": "S3",
    "service.restart": "S1", "repair.apply": "S2", "uninstall.apply": "S3",
    "rollback.apply": "S3", "pairing.approve": "S4",
}
PLANNERS = {"install.plan", "repair.plan", "uninstall.plan", "rollback.plan"}
COMMANDS = {
    "system.inspect", "version.inspect", "tailscale.verify", "service.status",
    "onboarding.status", "pairing.status", "validate.plan", "validate.run",
    *PLANNERS, *MUTATIONS,
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
    override = os.environ.get("OPENCLAW_NODE_HOST_NOW")
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
    return root / "openclaw-node-host" / "state.json"


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
        self.fixture_path = os.environ.get("OPENCLAW_NODE_HOST_FIXTURE")
        self.fixture = load_json(Path(self.fixture_path)) if self.fixture_path else {}
        self.observed_os = self.fixture.get("os", "macos" if sys.platform == "darwin" else "windows" if os.name == "nt" else "unsupported")
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
        return f"openclaw-node-host --json --state <state-path> {self.command.replace('.', ' ')}"

    def validate_inputs(self) -> tuple[dict[str, Any], int] | None:
        if not self.a.json:
            return self.fail("INVALID_INPUT", "--json is required", "failed", "invalid")
        if self.a.target != "local":
            return self.fail("INVALID_INPUT", "--target must be local", "failed", "invalid")
        needs_version = self.command in MUTATIONS or self.command in PLANNERS
        if needs_version and self.a.openclaw_version != REQUIRED_VERSION:
            return self.fail("VERSION_SPEC_REJECTED", f"only literal {REQUIRED_VERSION} is accepted", "failed", "invalid")
        if self.a.openclaw_version is not None and self.a.openclaw_version != REQUIRED_VERSION:
            return self.fail("VERSION_SPEC_REJECTED", f"only literal {REQUIRED_VERSION} is accepted", "failed", "invalid")
        if self.observed_os not in {"macos", "windows"}:
            return self.fail("UNSUPPORTED_OS", "only macOS and Windows 11 are supported", "failed", "precondition")
        if self.a.tls_fingerprint and not re.fullmatch(r"[a-f0-9]{64}", self.a.tls_fingerprint):
            return self.fail("INVALID_INPUT", "TLS fingerprint must be lowercase SHA-256", "failed", "invalid")
        node_version = self.fixture.get("node", {}).get("version")
        if node_version is not None:
            match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(node_version))
            if not match or tuple(map(int, match.groups())) < (22, 14, 0):
                return self.fail("NODE_VERSION_UNSUPPORTED", "Node.js 22.14.0 or newer is required", "failed", "precondition")
        return None

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
        if not self.fixture_path or os.environ.get("OPENCLAW_NODE_HOST_DISPOSABLE_INTEGRATION") != "1":
            return self.simulate(state, plan)
        return self.live_mutation(state, plan)

    def record(self, argv: list[str]) -> None:
        path = os.environ.get("OPENCLAW_NODE_HOST_RECORD")
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
        timeout = float(os.environ.get("OPENCLAW_NODE_HOST_COMMAND_TIMEOUT", "60"))
        attempts = max(1, min(int(os.environ.get("OPENCLAW_NODE_HOST_RETRY_ATTEMPTS", "2")), 3))
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
        if self.command in PLANNERS: return self.make_plan()
        if self.command in MUTATIONS: return self.apply()
        return self.readonly()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="openclaw-node-host")
    p.add_argument("--json", action="store_true"); p.add_argument("--state"); p.add_argument("--target", default="local")
    p.add_argument("--openclaw-version"); p.add_argument("--gateway-host"); p.add_argument("--gateway-port", type=int, choices=range(1, 65536))
    p.add_argument("--tls", action="store_true"); p.add_argument("--tls-fingerprint"); p.add_argument("--request-id"); p.add_argument("--plan-id"); p.add_argument("--confirm")
    p.add_argument("--display-name"); p.add_argument("--node-id"); p.add_argument("--browser-proxy", choices=("enabled", "disabled"), default="disabled"); p.add_argument("--allow-profile", action="append")
    p.add_argument("--pairing-request-id"); p.add_argument("--lifecycle-action", choices=("start", "stop", "restart")); p.add_argument("--validation-level", choices=("preflight", "service", "connection", "system", "browser"), default="preflight"); p.add_argument("--shell-probe", action="store_true")
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
