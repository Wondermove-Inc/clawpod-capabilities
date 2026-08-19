# Desktop v3.0.2 — self-contained backend engine

## Summary

The desktop harness is now a **self-contained unit**. The backend engine that
actually drives AT-SPI + xdotool ships inside the harness package at
`engine/desktop` (+ `engine/lib`, `engine/scripts`), so installing the harness
no longer depends on an image-vendored `desktop` system CLI.

## Why

Through v3.0.1 the harness (`desktop.py`) was only a contract/safety wrapper
that called a separate `desktop` backend CLI resolved from `DESKTOP_SYSTEM_CLI`
/ `PATH` / a hardcoded `/workspace/skills/desktop/desktop` fallback. That
backend existed only in the agent image (never in this registry), which caused
two failures:

- Installing the v3 skill overwrote `/workspace/skills/desktop`, deleting the
  image-provided engine — the harness kept working only by accident via the
  image's `/usr/local/bin/desktop` PATH symlink.
- On the next pod boot the image bootstrap (VERSION-based copy) rm-rf'd the
  registry-installed skill and restored v2 — image bootstrap and registry
  self-update deleted each other in a ping-pong.

## Changes

- **Engine vendored into the harness** (`engine/desktop` + `engine/lib/*` +
  `engine/scripts/*`): the AT-SPI/xdotool backend (former v2.0.0 CLI, exit codes
  0/1/2/3/4, `apps/observe/click/focus/screenshot/type/...` command surface).
- **`backend()` resolves the bundled engine first** (after an explicit
  `DESKTOP_SYSTEM_CLI` override, which tests still use): env → `engine/desktop`
  → PATH `desktop` → legacy `/workspace/skills/desktop/desktop`.
- **Exec-bit resilience**: `backend_call` runs the bundled engine through
  `sys.executable` when it installs without the executable bit (the registry
  installer only chmods the harness entrypoint), so exec-bit loss never breaks
  it. The engine shebang is `python3`, so this is equivalent to direct exec.

## Compatibility

- No command-surface change; the wrapper contract and safety classes are
  unchanged from v3.0.1.
- A pre-existing image `desktop` CLI on PATH is still honored only as a lower
  fallback; the bundled engine is authoritative.
