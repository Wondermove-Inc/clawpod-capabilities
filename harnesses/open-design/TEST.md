# Open Design validation evidence

Validated 2026-08-31 against the live self-hosted deployment at the operator-provided Base URL, OpenDesign **v0.20.3**, with the operator's token injected via environment only.

- Offline suite: `python3 tests/test_harness.py` → **12 passed** (fake daemon; no real server).
- Live smoke (operator-approved, including writes): `status`, `config.set`(+insecure-TLS warning), `health` (v0.20.3, `authEnforced:false` correctly detected and reported), `projects.list`, `projects.create`, `files.put` (byte-identical round-trip), `preview.link` (scoped URL verified to open without the API token), `export.html` (681B, saved), `export.archive` (valid ZIP), `export.manifest`, `files.get` (content identical), `projects.delete` (refused without approval; then deleted and absence-verified), `SECRET_IN_ARGV` guard, and token absence from state (`grep` of config.json). Pre-existing projects were left untouched.
- API contract capture (endpoints, shapes, server-side export limits) recorded in `docs/open-design-contract.md`.

## 0.2.0

- Base URL may carry a reverse-proxy path prefix; `preview.link` returns `webUrl` (web origin, prefix-free, for humans) and `apiUrl` (agent base). New tests run the full lifecycle through a `/agent-api`-prefixed fake proxy and verify webUrl/apiUrl composition and the prefix-free default derivation. 15 tests pass offline.

## 0.2.1

- Fixes the 0.2.0 regression where a `mapped` proxy (prefix substitutes `/api`, as on od.wondermove.local) got a double `/api` → 404. `config.set` probes both layouts and stores `apiStyle`; `--api-style` overrides; preview openness is now checked on the human webUrl.
- Offline: 16 tests (mapped-proxy fake E2E incl. path-collapse evidence, explicit override, invalid style).
- Live (od.wondermove.local vhost via resolver override, operator token): auto-detect `mapped`, health `authEnforced:true` (nginx enforces the Bearer token on /agent-api), create → upload (byte-identical) → preview webUrl opens tokenless → export.html → delete. Scratch project removed.
