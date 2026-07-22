# Google Workspace harness test plan

All automated tests use `.invalid` identities, isolated temporary state, and scripted HTTP. They never load production credentials or call Google.

Desktop OAuth coverage includes loopback success, denied consent, missing refresh token, state mismatch, duplicate callback rejection, timeout, bind failure, token/identity/scope errors, malformed or non-private client files, private atomic output, overwrite refusal, alias collision and merge, traversal/symlink rejection, secret redaction, URL encoding, PKCE S256 correctness, repeat invocation, and browser fallback. Release run: `PYTHONPATH=harnesses/google-workspace pytest -q`, 111 passed plus 151 command subtests.

## Inventory

- `test_google_workspace.py`: 35 unit and subprocess contract tests.
- `test_adversarial_contract.py`: 11 exhaustive/adversarial tests.
- Repository registry suite: 20 synchronization and lifecycle tests.

## Covered contracts

- exhaustive 151-command HTTPS resolution, closed command-specific schemas, required resource identifiers, and non-empty exact scope declarations
- subprocess discovery, one-object JSON output, status taxonomy, and authentication-before-preview behavior
- persisted account/command/input/target/ETag-bound one-use previews, stale/replay rejection, and 10-minute expiry implementation
- bounded automatic pagination and account/command/query-bound continuation tokens
- durable idempotency conflict/replay paths and per-item batch partial-result envelopes
- scripted provider failures, unsafe retry suppression, MIME/header defense, time-zone/recurrence validation, traversal/symlink rejection, and secret redaction
- dependency-free Drive media/multipart/resumable upload request paths, binary download/export, range resume, atomic writes, and SHA-256 verification

## Required protected E2E before release

Manual protected E2E remains mandatory: incremental OAuth consent, refresh/revocation, controlled Gmail draft/send, dedicated Calendar CRUD, isolated Drive simple/multipart/resumable transfer and range resume, share/revoke, and receiver channel lifecycle. Permanent delete, transfer ownership, and admin sharing require separate approval. Scripted tests prove the harness contract, not live provider acceptance.
