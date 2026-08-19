# Desktop v3.0.4 — implement the advertised engine commands (contract↔engine parity)

## Summary

The contract (`command_contracts.json` / `harness.json`) advertised ~20 commands
that the bundled backend engine did not implement, so calls fell through to the
engine's `Unknown command: <cmd>` path. This release implements those commands in
the bundled engine so the advertised surface actually works end to end.

## Root cause

`desktop.py` routes a contract command to the engine as `cmd.replace('.','-')`
(e.g. `file-dialog.open` → engine `file-dialog-open`). The bundled engine's
dispatch only covered the AT-SPI/xdotool core (~27 commands); window management,
clipboard, process control, file-dialog/dialog, download handling, and
`pointer.move` had no engine branch and returned `Unknown command`. The contract
was designed for a fuller backend; bundling the subset engine in 3.0.2 created
the mismatch.

## Implemented (bundled, self-contained — no new image packages)

- **window**: `window-activate/close/minimize/maximize/restore/resize/move`
  via `xdotool` (+ `xprop _NET_WORKAREA` so maximize respects panels; prior
  geometry cached for restore). `window.move` was already special-cased in
  desktop.py; the engine now also handles it for parity.
- **clipboard**: `clipboard-read/write/clear` via `Gtk.Clipboard` (GTK3 already
  present) — no `xclip`/`xsel` dependency, so no image change.
- **process**: `process-kill` (SIGKILL) / `process-terminate` (SIGTERM), with a
  guard that refuses PID ≤ 1, the engine's own tree, and session-critical
  processes (X server, D-Bus, AT-SPI, gateway, entrypoint, WM).
- **file-dialog / dialog**: `file-dialog-open/save/choose-directory/cancel` and
  `dialog-respond`, hybrid and portal-aware — AT-SPI detects and verifies the
  live chooser (native GTK or xdg-desktop-portal-gtk) before acting, then drives
  it (Ctrl+L → type path → accessible default button, Return fallback; cancel via
  accessible Cancel button or Escape). Never acts blindly on an unfocused window.
- **download**: `download-wait` (blocks until the newest download settles),
  `download-move`, `download-quarantine` (relocates into a 0700 dir, mode 0600,
  exec bits stripped).
- **pointer**: `pointer-move` via `xdotool mousemove`.

## Notes

- No manifest/contract schema change: these commands were already declared; only
  the engine gained implementations. Version bumped 3.0.3 → 3.0.4 across
  harness/skill/command_contracts/desktop.py/linkedHarness.
- New commands are NOT added to the macro `ALLOWED_COMMANDS` whitelist, so the
  desktop.py approval/idempotency gate cannot be bypassed via macros/chains.
- `file-dialog.*` and `dialog.respond` remain gated on `DBUS_SESSION_BUS_ADDRESS`
  by desktop.py (unchanged); driving is AT-SPI/keyboard because portal-rendered
  choosers are on-screen GTK dialogs.
