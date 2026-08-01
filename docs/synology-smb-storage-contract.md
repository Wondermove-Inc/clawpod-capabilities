# Synology SMB Storage contract

Registry-first classification: **create**. The installed and canonical registry inventory contained no Synology/SMB storage capability with this backend and policy boundary.

Version 0.1.0 pairs the `synology-smb-storage` AgentSkill and CLI Harness under the title **Synology SMB Storage**.

The Harness wraps installed `smbclient` and `mount.cifs`, requires exact SMB 3.1.1, fixes the target at `/workspace/shared`, and exposes no arbitrary command, target, dialect, or mount-option input. Passwords enter the Harness only through `SYNOLOGY_SMB_PASSWORD` or stdin. Child tools receive them only through `PASSWD`; inherited `SYNOLOGY_SMB_PASSWORD` is removed, stdin is `/dev/null`, and backend stdout/stderr are not surfaced. Secrets are excluded from argv, files, logs, and JSON output.

Post-install state is installed but not connected. Onboarding asks only for NAS address, account, and password, then performs bounded preflight, share discovery, mount, layout creation, and explicit transactional WORKFLOW policy installation after approval. An ambiguous share list requires user selection. If post-mount onboarding fails, the Harness restores changed WORKFLOW bytes, removes only newly created empty layout directories, and unmounts only the mount created by that invocation, returning rollback evidence.

The managed policy preserves unrelated WORKFLOW bytes, rejects malformed markers before mutation, keeps an exact rollback backup, and does not modify AGENTS.md. Durable artifacts belong in `/workspace/shared/common`, `/workspace/shared/<org-id>/common`, or `/workspace/shared/<org-id>/<agent-id>`. Scratch, cache, builds, Git, and SQLite remain local. File get/put defaults to 16 MiB and is capped at 64 MiB. Put sources must be relative to an explicit trusted transfer root; traversal and symlinks are rejected.
