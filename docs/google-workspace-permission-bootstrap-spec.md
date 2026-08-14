# Google Workspace credential permission bootstrap specification

Status: implemented 0.3.3 contract

Canonical baseline: `origin/main` at `2cfa36fafbc69dd48751d118247c422686e7f276` (PR #130)

Scope: local permission diagnostics and repair, no credential read, install, publication, or real mutation

## Source-of-truth reproduction

A metadata-only `lstat(2)` reproduction on Forge observed the relevant legacy shape without opening credential files:

| Artifact | Type | Mode | Ownership/link observation |
|---|---|---:|---|
| `/root` process ancestor | directory | `02777` | process-UID-owned with one uniform exact Forge chain GID Forge setgid collaborative boundary |
| `/root/.local` | directory | `02775` | process-UID-owned with one uniform exact Forge chain GID exact intermediate |
| `/root/.local/state` | directory | `02775` | process-UID-owned with one uniform exact Forge chain GID exact intermediate |
| `/root/.local/state/openclaw` | directory | `02775` | process-UID-owned with one uniform exact Forge chain GID exact intermediate |
| protected credential/binding directory | directory | `02770` | current pod user owns it |
| credential file | regular, non-symlink | `0660` | current pod user owns it, link count 1 |

Paths above describe the deployment shape only. Harness output MUST omit paths or replace each with a deterministic request-local opaque artifact identifier. The non-sticky exception applies only to this complete named chain with these exact, unnormalized modes and process UID ownership and one uniform exact Forge chain GID. No generic `02777` or `02775` trust exists. Exact process-owned `01777` is the only generic sticky-parent form accepted; arbitrary other-writable modes, owners, and groups remain forbidden. Intermediates are never repair targets. The protected directory and credential file are insecure because group permission bits remain set.

Current `auth.bindings.status` enters `list_bindings(validate_paths=True)`, which locks/parses the registry, resolves every `credentialRef`, and parses each credential bundle before it can provide useful permission diagnostics. Current repair preview calls `check_permissions`, but returns only repeated artifact categories, silently suppresses registry parse failures, and does not bind its effect digest to exact inode snapshots. Apply re-enumerates names and chmods from a new snapshot, so the preview is not an exact object set.

## Decision

Permission repair is sufficient for the reproduced state when a registry already identifies the credential. Migration is not part of bootstrap and MUST NOT be invoked implicitly. Migration remains necessary only when no binding registry/reference exists after permissions are healthy; it is a separate preview/confirm copy-or-reference operation and must never be coupled to chmod.

## Required behavior

1. `auth.bindings.status`, `auth.bindings.permissions.check`, and repair preview first perform metadata-only discovery. They MUST NOT require alias resolution, credential JSON parsing, readable credential content, or provider access.
2. Discovery is bounded to the configured protected root, its fixed registry/lock/credentials/backups artifacts, and direct children of the two fixed directories. No recursive traversal occurs.
3. Output contains check IDs, current/intended modes, type, repairability, and opaque artifact IDs. It contains no root, credential, or registry path and no file content.
4. Before preview, validate every parent and target with `lstat`: trusted parent chain; containment beneath the lexical and resolved protected root; current effective-user ownership; expected directory or regular-file type; no symlink/reparse point; and link count 1 for files. Unsupported types fail closed.
5. Preview records `(device, inode, type, uid, gid, link count, mode)` for every exact target. The effect digest covers the operation, root identity, ordered opaque target IDs, snapshots, and intended mode changes. It previews `02770 -> 0700` for protected directories and `0660 -> 0600` for files.
6. Confirmation requires a fresh matching digest. Apply reopens/revalidates every target without following links and compares the full snapshot before changing anything. Any owner, inode, type, link-count, containment, or mode race fails closed before the first chmod. A platform without safe no-follow chmod/ACL semantics fails closed.
7. Apply changes mode bits only, to `0700` for directories and `0600` for files. It never creates, copies, deletes, renames, parses, rewrites, or changes ownership/content. It never touches external references or the trusted `/root/.local/state/openclaw` ancestor chain.
8. Apply verifies the post-change inode/type/owner/link count and intended mode. A second preview is an empty plan and a confirmed repeat is a no-op, with no chmod calls.
9. Any owner mismatch, symlink, hardlink, escape, parent-chain race, target race, or unsupported type blocks the entire plan. External references are neither resolved nor targeted. Partial repair is forbidden.
10. `credentials/` and `backups/` are optional. Their absence is a passed, non-applicable observation: it does not fail `parentTrust`, block status or repair preview, or authorize creation. Preview records the opaque absent observations, and confirmation fails closed if either path appears after the snapshot. When the optional registry is absent, status reports binding metadata unavailable without entering registry bootstrap or creating storage.

## Acceptance matrix

| Case | Check/status | Preview | Confirm/apply |
|---|---|---|---|
| complete `02777 -> 02775 -> 02775 -> 02775` exact process-UID-owned with one uniform exact Forge chain GID Forge chain | pass parent trust | ancestors omitted | never changed |
| partial, renamed, or mode-normalized Forge chain | failed, not repairable | fail closed | no mutation |
| owned directory `02770` | insecure, repairable | exact opaque target, `02770 -> 0700` | mode-only repair |
| owned regular file `0660`, nlink 1 | insecure, repairable | exact opaque target, `0660 -> 0600` | mode-only repair |
| credential bytes malformed/unreadable | permission result still returned | preview still returned | bytes never opened or rewritten |
| already `0700`/`0600` | healthy | empty target set | no-op; idempotent |
| alias missing/unresolvable | binding health may be unhealthy | permission preview still works | permission-only result |
| `credentials/` and/or `backups/` absent | passed, non-applicable; parent trust unchanged | no creation effect; absence snapshot-bound | never created; appearance invalidates preview |
| owner mismatch/unknown owner | failed, not repairable | fail closed | no mutation |
| symlink/reparse point | failed, not repairable | fail closed | no mutation |
| regular-file hardlink count >1 | failed, not repairable | fail closed | no mutation |
| FIFO/socket/device/unknown type | failed, not repairable | fail closed | no mutation |
| lexical or resolved protected-root escape | failed, not repairable | fail closed | no mutation |
| external credential reference | not resolved | omitted from plan | never touched |
| parent or target snapshot changes after preview | report stale/race | old digest unusable | fail before first chmod |
| digest differs by target, snapshot, or mode | n/a | new digest | `APPROVAL_REQUIRED` |
| registry absent after healthy repair | permission healthy, binding unavailable | no implicit migration | explicit migration separately required |

## Contract tests

`tests/test_permission_bootstrap_contract.py` fixes the externally observable contract for metadata-only status, exact opaque repair plans, and idempotent mode-only behavior. It covers the exact Forge modes plus symlink, hardlink, parent/target swap, unsafe-mode, owner, containment, rollback, and redaction cases.
