# Synology SMB Storage contract

Registry-first classification: **REFINE**. Canonical search found exactly this existing Skill and linked Harness, with no competing capability.

Version 0.1.3 keeps the bounded, idempotent `mount.restore` recovery path and removes `file.list`, `file.get`, and `file.put`. The Harness is now control-plane only: credentials, discovery, mount lifecycle and recovery, status, layout, and WORKFLOW policy remain guarded commands.

Repeated outages restore first, then perform deeper layout and policy verification. The refinement excludes startup hooks, automatic reboot mounting, runtime configuration, publication, deployment, restart, and direct live mount/unmount actions.

The Harness wraps installed `smbclient` and `mount.cifs`, requires exact SMB 3.1.1, fixes the target at `/workspace/shared`, and exposes no arbitrary command, target, dialect, or mount-option input. Passwords enter the Harness only through `SYNOLOGY_SMB_PASSWORD` or stdin. Child tools receive them only through `PASSWD`; inherited `SYNOLOGY_SMB_PASSWORD` is removed, stdin is `/dev/null`, and backend stdout/stderr are not surfaced. Secrets are excluded from argv, files, logs, and JSON output.

Because the current Gateway run lane cannot inject protected memory secrets, credential-bearing commands use approved `exec.useSecrets` injection as `SYNOLOGY_SMB_PASSWORD`. Non-secret commands continue through Gateway `prepare → run` for validation and normal invocation.

Post-install state is installed but not connected. Onboarding asks only for NAS address, account, and password, then performs bounded preflight, share discovery, mount, layout creation, and explicit transactional WORKFLOW policy installation after approval. An ambiguous share list requires user selection. If post-mount onboarding fails, the Harness restores changed WORKFLOW bytes, removes only newly created empty layout directories, and unmounts only the mount created by that invocation, returning rollback evidence.

The managed policy preserves unrelated WORKFLOW bytes, rejects malformed markers before mutation, keeps an exact rollback backup, and does not modify AGENTS.md. Durable artifacts belong in `/workspace/shared/common`, `/workspace/shared/<org-id>/common`, or `/workspace/shared/<org-id>/<agent-id>`. Scratch, cache, builds, Git, and SQLite remain local. Ordinary copy, move, read, write, and listing use OS filesystem commands only after verifying that `/workspace/shared` is a CIFS mount from the exact approved `//server/share`. Mutations follow approval policy, with explicit caution for overwrite, replacement, move, and deletion.
