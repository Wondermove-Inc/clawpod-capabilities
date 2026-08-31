# Test plan and evidence

Planned fixture tests cover credential providers, recursive redaction, transfer-root confinement, fresh request-bound confirmations, dry-run, tenant isolation, rate-limit retry, timeouts and ambiguous mutation commits, stable partial-failure errors, command inventory, and real CLI subprocess behavior. No test accesses Atlassian Cloud.

Run `pytest -q harnesses/atlassian/tests` and `python scripts/validate.py`. Final results are recorded in the implementation commit report.

## 0.3.5

- `redact()` split into masking (unbounded, applied to all response data including paginated results) and `diagnostic()` (masked + 512-char bound, error messages only). New tests prove a 5000-char field and a 4096-char response field round-trip intact through `execute`, paginated items are masked, and diagnostics stay bounded.
- Repaired two stale pre-existing tests: `test_secretrefs_metadata_contract` pinned version 0.3.1 (failing since 0.3.2), and the suite was never collected by CI (pytest-style; CI runs unittest discover). Run locally: 37 passed, 1 skipped (capsys).
