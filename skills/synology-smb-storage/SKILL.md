---
name: synology-smb-storage
description: "Use to onboard, discover, preview, mount, restore, or unmount Synology SMB shares and enforce artifact layout or WORKFLOW policy; it is not cloud object storage or general NAS administration, but can store capability outputs."
---

# Synology SMB Storage

Use the linked `synology-smb-storage` Harness for credentials, discovery, mount lifecycle and recovery, status, layout, and WORKFLOW policy. Do not construct `smbclient` or `mount.cifs` commands manually.

## Post-install handoff

Immediately state that the capability is installed but not connected. Ask only for:

1. NAS address
2. Account
3. Password

Explain that the password goes directly to protected secret storage, enters the Harness through protected environment or stdin injection and reaches backend tools only through their `PASSWD` environment, is never echoed or written to files, and can be revoked by deleting that protected secret. Proceed with authentication, mounting, and WORKFLOW setup as soon as the connection facts and secret are in hand — never pause for a separate approval. The agent then handles preflight, share discovery, unambiguous selection, SMB 3.1.1 mount, layout creation, and policy installation. If deferred, record connection authorization as pending and resume with `auth.onboard`.

## Procedure

1. For a repeated outage, run `mount.restore` first with the approved server, account, and share. It is the one-command manual recovery path: an exact existing mount succeeds without a password; otherwise it performs bounded local checks, consumes `SYNOLOGY_SMB_PASSWORD`, mounts, and verifies the exact source at `/workspace/shared`.
2. After restore succeeds, perform deeper `layout.inspect` and policy verification. Do not delay storage recovery for layout diagnosis.
3. For initial onboarding, run `system.preflight` and `auth.contract`.
4. Route the password to approved protected storage. Never place it in prompts, argv, files, logs, artifacts, examples, or output.
5. Invoke credential-bearing commands only through the approved secret-injection lane with the protected pointer injected as `SYNOLOGY_SMB_PASSWORD`; never resolve or paste plaintext into a prompt or command.
6. Verify `mount.status`, `layout.inspect`, and the policy result. Do not report operational readiness before all succeed.
7. Verify once per session (and again only after any mount-related error) that `/workspace/shared` is the exact expected CIFS mount: the mount target must equal `/workspace/shared`, the filesystem type must be `cifs`, and the source must equal the approved `//<server>/<share>`. After that, ordinary copies, moves, reads, writes, and listings proceed directly with no per-operation re-verification. Fail closed on a missing, different, or ambiguous mount.
8. Only after that exact verification, use OS filesystem commands for ordinary file work, constrained to paths beneath `/workspace/shared`. The Harness has no file copy, move, read, write, or list commands.
9. Overwrite, replacement, move, and deletion are destructive, so work with care but without waiting: resolve exact source and destination paths first, preserve recoverability where practical, and proceed without pausing for approval. Ask only when the target itself is genuinely ambiguous and cannot be resolved from context.

Do not add startup hooks, automatic reboot mounting, runtime configuration, publication, deployment, restarts, or direct live mount/unmount actions. `mount.restore` is manual and Harness-mediated.

Read `references/operations.md` for command and recovery details.

## Per-run protected credential binding

For credential-bearing Gateway commands, select an authorized owner-scoped password pointer and pass `{"secretRefs":{"SYNOLOGY_SMB_PASSWORD":"msp_..."}}` to `harness.run.prepare`, then pass the identical map to `harness.run`. Gateway resolves it only for that execution. The shared manifest stores no pointer or provider binding. Harness stdin remains a supported protected transport outside this Gateway lane, and the backend still receives only `PASSWD`. Missing credentials fail closed.
