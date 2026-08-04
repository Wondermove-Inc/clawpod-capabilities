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

1. For a repeated outage, run `mount.restore` first with the approved server, account, and share. It is the one-command manual recovery path: an exact existing mount succeeds without a password; otherwise it performs bounded local checks, consumes `SYNOLOGY_SMB_PASSWORD`, mounts, and verifies the exact source at `/workspace/shared`.
2. After restore succeeds, perform deeper `layout.inspect` and policy verification. Do not delay storage recovery for layout diagnosis.
3. For initial onboarding, run `system.preflight` and `auth.contract`.
4. Route the password to approved protected storage. Never place it in prompts, argv, files, logs, artifacts, examples, or output.
5. Invoke credential-bearing commands only through the approved secret-injection lane with the protected pointer injected as `SYNOLOGY_SMB_PASSWORD`; never resolve or paste plaintext into a prompt or command.
6. Verify `mount.status`, `layout.inspect`, and the policy result. Do not report operational readiness before all succeed.
7. Use `file.list`, bounded `file.get`, and bounded `file.put` for file operations.

Do not add startup hooks, automatic reboot mounting, runtime configuration, publication, deployment, restarts, or direct live mount/unmount actions. `mount.restore` is manual and Harness-mediated.

Read `references/operations.md` for command and recovery details.
