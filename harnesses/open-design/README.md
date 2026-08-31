# Open Design Harness

Canonical `open-design` / **Open Design** Harness. Version 0.2.1. `config.set` auto-detects the proxy's API path style — `root` (prefix + `/api/...`) or `mapped` (prefix substitutes `/api`, the od.wondermove.local layout) — by probing `/api/version` both ways; `--api-style` overrides. `preview.link` verifies openness on the human `webUrl`. The agent-API Base URL may carry a reverse-proxy prefix (e.g. `/agent-api`); a separate `webBaseUrl` (default: the Base URL's origin) builds the human-facing preview links. Unverified TLS is a supported configuration for internal servers via `--insecure-tls-risk-accepted`.

Typed client for a self-hosted OpenDesign daemon (verified against v0.20.3; contract in `docs/open-design-contract.md`). Python standard library only. 16 commands: config/health onboarding, project and file lifecycle, scoped preview links, HTML/ZIP export, export manifest, and Claude Design `.zip` import.

## Contract

One JSON envelope per command: `{ok, schemaVersion, command, data, effects}` with `data.evidence.requests[]` recording every HTTP call (method, path, status, duration, bytes) and whether the token was sent. Errors carry `{code, message, kind, details}`; exit codes: 0 ok · 2 invalid · 3 unreachable · 4 auth · 5 precondition · 6 failed · 7 timeout. **Response data is never truncated**; only diagnostic messages are bounded (512).

Secrets: the API token is read exclusively from the `OPEN_DESIGN_API_TOKEN` environment (Gateway secret lane). A token appearing in argv fails closed (`SECRET_IN_ARGV`); state (`config.json`, 0600 under a 0700 root) holds only the Base URL and TLS trust and rejects secret-like content on load.

Guarantees: `files.put` re-downloads and requires byte-identical content before reporting success; `projects.delete` needs exact displayed name + `--approve` and verifies absence; `health` probes with a deliberately wrong credential to report whether the daemon actually enforces auth; `preview.link` verifies the minted URL opens; base URLs are validated (no path/query/credentials); uploads ≤ 25 MB, responses ≤ 100 MB with a hard error, timeouts bounded.

## Tests

`python3 tests/test_harness.py` — 12 unittest cases against an in-process fake daemon: config lifecycle and permissions, secret guards, auth mapping, enforcement detection both ways, timeout, full create→upload→preview→export→delete lifecycle with a 5,000-character field round-tripping untruncated, corrupted-upload rejection, filename/path validation, Claude Design import. No test touches a real server.
