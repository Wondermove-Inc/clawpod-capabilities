"""Macro recording and playback with command whitelist validation."""

import json
import os
import sys

from .exit_codes import ALLOWED_COMMANDS

MACRO_DIR = os.environ.get('DESKTOP_MACRO_DIR', '/workspace/skills/desktop/macros')


def _validate_commands(commands):
    """Validate that all commands in macro are whitelisted."""
    for cmd_str in commands:
        parts = cmd_str.strip().split()
        if not parts:
            continue
        sub_cmd = parts[0].lower()
        if sub_cmd not in ALLOWED_COMMANDS:
            print(f"ERROR: '{sub_cmd}' is not a valid desktop command. "
                  f"Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}", file=sys.stderr)
            sys.exit(1)


def save_macro(name, commands):
    """Save a list of commands as a named macro. Validates commands."""
    _validate_commands(commands)
    os.makedirs(MACRO_DIR, exist_ok=True)
    path = os.path.join(MACRO_DIR, f"{name}.json")
    with open(path, 'w') as f:
        json.dump({"name": name, "commands": commands}, f, indent=2)
    print(f"Macro saved: {name} ({len(commands)} commands)")


def run_macro(name, executor):
    """Run a saved macro. Validates commands before execution."""
    path = os.path.join(MACRO_DIR, f"{name}.json")
    if not os.path.exists(path):
        print(f"ERROR: Macro '{name}' not found", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        data = json.load(f)
    _validate_commands(data["commands"])
    from .power_commands import chain
    chain(data["commands"], executor)
    print(f"Macro completed: {name}")


def list_macros():
    """List available macros."""
    if not os.path.isdir(MACRO_DIR):
        print("No macros found")
        return
    macros = [f.replace('.json', '') for f in os.listdir(MACRO_DIR) if f.endswith('.json')]
    if not macros:
        print("No macros found")
        return
    for m in sorted(macros):
        print(f"  {m}")
