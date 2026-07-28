#!/usr/bin/env python3
"""OpenClaw Gateway argv adapter for the ClawPod Cloud Webhooks CLI."""

import json
import subprocess
import sys

COMMANDS = {
    "system.version": ["system", "version"],
    "auth.contract": ["auth", "contract"],
    "auth.status": ["auth", "status"],
    "permissions.list": ["permissions", "list"],
    "presets.list": ["presets", "list"],
    "source.list": ["source", "list"],
    "source.get": ["source", "get"],
    "playbook.list": ["playbook", "list"],
    "rule.list": ["rule", "list"],
    "event.inspect-redacted": ["event-inspect-redacted"],
    "event.verify": ["event-verify"],
    "audit.config": ["audit-config"],
    "mutation.preview": ["mutation-preview"],
    "source.update": ["source-update"],
    "source.test-local": ["source-test-local"],
    "secret.rotate-warning": ["secret-action-warning", "--action", "rotate"],
    "secret.regenerate-warning": ["secret-action-warning", "--action", "regenerate"],
}
# Backward-compatible public name used by manifest parity checks.
MAP = COMMANDS

POSITIONAL_FLAGS = {
    "source.get": "--resource-id",
    "event.inspect-redacted": "--event-id",
    "event.verify": "--event-id",
    "source.update": "--source-id",
}
BOOLEAN_FLAGS = {"--approve", "--require-destination-evidence"}
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
        if token == "--base-url" or token == POSITIONAL_FLAGS.get(command):
            if i + 1 >= len(options) or options[i + 1].startswith("--"):
                raise ValueError(f"{token} requires a value")
            value = options[i + 1]
            if token == "--base-url":
                base_url = value
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

    cli_argv = ["cli-anything-clawpod-cloud-webhooks", "--json"]
    if base_url is not None:
        cli_argv.extend(("--base-url", base_url))
    cli_argv.extend(COMMANDS[command])
    if positional is not None:
        cli_argv.append(positional)
    cli_argv.extend(forwarded)
    return cli_argv


def main(argv=None):
    try:
        cli_argv = translate(list(sys.argv[1:] if argv is None else argv))
        result = subprocess.run(cli_argv, text=True, capture_output=True, timeout=30)
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
