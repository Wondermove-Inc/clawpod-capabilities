# Desktop v3.0.3 — evidence

## Manifest declares passthroughEnv

`harness.json` now carries `passthroughEnv: ["DISPLAY", "DBUS_SESSION_BUS_ADDRESS"]`.
Both names are on the host runtime's fixed passthrough allowlist
(display/D-Bus/XDG session vars), so the manifest passes discovery validation and
becomes trust-eligible. A non-allowlisted name (e.g. a token/key) would be
rejected at discovery and could never be trusted or run.

## Expected gateway behavior

With a passthroughEnv-aware host:
- `harness.run desktop capabilities` / `environment.preflight`: display=true
  (DISPLAY inherited from the gateway process).
- `harness.run desktop app.list` / `ui.observe`: succeed against the live X
  server instead of failing `DISPLAY_STATE_UNAVAILABLE`.
- Portal actions (file dialogs) require an actual D-Bus session in the pod; the
  passthrough only forwards the address when present.

## Notes

- No engine or command-surface change from 3.0.2; only the manifest env
  declaration and version bump.
