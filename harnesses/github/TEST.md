# GitHub Harness Test Plan

Written before implementation.

## Inventory

- `tests/test_github.py`: approximately 25 unit and fake-`gh` subprocess E2E tests.
- Repository validation, registry determinism, secret-pattern scan, and whitespace checks.

## Planned coverage

- Command catalog and `gh` argv mapping for repository, issue, pull request, workflow run, release, and bounded API GET operations.
- Stable JSON success/error envelopes and stderr-only diagnostics.
- Required input and malformed repository/API endpoint rejection.
- Missing backend, backend nonzero exit, timeout, bounded retry on rate limiting, and no retry for mutations.
- Read-only versus mutation preview/confirmation behavior, destructive classifications, and idempotency-key validation.
- Redaction of token-like values from backend output and errors.
- Auth states: disconnected, wrong host/account, connected, asynchronous login start/status/cancel, and fail-closed expected identity checks.
- Installed-entrypoint-style execution from outside the package directory using the executable file.
- Release upload path handling without embedding file contents or credentials in argv.
- Manifest runtime numeric schema uses `number`; contract schemas may use `integer`.

## Safe backend strategy

Tests place a fake `gh` executable first on `PATH`; no credentials or network are used. A future approval-gated real-backend check should run `auth.status`, `repo.view`, and one bounded `issue.list` against an explicitly approved repository and expected account, then use mutation previews only unless separate action approval is granted.

## Results

Executed 2026-07-23 in the isolated worktree with no live credentials or network.

- `python3 -m pytest harnesses/github/tests -q`: `25 passed in 1.24s`.
- `python3 scripts/sync_registry.py`: updated generated registry after final package changes.
- `python3 scripts/sync_registry.py --check`: synchronized.
- `python3 scripts/validate.py`: `OK: validated 8 capability entries`.
- `python3 -m pytest -q`: `203 passed, 151 subtests passed in 10.24s`.
- Secret-pattern scan over tracked/new source: no credential-shaped literals detected.
- `git diff --check`: clean.

Coverage uses a fake `gh` subprocess and installed-entrypoint-style executable invocation from `/tmp`. It verifies 25 cases including all read domains, mutation preview/confirmation, non-retry of writes, idempotent replay, bounded read retry, timeout, missing/failing backend, validation, redaction, exact-account failure, asynchronous authorization, manifest safety, runtime `number`, and contract `integer` schemas. Live provider behavior remains intentionally untested pending separate credential-use and network approval.
