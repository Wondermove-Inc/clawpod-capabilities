# Google Workspace 0.3.6 binding-store GID migration

This patch extends the existing `auth.bindings.permissions.repair` preview/confirm contract to migrate v0.3.4 binding-store metadata safely when the agent process GID differs from the protected store GID.

- Expected UID/GID is derived only from exact verified protected parent/root snapshots; process EGID and supplementary groups are not trusted.
- Discovery is bounded to the root, `credentials/`, `backups/`, registry, lock, and strict credential, backup, registry-temp, and credential-tombstone name grammars. Unknown content is rejected and never traversed.
- Only process-UID-owned contained real directories and single-link regular files are repairable. Symlinks, foreign UIDs, unexpected hardlinks/types/names, and unstable parent/name/inode snapshots fail closed.
- Preview binds exact before snapshots, intended UID/GID/modes, absent artifacts, and root/parent identity into the existing effect digest. Apply opens every target no-follow before mutation and uses descriptor-bound `fchown`/`fchmod`.
- Partial apply performs best-effort descriptor-bound ownership/mode rollback. Successful repair is idempotent; failed/retried repair does not read or rewrite credential content, change registry revision/backups, delete legacy sources, create an absent store, or touch provider data.
