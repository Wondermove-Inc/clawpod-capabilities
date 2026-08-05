# Operations and recovery

Canonical mount target is `/workspace/shared`. The Harness fixes `vers=3.1.1,nosuid,nodev,noexec,cache=strict` and pins smbclient minimum and maximum protocol to `SMB3_11`; callers cannot add options or change the target.

Commands include `mount.restore`, the idempotent one-command manual outage recovery path. It accepts server, account, and share; an exact existing mount is a no-op without secret use. Otherwise it performs bounded local prerequisite checks, requires `SYNOLOGY_SMB_PASSWORD`, mounts with the fixed options and target, and verifies the exact CIFS source and target before success. Restore first during repeated outages, then run deeper `layout.inspect` and policy verification.

`auth.onboard` is credential-related and externally visible. Mount, unmount, layout, and policy commands require matching approval. Discovery and mounting use a secret. Onboarding and layout creation are external side effects. Status, preview, and inspect remain read-only. Unmount and WORKFLOW mutations are write-safe.

The current Gateway run path cannot inject protected memory secrets. Run credential-bearing commands through approved `exec.useSecrets` with the pointer injected as `SYNOLOGY_SMB_PASSWORD`; do not resolve plaintext into argv, prompts, files, or reports. Gateway `prepare → run` remains mandatory for non-secret release-gate commands.

The managed WORKFLOW block is versioned and marker-delimited. Installation preserves bytes outside the block, writes atomically, stores a same-directory rollback backup, fails closed on malformed markers, and never changes `AGENTS.md`. Use `workflow.rollback` to restore the exact pre-install bytes.

The Harness intentionally exposes no ordinary file operations. Before any OS-level copy, move, read, write, or listing, verify from the OS mount table that the target is exactly `/workspace/shared`, its filesystem type is `cifs`, and its source is exactly the approved `//<server>/<share>`. A prior successful check is not sufficient after mount state may have changed. Fail closed on mismatch, then constrain ordinary filesystem commands to `/workspace/shared`.

Follow the active approval policy for mutations. Before overwrite, replacement, move, or deletion, inspect the exact source and destination, avoid unresolved variables and broad globs, prefer recoverable handling when practical, and request approval whenever destructive scope or authority is unclear.

On ambiguous discovery, supply a user-selected `--share`. On bad credentials/backend failure, correct access or availability before retrying. On mount conflict, inspect and resolve the existing mount or non-empty target before applying. Do not bypass the fixed mount root or options. Startup hooks, reboot automount, runtime configuration, publication, deployment, restart, and direct live mount/unmount actions are outside recovery scope.
