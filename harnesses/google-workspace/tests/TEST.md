# Google Workspace harness test plan

All automated tests use `.invalid` identities, isolated temporary state, and scripted HTTP. They never load production credentials or call Google.

Desktop OAuth coverage includes loopback success, denied consent, missing refresh token, state mismatch, duplicate callback rejection, timeout, bind failure, token/identity/scope errors, malformed or absent client files, atomic output, overwrite refusal, alias collision and merge, traversal rejection and linked-file acceptance, secret redaction, URL encoding, PKCE S256 correctness, repeat invocation, and browser fallback. The command inventory contains 162 commands (the 152-command compatibility baseline plus 10 refine commands).

## Inventory

- `test_google_workspace.py`: 35 unit and subprocess contract tests.
- `test_adversarial_contract.py`: 11 exhaustive/adversarial tests.
- Repository registry suite: 20 synchronization and lifecycle tests.

## Covered contracts

- exhaustive 162-command contract coverage, including 147 provider HTTPS operations, closed command-specific schemas, required resource identifiers, and non-empty exact scope declarations
- subprocess discovery, one-object JSON output, status taxonomy, and authentication-before-preview behavior
- persisted account/command/input/target/ETag-bound one-use previews, stale/replay rejection, and 10-minute expiry implementation
- bounded automatic pagination and account/command/query-bound continuation tokens
- live installed-Gateway prepare→run coverage for integer `pageSize=10`, JSON-string provider params, Gmail/Calendar `maxResults`, Drive `pageSize`, fractional/type rejection, and harness limit enforcement, all over scripted HTTP only; exact copied-install Gmail/Calendar/Drive prepare→run failures also assert repeated credential-free invocations preserve the absent registry/lock/credentials/backups tree byte-for-byte and stat-for-stat
- OAuth and binding files with varied modes, ownership metadata, and link shapes do not fail readiness solely for that metadata; missing and malformed files still fail.
- durable idempotency conflict/replay paths and per-item batch partial-result envelopes
- scripted provider failures, unsafe retry suppression, MIME/header defense, time-zone/recurrence validation, traversal rejection and linked-file acceptance, and secret redaction
- dependency-free Drive media/multipart/resumable upload request paths, binary download/export, range resume, atomic writes, and SHA-256 verification

## v0.3.7 local validation

- `PYTHONPATH=harnesses/google-workspace python3 -m pytest -q harnesses/google-workspace/tests`: 127 passed, 162 subtests passed.
- Source-first suite excluding the loopback module: 112 passed, 162 subtests passed.
- `python3 -m pytest -q tests/test_version_integrity.py tests/test_release_version_integrity.py tests/test_registry_sync.py tests/test_gateway_harness_manifests.py`: 22 passed, 40 subtests passed.
- `python3 scripts/sync_registry.py --check` and `python3 scripts/validate.py`: synchronized; all 43 capability entries valid.

## Required protected E2E before release

Manual protected E2E remains mandatory: incremental OAuth consent, refresh/revocation, controlled Gmail draft/send, dedicated Calendar CRUD, isolated Drive simple/multipart/resumable transfer and range resume, share/revoke, and receiver channel lifecycle. Permanent delete, transfer ownership, and admin sharing require separate approval. Scripted tests prove the harness contract, not live provider acceptance.
