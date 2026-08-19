# Desktop v3.0.5 — implement stubbed observation commands + file-dialog robustness

## Summary

Two follow-ups to 3.0.4:

1. **Observation commands were stubbed.** `desktop.py` returned a canned
   `{state:completed, input:...}` for `window.list`, `window.get`, `app.get`,
   `screen.list`, `dialog.inspect`, `clipboard.inspect`, `download.inspect`
   instead of real data — so, e.g., an agent could not discover window ids to
   feed the window.* management added in 3.0.4. These now route to the engine
   and return real observations.
2. **File-dialog driving had real-GUI defects** (found by live testing against a
   Zenity file chooser), now fixed.

## Observation commands (now real)

- Removed the 7 commands from `desktop.py`'s synthetic set; they flow through the
  normal read-only backend path (they are already in `OBS`, so no
  approval/idempotency is required).
- Engine implementations:
  - `window-list` / `window-get` — visible windows with X id, name, geometry, pid
    (xdotool).
  - `screen-list` — connected monitors (xrandr, with a display-geometry fallback).
  - `app-get` — one accessible application's windows (AT-SPI).
  - `dialog-inspect` — active dialog title, buttons, and text fields (AT-SPI).
  - `clipboard-inspect` — clipboard text presence, length, and target atoms
    (Gtk.Clipboard), without forcing the caller to pull possibly-sensitive text.
  - `download-inspect` — download directory listing with size/mtime/partial flag.

## File-dialog fixes (regressions found in live GUI testing)

- **Detection**: `_find_active_dialog` required MODAL/ACTIVE, but Zenity's
  GtkFileChooserDialog exposes only SHOWING+VISIBLE, so `file-dialog.cancel` /
  `dialog.inspect` missed it. Now any SHOWING dialog/file-chooser/alert qualifies;
  MODAL/ACTIVE/FOCUSED and the file-chooser role only raise priority. Dropped the
  `frame` role so the desktop root is never mistaken for a dialog.
- **Path entry**: typing a path char-by-char raced the location entry's
  autocompletion and corrupted the tail (`/a/b.txt` → `/a/b.txtt.txt`). Now the
  path is placed via `/`-popup → select-all → clipboard paste (atomic), then
  Return.
- **Confirmation**: no longer trusts a single AT-SPI "dialog not found" (which can
  be a transient miss) — confirms the dialog is gone across several polls, and on
  failure reports an honest error instead of a false success.

## Notes

- No manifest/contract schema change; version bumped 3.0.4 → 3.0.5 across
  harness/skill/capability/command_contracts/desktop.py/linkedHarness/registry.
- Parity test tightened: the 7 observation commands are now required to have
  engine dispatch (no longer treated as synthetic).
