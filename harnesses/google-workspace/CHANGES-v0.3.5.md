# Google Workspace 0.3.5 corrective change

This patch fixes protected binding imports for every agent when the runtime process default GID differs from the trusted protected-store GID. Numeric GID 1000 has no special meaning.

- Protected directories and credential, lock, registry, backup, and temporary files are created through no-follow directory/file descriptors.
- Trusted UID/GID comes only from the exact verified protected store or its exact verified parent snapshot; process EGID and supplementary groups are never ownership fallbacks.
- New artifacts receive explicit descriptor-bound store ownership and strict `0700`/`0600` modes before use. Missing or denied `fchown` fails closed.
- Creation verifies regular/directory type, single-link files, containment, inode identity, size, and stable parent snapshots.
- Failed chown, write, fsync, replacement, or post-create checks clean uncommitted temporary credentials and backups. Registry revisions advance only through the existing durable replacement commit boundary.
- Import continues to copy from, never rename or delete, the legacy source.
- The platform-governed exact `/root/.local/state/openclaw/google-workspace` and immediate `/workspace/<private-root>` ancestor rules and all provider command semantics are unchanged.
