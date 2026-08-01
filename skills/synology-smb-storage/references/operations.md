# Operations and recovery

Canonical mount target is `/workspace/shared`. The Harness fixes `vers=3.1.1,nosuid,nodev,noexec,cache=strict` and pins smbclient minimum and maximum protocol to `SMB3_11`; callers cannot add options or change the target.

Commands: `system.preflight`, `auth.contract`, `auth.onboard`, `shares.discover`, `mount.preview`, `mount.apply`, `mount.status`, `mount.unmount`, `layout.inspect`, `layout.ensure`, `file.list`, `file.get`, `file.put`, `workflow.install`, `workflow.rollback`.

`auth.onboard` is credential-related and externally visible. Mount, unmount, layout, file put, and policy commands require matching write approval. Discovery and mounting use a secret. Onboarding is an external side effect. Layout creation and file put are external side effects. Status, preview, inspect, list, and get remain read-only. Unmount and WORKFLOW mutations are write-safe.

The current Gateway run path cannot inject protected memory secrets. Run credential-bearing commands through approved `exec.useSecrets` with the pointer injected as `SYNOLOGY_SMB_PASSWORD`; do not resolve plaintext into argv, prompts, files, or reports. Gateway `prepare → run` remains mandatory for non-secret release-gate commands.

The managed WORKFLOW block is versioned and marker-delimited. Installation preserves bytes outside the block, writes atomically, stores a same-directory rollback backup, fails closed on malformed markers, and never changes `AGENTS.md`. Use `workflow.rollback` to restore the exact pre-install bytes.

File transfers default to 16 MiB and accept an explicit maximum no greater than 64 MiB. `file.put` requires an absolute, trusted `transferRoot` and a source relative to that root; traversal and symlinks are rejected. `file.list` reports symlinks without following them.

On ambiguous discovery, supply a user-selected `--share`. On bad credentials/backend failure, correct access or availability before retrying. On mount conflict, inspect and resolve the existing mount or non-empty target before applying. Do not bypass the fixed mount root or options.
