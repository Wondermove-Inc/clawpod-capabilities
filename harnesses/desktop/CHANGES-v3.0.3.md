# Desktop v3.0.3 — declare passthroughEnv for gateway harness runs

## Summary

The harness now declares `passthroughEnv: ["DISPLAY", "DBUS_SESSION_BUS_ADDRESS"]`
so that when it runs via the gateway (`harness.run`), the display and D-Bus
session env vars are inherited from the gateway process.

## Why

The gateway executes harnesses with a minimal, isolated environment (only
PATH/SystemRoot/WINDIR) for security. Desktop's backend reads `DISPLAY` to reach
the X server and `DBUS_SESSION_BUS_ADDRESS` for portal-backed dialogs. Without
those, `harness.run desktop app.list` / `ui.observe` failed with
`DISPLAY_STATE_UNAVAILABLE` even though direct execution (which inherits the pod
env) worked. This is a run-environment gap, not an engine defect.

The host runtime (OpenClaw 2026.x) added a `passthroughEnv` manifest contract:
a harness may declare a fixed allowlist of benign display/D-Bus/XDG session vars
to inherit; anything outside that allowlist (credentials, tokens, loaders) is
rejected at discovery and can never be passed through. This is covered by the
manifest digest and trust gate like any other manifest change.

## Changes

- `harness.json`: `passthroughEnv: ["DISPLAY", "DBUS_SESSION_BUS_ADDRESS"]`.
- Version 3.0.2 -> 3.0.3 (harness/skill/command_contracts/desktop.py/linkedHarness).

## Requirements / notes

- Requires an OpenClaw host that supports the `passthroughEnv` manifest field.
  On an older host the field would be rejected by the strict manifest schema, so
  install this only where the host runtime advertises passthroughEnv support.
- `DISPLAY` restores app.list/ui.observe and all AT-SPI/xdotool operations.
- `DBUS_SESSION_BUS_ADDRESS` only matters for portal actions (file dialogs); if
  the pod has no D-Bus session, portal actions stay blocked with a clear message,
  while core observe/click/type continue to work.
