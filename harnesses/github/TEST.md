# GitHub capability validation evidence

Validated locally on 2026-08-01 without live GitHub credential use, installation, or provider mutations. Publication lifecycle actions are outside this validation and require separate explicit approval.

The `release.body.update` tests use a local synthetic `gh` executable and a release fixture only. They assert exact-tag inspection, dry-run without PATCH, a single numeric-id PATCH whose stdin object has only the `body` key, independent numeric-id GET readback, exact body verification, protected metadata and complete asset invariants, fail-closed mismatch handling, and mutation non-retry. No test contacts GitHub or changes a real release.

## Commands and results

- `pytest -q harnesses/github/tests harnesses/clawpod-capability-registry/tests tests/test_registry_sync.py` → `67 passed`
- `pytest -q` → collection stopped on two duplicate-module-name errors in the unrelated `clawpod-cloud-webhooks` and `clawpod-capability-registry` test trees; the same two errors reproduce on clean `origin/main` (`fb8bbc6`), so this is a baseline-only full-suite collection issue
- `python3 scripts/sync_registry.py --check` → synchronized
- `python3 scripts/validate.py` → `OK: validated 16 capability entries`
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
