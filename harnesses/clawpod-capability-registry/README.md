# ClawPod Capability Registry Harness

This Harness searches, inspects, installs, updates, validates, and rolls back packages from the canonical `Wondermove-Inc/clawpod-capabilities` registry.

## Type selection

`inspect`, `install`, `update`, and `validate` accept optional `--type skill|harness`.

- Omit `--type` only when the requested id/version identifies one registry entry.
- If both a Skill and Harness share the requested id/version, selection fails with `ambiguous_type`; rerun with an explicit type.
- `--target-root` is routed according to the selected registry entry type. Linked Skill/Harness units still require explicit `--skills-root` and `--harnesses-root`.
- Install and validation evidence includes the selected `type`, exact `version`, and resolved destination. Installed provenance also records canonical repository, type, source path, and file digests.

Package writes remain approval-bound. Selection or installation does not authorize capability invocation, credentials, external side effects, or production changes.
