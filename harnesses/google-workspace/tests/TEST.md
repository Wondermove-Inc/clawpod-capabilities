# Google Workspace harness test plan

All automated tests use `.invalid` identities, isolated temporary state, and scripted HTTP. They never load production credentials or call Google.

Desktop OAuth coverage includes loopback success, denied consent, missing refresh token, state mismatch, duplicate callback rejection, timeout, bind failure, token/identity/scope errors, malformed or non-private client files, private atomic output, overwrite refusal, alias collision and merge, traversal/symlink rejection, secret redaction, URL encoding, PKCE S256 correctness, repeat invocation, and browser fallback. The command inventory contains 164 commands (the 152-command compatibility baseline plus 12 refine commands).

## Inventory

- `test_google_workspace.py`: 35 unit and subprocess contract tests.
- `test_adversarial_contract.py`: 11 exhaustive/adversarial tests.
- Repository registry suite: 20 synchronization and lifecycle tests.

## Covered contracts

- exhaustive 164-command contract coverage, including 147 provider HTTPS operations, closed command-specific schemas, required resource identifiers, and non-empty exact scope declarations
- subprocess discovery, one-object JSON output, status taxonomy, and authentication-before-preview behavior
- persisted account/command/input/target/ETag-bound one-use previews, stale/replay rejection, and 10-minute expiry implementation
- bounded automatic pagination and account/command/query-bound continuation tokens
- live installed-Gateway prepare→run coverage for integer `pageSize=10`, JSON-string provider params, Gmail/Calendar `maxResults`, Drive `pageSize`, fractional/type rejection, and harness limit enforcement, all over scripted HTTP only; exact copied-install Gmail/Calendar/Drive prepare→run failures also assert repeated credential-free invocations preserve the absent registry/lock/credentials/backups tree byte-for-byte and stat-for-stat
- exact Forge `02777/02775/02775/02775/02770` binding-root-chain compatibility across binding inspection and Gmail/Calendar/Drive alias reads, while preserving foreign UID/GID, partial-chain, symlink, hardlink, non-sticky shared-parent, containment, and parent-race rejection
- permission-first bootstrap status and snapshot-bound preview/confirm repair for legacy mode-02770 directories and mode-0660 files, including metadata-only redaction, idempotency, owner/type/link/containment rejection, stale parent/target races, and backend rollback
- durable idempotency conflict/replay paths and per-item batch partial-result envelopes
- scripted provider failures, unsafe retry suppression, MIME/header defense, time-zone/recurrence validation, traversal/symlink rejection, and secret redaction
- dependency-free Drive media/multipart/resumable upload request paths, binary download/export, range resume, atomic writes, and SHA-256 verification

## Required protected E2E before release

Manual protected E2E remains mandatory: incremental OAuth consent, refresh/revocation, controlled Gmail draft/send, dedicated Calendar CRUD, isolated Drive simple/multipart/resumable transfer and range resume, share/revoke, and receiver channel lifecycle. Permanent delete, transfer ownership, and admin sharing require separate approval. Scripted tests prove the harness contract, not live provider acceptance.
