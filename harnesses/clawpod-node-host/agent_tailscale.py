"""Agent-side Tailscale sign-in; never install or reconfigure the user's node."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import threading

SIGN_IN_URL = re.compile(r"https://login\.tailscale\.com/[^\s<>\"']+")


class TailscaleError(Exception):
    def __init__(self, code: str, message: str, exit_code: int = 6):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def status(fixture: dict | None) -> dict:
    if fixture is not None:
        raw = fixture.get("agentTailscale")
        if not isinstance(raw, dict):
            raise TailscaleError("AGENT_TAILSCALE_STATUS_FAILED", "Invalid agent Tailscale fixture.")
        if raw.get("present") is False:
            raise TailscaleError("AGENT_TAILSCALE_ABSENT", "Tailscale CLI is missing from the agent runtime.", 5)
        value = {"BackendState": raw.get("backendState")}
    else:
        try:
            result = subprocess.run(["tailscale", "status", "--json"], text=True,
                                    capture_output=True, timeout=10, check=False)
            value = json.loads(result.stdout)
            # tailscale can report NeedsLogin with a nonzero exit status.
            if result.returncode and (not isinstance(value, dict) or value.get("BackendState") != "NeedsLogin"):
                raise ValueError("status command failed")
        except FileNotFoundError:
            raise TailscaleError("AGENT_TAILSCALE_ABSENT", "Tailscale CLI is missing from the agent runtime.", 5) from None
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise TailscaleError("AGENT_TAILSCALE_STATUS_FAILED", "Could not read Tailscale status; check the agent's tailscaled service.") from None
    state = value.get("BackendState") if isinstance(value, dict) else None
    if not isinstance(state, str) or not state:
        raise TailscaleError("AGENT_TAILSCALE_STATUS_FAILED", "Tailscale did not report a backend state.")
    return {"present": True, "state": state, "ready": state == "Running"}


def login_url(fixture: dict | None) -> str:
    if fixture is not None:
        raw = fixture.get("agentTailscale", {}).get("loginUrl")
        if isinstance(raw, str) and SIGN_IN_URL.fullmatch(raw):
            return raw
        raise TailscaleError("LOGIN_URL_UNAVAILABLE", "Tailscale did not produce an interactive sign-in link.")
    timeout = float(os.environ.get("CLAWPOD_NODE_HOST_COMMAND_TIMEOUT", "30"))
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Command timeout must be finite and positive.")
    timeout = min(timeout, 30)
    try:
        proc = subprocess.Popen(["tailscale", "login"], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
    except OSError:
        raise TailscaleError("LOGIN_URL_UNAVAILABLE", "Could not start Tailscale sign-in; check tailscaled.") from None
    found: queue.Queue[str | None] = queue.Queue(maxsize=1)

    def read_url() -> None:
        try:
            for line in proc.stdout:
                match = SIGN_IN_URL.search(line)
                if match:
                    found.put(match.group(0))
                    return
        finally:
            if found.empty():
                found.put(None)

    reader = threading.Thread(target=read_url, daemon=True)
    reader.start()
    try:
        try:
            url = found.get(timeout=timeout)
        except queue.Empty:
            url = None
    finally:
        # The daemon owns sign-in; stop only this CLI waiter, then reap it.
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        reader.join(timeout=1)
        proc.stdout.close()
    if not url:
        raise TailscaleError("LOGIN_URL_UNAVAILABLE", "Tailscale did not produce an interactive sign-in link; check tailscaled and retry.")
    return url


def run_agent(command: str) -> tuple[dict, int]:
    out = {"ok": True, "command": command, "safetyClass": "S4" if command == "agent.login" else "S0",
           "status": "success", "effects": [], "errors": [], "redactions": ["credential", "peer-inventory"]}
    try:
        fixture_path = os.environ.get("CLAWPOD_NODE_HOST_FIXTURE")
        fixture = json.loads(Path(fixture_path).read_text()) if fixture_path else None
        if fixture_path and not isinstance(fixture, dict):
            raise ValueError("Agent fixture must be an object.")
        observed = status(fixture)
        out["agentTailscale"] = observed
        if observed["ready"]:
            out["nextAction"] = {
                "kind": "user", "step": 2, "resumeCommand": None,
                "message": "Agent Tailscale is connected. Help the user install Tailscale from https://tailscale.com/download if missing and sign in to the same tailnet on their computer. Reuse an existing connection. Verify both devices can communicate, then confirm the computer's OS/CPU and select its ClawPod Node installer.",
            }
            return out, 0
        if observed["state"] != "NeedsLogin":
            out["status"] = "waiting_user"
            out["nextAction"] = {
                "kind": "user", "step": 1, "resumeCommand": "agent status",
                "message": f"Agent Tailscale reports {observed['state']}. Check its daemon and any pending device authorization, then recheck agent status. Do not treat this as a completed sign-in or start a new login blindly.",
            }
            return out, 3
        if command == "agent.status":
            out["status"] = "waiting_user"
            out["nextAction"] = {"kind": "user", "step": 1, "resumeCommand": "agent login",
                                 "message": "The agent's own Tailscale is signed out. Run agent login and send its link to the user, then recheck agent status after sign-in."}
            return out, 3
        url = login_url(fixture)
        record = os.environ.get("CLAWPOD_NODE_HOST_RECORD")
        if record:
            with open(record, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({"argv": ["tailscale", "login"]}) + "\n")
        out["status"] = "waiting_user"
        out["agentTailscale"]["url"] = url
        out["effects"] = [{"type": "tailscale-sign-in-started"}]
        out["nextAction"] = {
            "kind": "user", "step": 1, "resumeCommand": "agent status",
            "message": f"Send this agent sign-in link to the user: {url} . Ask them to use the tailnet intended for the computer connection. Recheck agent status after sign-in; a link alone does not prove connection.",
        }
        return out, 3
    except TailscaleError as exc:
        out.update(ok=False, status="failed", errors=[{"code": exc.code, "message": str(exc)}])
        return out, exc.exit_code
