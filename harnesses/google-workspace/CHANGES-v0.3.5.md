# Google Workspace 0.3.5 corrective change

This patch fixes protected binding imports when the runtime process default GID differs from the trusted protected-store GID, including the Forge GID 1000 layout.

- Protected directories and credential, lock, registry, backup, and temporary files are created through no-follow directory/file descriptors.
- New artifacts receive explicit store-GID ownership and strict `0700`/`0600` modes before use.
- Creation verifies regular/directory type, single-link files, containment, inode identity, size, and stable parent snapshots.
- Failed chown, write, fsync, replacement, or post-create checks clean uncommitted temporary credentials and backups. Registry revisions advance only through the existing durable replacement commit boundary.
- Import continues to copy from, never rename or delete, the legacy source.
- Exact `/root/.local/state/openclaw/google-workspace` and immediate `/workspace/<private-root>` trust exceptions and all provider command semantics are unchanged.
