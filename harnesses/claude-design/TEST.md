# Test contract

Run `pytest -q harnesses/claude-design/tests/test_claude_design.py`.

Coverage includes stable envelopes; browser-first onboarding/auth readiness; minimal human-only authentication; no mandatory MCP registration/OAuth/setup token; optional MCP diagnostics; Claude Code 2.1.229 redirect URI defect; `Connected` not authorized; preserved 56-command parity; exact preview/apply digests; project, design-system, template, code-sync, destination, and admin browser handoffs; exact-name deletion; identifier rejection; local export MIME/bytes/SHA-256; metadata and manifest contracts; and secret-literal exclusion.

No live credentials, provider mutation, publication, MCP registration, OAuth attempt, or browser action occurs in unit tests. Registry sync, repository validation, and a repository secret scan are separate release checks.
