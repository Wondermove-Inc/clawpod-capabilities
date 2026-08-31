# Open Design validation evidence

Validated 2026-08-31 against the live self-hosted deployment at the operator-provided Base URL, OpenDesign **v0.20.3**, with the operator's token injected via environment only.

- Offline suite: `python3 tests/test_harness.py` → **12 passed** (fake daemon; no real server).
- Live smoke (operator-approved, including writes): `status`, `config.set`(+insecure-TLS warning), `health` (v0.20.3, `authEnforced:false` correctly detected and reported), `projects.list`, `projects.create`, `files.put` (byte-identical round-trip), `preview.link` (scoped URL verified to open without the API token), `export.html` (681B, saved), `export.archive` (valid ZIP), `export.manifest`, `files.get` (content identical), `projects.delete` (refused without approval; then deleted and absence-verified), `SECRET_IN_ARGV` guard, and token absence from state (`grep` of config.json). Pre-existing projects were left untouched.
- API contract capture (endpoints, shapes, server-side export limits) recorded in `docs/open-design-contract.md`.
