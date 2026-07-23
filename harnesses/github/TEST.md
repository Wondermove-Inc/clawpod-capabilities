# GitHub capability correction evidence

Validated locally on 2026-07-23 without live GitHub credentials, publication, installation, push, or provider mutations.

## Commands and results

- `pytest -q harnesses/github/tests harnesses/clawpod-capability-registry/tests/test_core.py` → `37 passed in 1.28s`
- `python3 scripts/validate.py && pytest -q` → `OK: validated 8 capability entries`; `208 passed, 151 subtests passed in 10.63s`
- `python3 scripts/sync_registry.py --check` → synchronized
- `python3 -m py_compile harnesses/github/github.py harnesses/clawpod-capability-registry/clawpod_capability_registry.py scripts/sync_registry.py scripts/validate.py` → passed
- secret-pattern scan for GitHub token/Bearer forms → no matches
- registry Harness unsupported `minLength` scan → no matches
- `git diff --check` → passed

## Security/runtime coverage

Synthetic `gh` tests prove that `auth.status` uses only bounded `GET user` argv, never invokes `gh auth status --json hosts`, returns only host/login/authenticated, and compares expected login exactly. Login start/status/cancel are absent. Tests cover validation, bounded endpoints and numerics, timeout, safe read retry, mutation non-retry, redaction, release upload clobber preview, and ambiguous mutation failure.

Registry unit tests cover explicit type disambiguation, linked Skill plus Harness installation and validation, digest failure rollback, missing-root blocking, and standalone compatibility. No live authentication or real backend mutation was attempted.
