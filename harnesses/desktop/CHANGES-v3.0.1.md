# Desktop 3.0.1

- Makes display geometry, resolution, DPI, scale, X resources, X settings, and desktop/X session lifecycle structurally immutable.
- Rejects known display/session mutation commands and arguments before backend dispatch.
- Preserves all 67 commands. `session.open`, `session.recover`, and `session.close` remain discoverable but explicitly fail closed because their prior implementation only returned synthetic prepared/completed results and could be mistaken for authorization to create, replace, recover, or close a desktop/X session.
- Snapshots display geometry and DPI around every backend call and fails closed with `DESKTOP_STATE_CHANGED` on drift.
- Restricts the synthetic environment matrix from running against an unmarked active display.
