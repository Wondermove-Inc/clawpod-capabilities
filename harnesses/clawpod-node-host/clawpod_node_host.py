#!/usr/bin/env python3
"""ClawPod Node app onboarding: agent Tailscale and offline installer selection."""
from __future__ import annotations

import argparse
import json
import re
from typing import Any

COMMANDS = {"agent.status", "agent.login", "installer.info"}

SECRET_PATTERN = re.compile(
    r"(?i)(bearer\s+\S+|(?:token|password|secret|api[_-]?key|auth)[=:]\s*\S+|"
    r"tskey-[A-Za-z0-9_-]+|-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----)",
    re.DOTALL,
)


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): ("[REDACTED]" if re.search(r"(?i)(token|password|secret|auth|private.?key|email|login)", str(k)) else sanitize(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        return SECRET_PATTERN.sub("[REDACTED]", value)
    return value


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def parser() -> argparse.ArgumentParser:
    p = Parser(prog="clawpod-node-host")
    p.add_argument("--json", action="store_true")
    p.add_argument("--target", default="local")
    p.add_argument("--platform", dest="platform_name", choices=("linux", "macos", "windows"))
    p.add_argument("--arch", choices=("x64", "arm64"))
    p.add_argument("--gateway-url")
    p.add_argument("group", choices=("agent", "installer"))
    p.add_argument("action")
    return p


def main() -> int:
    command = "unknown"
    try:
        args = parser().parse_args()
        command = f"{args.group}.{args.action}"
        if command not in COMMANDS:
            raise ValueError("Use agent status, agent login, or installer info.")
        if not args.json or args.target != "local":
            raise ValueError("--json is required and --target must be local.")
        if command == "installer.info":
            from installer import installer_info
            output, code = installer_info(args)
        else:
            if args.platform_name is not None or args.arch is not None or args.gateway_url is not None:
                raise ValueError("Target-computer options apply only to installer info.")
            from agent_tailscale import run_agent
            output, code = run_agent(command)
    except (ValueError, OSError) as exc:
        output = {"ok": False, "command": command, "safetyClass": "S0", "status": "failed",
                  "effects": [], "errors": [{"code": "INVALID_INPUT", "message": str(exc)}],
                  "redactions": ["credential"]}
        code = 2
    print(json.dumps(sanitize(output), sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
