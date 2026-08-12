#!/usr/bin/env python3
"""OpenClaw Gateway argv adapter for the ClawPod Cloud Webhooks CLI."""

import json
from pathlib import Path
import subprocess
import sys

COMMANDS = {
    "system.version": ["system", "version"],
    "auth.contract": ["auth", "contract"],
    "auth.onboard": ["auth", "onboard"],
    "auth.status": ["auth", "status"],
    "permissions.list": ["permissions", "list"],
    "presets.list": ["presets", "list"],
    "source.list": ["source", "list"],
    "source.get": ["source", "get"],
    "source.create": ["source", "create"],
    "source.update": ["source", "update"],
    "source.delete": ["source", "delete"],
    "source.enable": ["source-enable"],
    "source.disable": ["source-disable"],
    "source.rotate-secret": ["source-rotate-secret"],
    "source.regenerate": ["source-regenerate"],
    "playbook.list": ["playbook", "list"],
    "playbook.get": ["playbook", "get"],
    "playbook.create": ["playbook", "create"],
    "playbook.update": ["playbook", "update"],
    "playbook.delete": ["playbook", "delete"],
    "rule.list": ["rule", "list"],
    "rule.get": ["rule", "get"],
    "rule.create": ["rule", "create"],
    "rule.update": ["rule", "update"],
    "rule.delete": ["rule", "delete"],
    "rule.enable": ["rule-enable"],
    "rule.disable": ["rule-disable"],
    "rule.reorder": ["rule-reorder"],
    "event.list": ["event", "list"],
    "event.get": ["event", "get"],
    "event.inspect-redacted": ["event-inspect-redacted"],
    "event.verify": ["event-verify"],
    "audit.config": ["audit-config"],
    "mutation.preview": ["mutation-preview"],
    "source.test-local": ["source-test-local"],
    "secret.rotate-warning": ["secret-action-warning", "--action", "rotate"],
    "secret.regenerate-warning": ["secret-action-warning", "--action", "regenerate"],
}
# Backward-compatible public name used by manifest parity checks.
MAP = COMMANDS

POSITIONAL_FLAGS = {
    "source.get": "--resource-id",
    "source.update": "--source-id",
    "source.delete": "--source-id",
    "source.enable": "--source-id",
    "source.disable": "--source-id",
    "source.rotate-secret": "--source-id",
    "source.regenerate": "--source-id",
    "playbook.get": "--resource-id",
    "playbook.update": "--playbook-id",
    "playbook.delete": "--playbook-id",
    "rule.get": "--resource-id",
    "rule.update": "--rule-id",
    "rule.delete": "--rule-id",
    "rule.enable": "--rule-id",
    "rule.disable": "--rule-id",
    "rule.reorder": "--rule-id",
    "event.get": "--resource-id",
    "event.inspect-redacted": "--event-id",
    "event.verify": "--event-id",
}
BOOLEAN_FLAGS = {"--approve", "--approve-login", "--require-destination-evidence", "--insecure-skip-tls-verify", "--i-understand-insecure-tls-risk"}
GLOBAL_VALUE_FLAGS = {"--base-url", "--ca-cert", "--timeout", "--retries"}
GLOBAL_BOOLEAN_FLAGS = {"--insecure-skip-tls-verify", "--i-understand-insecure-tls-risk"}
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def failure(code, message):
    return json.dumps(
        {"ok": False, "error": {"code": code, "message": message}},
        sort_keys=True,
        separators=(",", ":"),
    )


def translate(gateway_argv):
    """Translate Gateway baseArgv + argMap argv to the Click CLI contract."""
    if not gateway_argv:
        raise ValueError("command is required")
    command = gateway_argv[0]
    if command not in COMMANDS:
        raise ValueError("unknown command")

    options = list(gateway_argv[1:])
    base_url = None
    positional = None
    forwarded = []
    i = 0
    while i < len(options):
        token = options[i]
        if not token.startswith("--"):
            raise ValueError("malformed arguments")
        if token in GLOBAL_VALUE_FLAGS or token == POSITIONAL_FLAGS.get(command):
            if i + 1 >= len(options) or options[i + 1].startswith("--"):
                raise ValueError(f"{token} requires a value")
            value = options[i + 1]
            if token == "--base-url":
                base_url = value
            elif token in GLOBAL_VALUE_FLAGS:
                forwarded.extend((token, value))
            else:
                positional = value
            i += 2
            continue
        if token in BOOLEAN_FLAGS:
            if i + 1 < len(options) and not options[i + 1].startswith("--"):
                value = options[i + 1].lower()
                if value in TRUE_VALUES:
                    forwarded.append(token)
                elif value not in FALSE_VALUES:
                    raise ValueError(f"{token} requires a boolean value")
                i += 2
            else:
                forwarded.append(token)
                i += 1
            continue
        if i + 1 >= len(options) or options[i + 1].startswith("--"):
            raise ValueError(f"{token} requires a value")
        forwarded.extend((token, options[i + 1]))
        i += 2

    positional_flag = POSITIONAL_FLAGS.get(command)
    if positional_flag and positional is None:
        raise ValueError(f"{positional_flag} is required")

    cli_argv = [
        sys.executable,
        "-m",
        "cli_anything.clawpod_cloud_webhooks.clawpod_cloud_webhooks_cli",
        "--json",
    ]
    if base_url is not None:
        cli_argv.extend(("--base-url", base_url))
    global_forwarded=[]; command_forwarded=[]
    for index,token in enumerate(forwarded):
        target=global_forwarded if token in GLOBAL_VALUE_FLAGS or token in GLOBAL_BOOLEAN_FLAGS or (index and forwarded[index-1] in GLOBAL_VALUE_FLAGS) else command_forwarded
        target.append(token)
    cli_argv.extend(global_forwarded)
    cli_argv.extend(COMMANDS[command])
    forwarded=command_forwarded
    if positional is not None:
        cli_argv.append(positional)
    cli_argv.extend(forwarded)
    return cli_argv


def main(argv=None):
    try:
        cli_argv = translate(list(sys.argv[1:] if argv is None else argv))
        package_root = str(Path(__file__).resolve().parent)
        result = subprocess.run(
            cli_argv,
            text=True,
            capture_output=True,
            timeout=30,
            cwd=package_root,
        )
        if result.stdout:
            sys.stdout.write(result.stdout)
        else:
            sys.stdout.write(failure("cli_error", "CLI execution failed"))
        return result.returncode
    except subprocess.TimeoutExpired:
        print(failure("adapter_timeout", "CLI execution timed out"))
        return 2
    except ValueError as exc:
        print(failure("adapter_error", str(exc)))
        return 2
    except Exception:
        # Never echo process errors or backend diagnostics, which may contain secrets.
        print(failure("adapter_error", "adapter execution failed"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
