---
name: synology-smb-storage
description: Connect Synology SMB 3.1.1 shared storage, enforce its durable-artifact layout, and operate files through a guarded typed harness.
---

# Synology SMB Storage

Use the linked `synology-smb-storage` Harness. Do not construct `smbclient`, `mount.cifs`, or shell commands manually.

## Post-install handoff

Immediately state that the capability is installed but not connected. Ask only for:

1. NAS address
2. Account
3. Password

Explain that the password goes directly to protected secret storage, enters the Harness through protected environment or stdin injection and reaches backend tools only through their `PASSWD` environment, is never echoed or written to files, and can be revoked by deleting that protected secret. Obtain explicit approval before authentication, mounting, or WORKFLOW mutation. The agent then handles preflight, share discovery, unambiguous selection, SMB 3.1.1 mount, layout creation, and policy installation. If deferred, record connection authorization as pending and resume with `auth.onboard`.

## Procedure

1. Run `system.preflight` and `auth.contract`.
2. Route the password to approved protected storage. Never place it in prompts, argv, files, logs, artifacts, examples, or output.
3. Invoke `auth.onboard` with password environment/stdin injection. Auto-select a share only when discovery returns exactly one eligible disk share. Otherwise ask the user to choose from the returned names.
4. Verify `mount.status`, `layout.inspect`, and the policy result. Do not report operational readiness before all succeed.
5. Use `file.list`, bounded `file.get`, and bounded `file.put` for file operations. For put, provide an explicit trusted `transferRoot` and a source path relative to it. Reject traversal and all symlinks.
6. Use local workspace for scratch, cache, builds, Git, and SQLite. Put durable artifacts under shared `common`, organization common, or organization/agent paths.

Read `references/operations.md` for command and recovery details.