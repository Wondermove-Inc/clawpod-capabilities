# Test contract

Run:

```text
python3 -m pytest -q harnesses/verified-research/tests/test_verified_research.py
python3 -m pytest -q
python3 harnesses/verified-research/scripts/generate_schemas.py
python3 scripts/sync_registry.py --check
python3 scripts/validate.py
python3 -m py_compile harnesses/verified-research/verified_research.py harnesses/verified-research/scripts/generate_schemas.py
git diff --check
```

The focused suite covers exact-byte snapshot tampering, metadata and date candidates, claim structure, quote/line integrity, Gateway root-path versus relative-child string contracts, CLI execution with absolute roots and nested relative child names, incomplete root/name pairs, path and overwrite safety, input/output bounds, optional PDF backend limits, SSRF and redirect rejection, compressed and oversized HTTP responses, offline imports, partial-failure exits, sanitized internal errors, and deterministic output excluding `requestId`. No Node subtests exist in this repository.

It also enforces the version 0.1.6 connected-unit contract and deterministic Tavily documentation: recommended-backend routing, five bounded tool roles, installed-versus-connected onboarding, schema plus low-cost search verification, degraded and rollback behavior, approval-gated restart/removal, rate/cost limits, environment interpolation, and rejection of likely Tavily key literals. These are hermetic documentation tests; they never register MCP, resolve a secret, restart Gateway, or make a live Tavily call.

For release evidence only, an approved onboarding operator may run `mcporter list tavily --schema`, followed by one `tavily_search` with `max_results=1`, `search_depth=basic`, `include_raw_content=false`, and `include_images=false`. Do not capture the response body in committed artifacts. If protected credentials are unavailable, record the bounded smoke as credential-blocked rather than weakening the hermetic suite.
