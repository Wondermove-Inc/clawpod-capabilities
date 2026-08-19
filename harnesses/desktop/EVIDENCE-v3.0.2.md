# Desktop v3.0.2 — evidence

## Self-contained backend resolution

With no environment and no PATH, the harness resolves its own bundled engine:

```
$ env -i python3 harnesses/desktop/desktop.py capabilities
result.backend           = <package>/harnesses/desktop/engine/desktop
result.backendAvailable  = true
result.version           = 3.0.2
```

This proves the unit no longer depends on `DESKTOP_SYSTEM_CLI`, a PATH `desktop`
symlink, or the `/workspace/skills/desktop/desktop` legacy fallback.

## Backend interface parity

The vendored engine is the same AT-SPI/xdotool backend the v3 wrapper was
designed against (observe JSON shape with `active_window`/`nodes`/`screenshot`,
exit code 4 = AT-SPI failure, the `apps/observe/click/focus/screenshot/type/...`
command surface referenced by `MAP`). No wrapper contract change was required.

## Notes

- Live AT-SPI/xdotool operation still requires a provisioned display session
  (DISPLAY + at-spi2 registry). `capabilities`/`environment.preflight` report
  backend availability and D-Bus/AT-SPI status; they do not fabricate a session.
