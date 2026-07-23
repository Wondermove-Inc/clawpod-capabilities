# GitHub capability final correction evidence

Validated locally on 2026-07-23 without live GitHub credential use, installation, or provider mutations. Publication lifecycle actions were performed separately only after explicit approval.

## Commands and results

- `pytest -q harnesses/github/tests harnesses/clawpod-capability-registry/tests tests/test_registry_sync.py` → `45 passed in 1.54s`
- `pytest -q` → `210 passed, 151 subtests passed in 10.30s`
- `python3 scripts/sync_registry.py --check` → synchronized
- `python3 scripts/validate.py` → `OK: validated 8 capability entries`
- `python3 -m py_compile harnesses/github/github.py harnesses/github/scripts/generate_schemas.py harnesses/clawpod-capability-registry/clawpod_capability_registry.py scripts/sync_registry.py scripts/validate.py` → passed
- secret-pattern scan for GitHub token/Bearer forms → no matches
- registry Harness unsupported `minLength` scan → no matches
- `git diff --check` → passed

## GitHub security/runtime coverage

Synthetic `gh` tests prove that `auth.status` uses only bounded `GET user` argv, never invokes `gh auth status --json hosts`, emits only host/login/authenticated, compares expected login exactly, and is classified `secretUse` plus `readOnly`. Login start/status/cancel remain absent.

Tests cover command-specific state validation (`issue.list` rejects `merged`), IDs, hosts, endpoints, sizes, timeout, bounded output, safe read retry, mutation non-retry, redaction, release upload clobber preview, and stable mutation errors. Pre-backend validation/confirmation failures report `ambiguousCommit:false`; failures and timeouts after the mutation subprocess starts report `ambiguousCommit:true`.

GitHub packages declare Linux and macOS only because bounded output currently relies on POSIX `resource`/`preexec_fn`; Windows remains unsupported in v0.1.

## Registry coverage

Every currently paired Skill declares typed exact linked Harness metadata `{id, version}`. Linked versions are independently selected rather than inferred from the Skill version. The registry capability pair is version `0.2.0`; its Skill links the exact Registry Harness `0.2.0`. Tests cover differing Skill/Harness versions, explicit type selection, transactional paired install/update/validation, digest verification, partial rollback, missing-root blocking, and standalone compatibility.

No real registry fetch, authentication, Gateway install/trust change, or backend mutation was attempted during local validation. Canonical CI independently validates registry synchronization, package schemas, tests, and trusted-candidate generation before merge.
