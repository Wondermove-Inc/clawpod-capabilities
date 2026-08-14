# Google Workspace credential permission bootstrap specification

Status: implementation contract and red tests only

Canonical baseline: `origin/main` at `2cfa36fafbc69dd48751d118247c422686e7f276` (PR #130)

Scope: local permission diagnostics and repair, no credential read, install, publication, or real mutation

## Source-of-truth reproduction

A metadata-only `lstat(2)` reproduction on Forge observed the relevant legacy shape without opening credential files:

| Artifact | Type | Mode | Ownership/link observation |
|---|---|---:|---|
| `/workspace` ancestor | directory | `02777` | trusted collaborative setgid/sticky boundary |
| protected credential/binding directory | directory | `02770` | current pod user owns it |
| credential file | regular, non-symlink | `0660` | current pod user owns it, link count 1 |

Paths above describe the deployment shape only. Harness output MUST omit paths or replace each with a deterministic request-local opaque artifact identifier. The `02777` ancestor is accepted only by the existing exact Forge parent exception. It is never a repair target. The protected directory and credential file are insecure because group permission bits remain set.

Current `auth.bindings.status` enters `list_bindings(validate_paths=True)`, which locks/parses the registry, resolves every `credentialRef`, and parses each credential bundle before it can provide useful permission diagnostics. Current repair preview calls `check_permissions`, but returns only repeated artifact categories, silently suppresses registry parse failures, and does not bind its effect digest to exact inode snapshots. Apply re-enumerates names and chmods from a new snapshot, so the preview is not an exact object set.

## Decision

Permission repair is sufficient for the reproduced state when a registry already identifies the credential. Migration is not part of bootstrap and MUST NOT be invoked implicitly. Migration remains necessary only when no binding registry/reference exists after permissions are healthy; it is a separate preview/confirm copy-or-reference operation and must never be coupled to chmod.

## Required behavior

1. `auth.bindings.status`, `auth.bindings.permissions.check`, and repair preview first perform metadata-only discovery. They MUST NOT require alias resolution, credential JSON parsing, readable credential content, or provider access.
2. Discovery is bounded to the configured protected root, its fixed registry/lock/credentials/backups artifacts, and direct children of the two fixed directories. No recursive traversal occurs.
3. Output contains check IDs, current/intended modes, type, repairability, and opaque artifact IDs. It contains no root, credential, or registry path and no file content.
4. Before preview, validate every parent and target with `lstat`: trusted parent chain; containment beneath the lexical and resolved protected root; current effective-user ownership; expected directory or regular-file type; no symlink/reparse point; and link count 1 for files. Unsupported types fail closed.
5. Preview records `(device, inode, type, uid, link count, mode)` for every exact target. The effect digest covers the operation, root identity, ordered opaque target IDs, snapshots, and intended mode changes. It previews `02770 -> 0700` for protected directories and `0660 -> 0600` for files.
6. Confirmation requires a fresh matching digest. Apply reopens/revalidates every target without following links and compares the full snapshot before changing anything. Any owner, inode, type, link-count, containment, or mode race fails closed before the first chmod. A platform without safe no-follow chmod/ACL semantics fails closed.
7. Apply changes mode bits only, to `0700` for directories and `0600` for files. It never creates, copies, deletes, renames, parses, rewrites, or changes ownership/content. It never touches external references or the trusted `/workspace` ancestor.
8. Apply verifies the post-change inode/type/owner/link count and intended mode. A second preview is an empty plan and a confirmed repeat is a no-op, with no chmod calls.
9. Any owner mismatch, symlink, hardlink, escape, parent-chain race, target race, unsupported type, or external reference blocks the entire plan. Partial repair is forbidden.

## Acceptance matrix

| Case | Check/status | Preview | Confirm/apply |
|---|---|---|---|
| `02777` exact trusted Forge ancestor | pass parent trust | ancestor omitted | never changed |
| owned directory `02770` | insecure, repairable | exact opaque target, `02770 -> 0700` | mode-only repair |
| owned regular file `0660`, nlink 1 | insecure, repairable | exact opaque target, `0660 -> 0600` | mode-only repair |
| credential bytes malformed/unreadable | permission result still returned | preview still returned | bytes never opened or rewritten |
| already `0700`/`0600` | healthy | empty target set | no-op; idempotent |
| alias missing/unresolvable | binding health may be unhealthy | permission preview still works | permission-only result |
| owner mismatch/unknown owner | failed, not repairable | fail closed | no mutation |
| symlink/reparse point | failed, not repairable | fail closed | no mutation |
| regular-file hardlink count >1 | failed, not repairable | fail closed | no mutation |
| FIFO/socket/device/unknown type | failed, not repairable | fail closed | no mutation |
| lexical or resolved escape/external ref | failed, not repairable | fail closed | no mutation |
| parent or target snapshot changes after preview | report stale/race | old digest unusable | fail before first chmod |
| digest differs by target, snapshot, or mode | n/a | new digest | `APPROVAL_REQUIRED` |
| registry absent after healthy repair | permission healthy, binding unavailable | no implicit migration | explicit migration separately required |

## Red tests added

`tests/test_permission_bootstrap_contract.py` fixes the externally observable contract for metadata-only status, exact opaque repair plans, and idempotent mode-only behavior. On this baseline, the new contract tests fail because status does not include permission diagnostics and repair plans do not enumerate exact snapshot-bound changes. Existing symlink, hardlink, parent escape/race, and redaction tests remain the passing safety baseline.
