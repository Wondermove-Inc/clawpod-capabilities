# 0.4.1 — post-merge review fixes

- The local scope gate was stricter than Google: `drive`/`drive.file` credentials are accepted by the Docs/Sheets/Slides APIs (per-file visibility enforced by Google for `drive.file`), and `drive.readonly` covers their reads. `enforce()` now mirrors that, so Drive-scoped accounts are no longer blocked locally with a false `INSUFFICIENT_SCOPE`.
- Removed a provably dead clause in the editor-API preflight branch.
