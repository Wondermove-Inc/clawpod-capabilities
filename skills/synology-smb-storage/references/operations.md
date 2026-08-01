# Operations and recovery

Canonical mount target is `/workspace/shared`. The Harness fixes `vers=3.0,nosuid,nodev,noexec,cache=strict`; callers cannot add options or change the target.

Commands: `system.preflight`, `auth.contract`, `auth.onboard`, `shares.discover`, `mount.preview`, `mount.apply`, `mount.status`, `mount.unmount`, `layout.inspect`, `layout.ensure`, `file.list`, `file.get`, `file.put`, `workflow.install`, `workflow.rollback`.

`auth.onboard` is credential-related and externally visible. Mount, unmount, layout, file put, and policy commands require matching write approval. Read-only status, preview, inspect, list, and get do not.

The managed WORKFLOW block is versioned and marker-delimited. Installation preserves bytes outside the block, writes atomically, stores a same-directory rollback backup, fails closed on malformed markers, and never changes `AGENTS.md`. Use `workflow.rollback` to restore the exact pre-install bytes.

On ambiguous discovery, supply a user-selected `--share`. On bad credentials/backend failure, correct access or availability before retrying. On mount conflict, inspect and resolve the existing mount or non-empty target before applying. Do not bypass the fixed mount root or options.