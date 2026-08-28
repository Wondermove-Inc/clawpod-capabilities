#!/usr/bin/env python3
"""Generate harness.json from the option tables in ops_troubleshooting.py so the CLI and manifest cannot drift."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ops_troubleshooting", ROOT / "ops_troubleshooting.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

DESCRIPTION = (
    "Use to troubleshoot Linux host, network, Kubernetes, and security-hygiene problems with bounded read-only "
    "diagnostics that record every command as evidence, then propose plan-bound remediation (service restart, "
    "rollout restart, managed-pod delete) that runs only after explicit approval. Use soc-event-correlation for "
    "attack-story analysis, org-operations for incident reporting, and node-host for node onboarding."
)
WHEN_TO_USE = [
    "Diagnose why this server is slow or out of disk",
    "Find out why the pod keeps restarting",
    "Check the certificate, DNS, and port reachability for this service",
    "Review recent logins, failed auth attempts, and pending security updates",
    "Plan and, after approval, restart the failing service or rollout",
]
OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["ok", "schemaVersion", "command"],
    "properties": {
        "ok": {"type": "boolean"},
        "schemaVersion": {"type": "number"},
        "command": {"type": ["string", "null"]},
        "data": {},
        "effects": {"type": "array"},
        "error": {"type": "object"},
    },
    "additionalProperties": False,
}
COMMAND_DESCRIPTIONS = {
    "version": "Report the harness release version, limits, and remediation allowlist.",
    "host.overview": "Uptime, load, memory, swap, root disk, OS, and top CPU processes with threshold findings.",
    "host.disk": "Filesystem space and inode usage for local mounts with threshold findings.",
    "host.processes": "Top processes by CPU or memory, flagging zombies.",
    "host.services": "Failed systemd units, or the detailed state and restart count of one unit.",
    "host.journal": "Bounded, redacted journal lines for a window, unit, priority, or pattern.",
    "net.ports": "Listening TCP/UDP sockets and which are exposed on all interfaces.",
    "net.dns": "Resolve a name with the host resolver and report timing and nameservers.",
    "net.reach": "TCP reachability to host:port with optional TLS certificate inspection and expiry findings.",
    "net.route": "Default routes and interface state from iproute2.",
    "security.logins": "Recent login sessions from wtmp with per-user and per-source counts.",
    "security.auth-events": "Failed/accepted SSH logins and sudo use from the journal with brute-force findings.",
    "security.users": "Interactive accounts, uid 0 accounts, admin group members, authorized_keys counts, and sensitive-file metadata.",
    "security.updates": "Pending package updates, security updates, and reboot-required state (apt or dnf).",
    "change.recent": "Recently modified files under an allowlisted root plus recent package operations.",
    "k8s.context": "Current kubectl context, client/server versions, and read permissions.",
    "k8s.nodes": "Node readiness, pressure conditions, taints, and optional usage.",
    "k8s.pods": "Unhealthy pods with restart counts, waiting reasons, OOMKilled history, and scheduling failures.",
    "k8s.describe": "kubectl describe for an allowlisted read-only kind (never secrets or configmaps).",
    "k8s.logs": "Bounded pod logs with tail, window, container, previous instance, and pattern filter.",
    "k8s.events": "Warning (or all) events sorted by recency with reason counts.",
    "k8s.rollout": "Rollout status, replica counts, conditions, images, and history for a workload.",
    "triage.host": "One bounded pass over overview, disk, failed units, journal errors, and ports.",
    "triage.k8s": "One bounded pass over context, nodes, unhealthy pods, and warning events.",
    "remediate.plan": "Snapshot preconditions and write an approval-bound plan for one allowlisted action.",
    "remediate.apply": "Apply an approved, unexpired plan once, after re-checking preconditions, and verify the outcome.",
}


def arg_entry(name: str, optional: bool) -> tuple[dict, dict]:
    flag, value_type, _ = module.OPTIONS[name]
    if value_type == "boolean":
        return {"type": "boolean"}, {"arg": name, "type": "booleanFlag", "flag": flag, "valueType": "boolean", "optional": optional}
    if value_type == "integer":
        return {"type": "number"}, {"arg": name, "type": "option", "flag": flag, "valueType": "integer", "optional": optional}
    if value_type.startswith("path:"):
        role = value_type.split(":", 1)[1]
        return {"type": "string"}, {"arg": name, "type": "option", "flag": flag, "valueType": "path", "optional": optional, "pathRole": role}
    if value_type.startswith("enum:"):
        values = value_type.split(":", 1)[1].split(",")
        return {"type": "string", "enum": values}, {"arg": name, "type": "option", "flag": flag, "valueType": "enum", "optional": optional, "values": values}
    return {"type": "string"}, {"arg": name, "type": "option", "flag": flag, "valueType": "string", "optional": optional}


def build() -> dict:
    commands = {}
    for command, options in module.COMMAND_OPTIONS.items():
        properties, required, arg_map = {}, [], []
        for name, optional in tuple((common, True) for common in module.COMMON) + options:
            schema, arg = arg_entry(name, optional)
            properties[name] = schema
            arg_map.append(arg)
            if not optional:
                required.append(name)
        input_schema = {"type": "object", "properties": properties, "additionalProperties": False}
        if required:
            input_schema["required"] = required
        commands[command] = {
            "description": COMMAND_DESCRIPTIONS[command],
            "baseArgv": [command],
            "safetyClasses": module.SAFETY.get(command, ["readOnly"]),
            "inputSchema": input_schema,
            "outputSchema": OUTPUT_SCHEMA,
            "argMap": arg_map,
        }
    return {
        "schemaVersion": 1,
        "kind": "openclaw.harness.v1",
        "name": "ops-troubleshooting",
        "title": "Ops Troubleshooting",
        "description": DESCRIPTION,
        "version": module.VERSION,
        "entrypoint": "./ops_troubleshooting.py",
        "packageRoot": ".",
        "execution": {"cwd": ".", "timeoutMs": 90000, "requiresJson": True},
        "whenToUse": WHEN_TO_USE,
        "capabilities": [
            "bounded-read-only-diagnostics",
            "evidence-recorded-commands",
            "secret-redaction",
            "linux-host-network-security",
            "kubernetes-read-only",
            "plan-bound-remediation",
        ],
        "authModel": {"type": "protected-environment-or-existing-config", "storesSecrets": False, "requiresHumanAccount": False},
        "commands": commands,
    }


def main(argv: list[str]) -> int:
    manifest = build()
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    path = ROOT / "harness.json"
    if "--check" in argv:
        if not path.is_file() or path.read_text(encoding="utf-8") != rendered:
            print("harness.json is out of date; run scripts/generate_manifest.py", file=sys.stderr)
            return 1
        print("harness.json is current")
        return 0
    path.write_text(rendered, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT.parent.parent)} with {len(manifest['commands'])} commands")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
