# ClawPod Capability Registry phase 1 test evidence

Phase 1 is additive infrastructure only. No package in the checked-in registry declares `linkedHarness`; existing packages retain legacy standalone semantics. Tests use temporary roots and deterministic payloads without network or live installation.

## Coverage

- Optional typed exact `linkedHarness: {id, version}` metadata.
- Skill and Harness versions may differ; the exact declared Harness version is selected.
- Explicit type selection and same-id ambiguity rejection.
- Transactional linked Skill plus Harness install, update, and validation with explicit roots.
- Digest verification, blocked missing-root installation, and partial-failure rollback.
- Existing standalone Skill/Harness install, validation, update, rollback, and entrypoint behavior.
- Backward-compatible registry generation when no package declares a link.
- Deterministic local list and not-found behavior without canonical-registry network access.

## Commands and results

- `pytest -q harnesses/clawpod-capability-registry/tests tests/test_registry_sync.py tests/test_validator.py` → `21 passed in 0.35s`
- `pytest -q` → `182 passed, 151 subtests passed in 8.91s`
- `python3 scripts/sync_registry.py --check` → synchronized
- `python3 scripts/validate.py` → `OK: validated 6 capability entries`
- trusted-base compatibility: `origin/main:scripts/sync_registry.py --root <candidate> --stdout` byte-compared equal to checked-in `registry/index.json`
- `py_compile`, secret-pattern scan, Registry Harness unsupported-`minLength` scan, and `git diff --check` → passed

## Release state

The Registry Skill and Harness are version `0.2.0`. Their documentation describes the optional pair lifecycle, Gateway validation/trust requirement, and representative bounded `prepare → run` verification. Phase 2 package declarations and the GitHub capability pair are intentionally excluded until phase 1 is merged and trusted validation recognizes the additive metadata.
