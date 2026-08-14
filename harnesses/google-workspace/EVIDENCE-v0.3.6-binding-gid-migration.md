# Google Workspace 0.3.6 binding-GID migration evidence

All evidence is local and uses isolated synthetic metadata/credentials. No live credential, provider write, service restart, installation, publication, push, or PR update is performed.

Automated fixtures cover fresh install, already migrated/idempotent state, v0.3.4 modes, distinct process/store GIDs, known credentials/backups/registry/lock/temp/staging artifacts, mixed or foreign ownership refusal, unknown content, symlink/hardlink/type/name refusal, target and parent swaps, stale preview/effect digest, denied `fchown`, partial failure rollback, retry, and stable credential bytes/registry revision/backups/legacy source on failure. Existing import transaction tests cover multiple agent aliases and store GIDs independent of process EGID/supplementary groups.

The final local commands and exact results are recorded in `tests/TEST.md` and the commit handoff. Synthetic numeric-GID rows may skip where the sandbox user namespace cannot represent those GIDs; descriptor-level ownership failure and rollback coverage remains active. Live Forge captain/GID verification is an environment-only remaining step and is not claimed or faked here.
