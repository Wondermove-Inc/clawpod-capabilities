# Operations

Use `capabilities` for the complete live inventory. Commands cover existing-session observation, app/window/screen/UI/image observation, pointer/keyboard/clipboard/dialog/file-dialog/download interaction, task plan/preview/run/replay/recovery/cleanup, and owned process termination. Inputs are JSON strings passed with `--input`; output is one `desktop.v3` envelope.

`session.list` and `session.get` observe an existing session. `session.open`, `session.recover`, and `session.close` remain discoverable for contract compatibility, but fail closed with `SESSION_LIFECYCLE_FORBIDDEN`: Desktop never creates, replaces, recovers, or closes the desktop/X session. Display resolution/DPI/scale changes, X resource writes, and X settings writes are structurally forbidden.
