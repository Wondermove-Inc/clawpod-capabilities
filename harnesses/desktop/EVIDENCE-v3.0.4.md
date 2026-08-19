# Evidence — Desktop v3.0.4

## Static / unit

- `python3 -m py_compile` clean for engine + all new lib modules
  (window_manager, process_ops, clipboard_ops, file_dialog, download_ops,
  xdotool_engine).
- `scripts/validate.py`: OK, 41 capability entries.
- New tests in `tests/test_desktop.py`:
  - `test_engine_implements_all_advertised_commands` — parity guard: every
    contract command that desktop.py delegates to the engine now has an engine
    dispatch branch (previously ~20 missing, incl. `pointer.drag-drop` on the
    accessibility path).
  - `test_engine_new_commands_not_unknown` — new commands reach their handler,
    never the `Unknown command` fall-through.
  - `test_portal_action_blocked_without_dbus` — `file-dialog.open` blocked with
    `DBUS_SESSION_UNAVAILABLE` when the D-Bus session address is absent.

## Live pod smoke (RND, sooyoung agent; ran from /tmp, workspace untouched)

- **clipboard** roundtrip: `clipboard-write "clawpod-smoke-3.0.4"` → `Clipboard set (19 chars)`;
  `clipboard-read` → `clawpod-smoke-3.0.4`; `clipboard-clear` → subsequent read empty.
  (Fixed a GTK3 API bug found here: clipboard is `Gtk.Clipboard.get()`, not the
  GTK4-only `Gdk.Clipboard`.)
- **process**: `process-terminate <sleep pid>` sends SIGTERM and the process
  exits. Guard refuses pid ≤ 1, the engine's own tree, and session-critical
  processes by name — verified refusals for `Xvfb` (166) and `dbus-daemon` (184).
- **download**: `download-move` relocates a completed file; `download-quarantine`
  moves into `~/.cache/desktop/quarantine/` as `-rw-------` (mode 0600, exec bits
  stripped).
- **window**: `_work_area()` reads `_NET_WORKAREA` panel-aware → `(0, 27, 1920, 1053)`
  (top panel excluded), so maximize will not cover the XFCE panel.
- **file-dialog**: `file-dialog-cancel` with no dialog present returns a clean
  `no active file/confirmation dialog found` error within seconds (no hang).

## Not exercised live (by design)

Window move/resize/maximize and file-dialog confirm act on real on-screen
windows; they were verified at dispatch + logic level only, not driven against a
live agent's windows to avoid disrupting an active session. Full interactive
verification belongs in a controlled desktop or the installing agent's own
preflight.
