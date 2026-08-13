# Test contract

Run `pytest -q harnesses/claude-design/tests/test_claude_design.py`.

Coverage includes stable envelopes; browser-first onboarding/auth readiness; minimal human-only authentication; no mandatory MCP registration/OAuth/setup token; optional MCP diagnostics; Claude Code 2.1.229 redirect URI defect; `Connected` not authorized; preserved 59-command parity; exact short/long browser input routing; inert JSON encoding of quotes, newlines, Unicode, and markup; fail-closed evaluate-disabled behavior; exact readback verification; stale-ref and timeout diagnosis without automatic Gateway restart; exact preview/apply digests; project, design-system, template, code-sync, destination, and admin browser handoffs; exact-name deletion; identifier rejection; native PDF route discovery; expected full-deck page count; artifact metadata; explicit native/fallback provenance; page-by-page visual QA; metadata and manifest contracts; and secret-literal exclusion.

No live credentials, provider mutation, publication, MCP registration, OAuth attempt, or browser action occurs in unit tests. Registry sync, repository validation, and a repository secret scan are separate release checks.
