---
name: synology-smb-storage
description: Connect Synology SMB 3.1.1 shared storage, verify its exact mount, and enforce its durable-artifact layout and WORKFLOW policy.
---

# Synology SMB Storage

Use the linked `synology-smb-storage` Harness for credentials, discovery, mount lifecycle and recovery, status, layout, and WORKFLOW policy. Do not construct `smbclient` or `mount.cifs` commands manually.

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
7. Before every ordinary file copy, move, read, write, or listing, verify that `/workspace/shared` is the exact expected CIFS mount: the mount target must equal `/workspace/shared`, the filesystem type must be `cifs`, and the source must equal the approved `//<server>/<share>`. Fail closed on a missing, different, or ambiguous mount.
8. Only after that exact verification, use OS filesystem commands for ordinary file work, constrained to paths beneath `/workspace/shared`. The Harness has no file copy, move, read, write, or list commands.
9. Obtain approval required by the active policy before mutations. Treat overwrite, replacement, move, and deletion as destructive: inspect and resolve exact source and destination paths first, preserve recoverability where practical, and ask before proceeding when scope or authorization is unclear.

Do not add startup hooks, automatic reboot mounting, runtime configuration, publication, deployment, restarts, or direct live mount/unmount actions. `mount.restore` is manual and Harness-mediated.

Read `references/operations.md` for command and recovery details.
