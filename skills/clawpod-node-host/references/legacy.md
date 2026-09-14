# Legacy CLI, enrollment, and SSH provisioning

Read this only for an existing CLI-managed node or an explicit request for CLI, script, or SSH provisioning. New standalone app users follow [installer onboarding](onboarding.md) and [app operations](operations.md). These legacy commands remain compatible; they neither install nor manage the standalone app.

The only accepted legacy OpenClaw package version is literal `2026.4.11`; never substitute `latest`, a range, alias, URL, or inferred version. Runtime is Node, never Bun. Supported legacy provisioning targets are macOS and Windows 11; the new Linux installer support does not extend these legacy providers.

## Self-service enrollment script

The legacy enrollment track produces one complete credential-free script, with Gateway host, port, TLS flag, pinned package, and generated node ID already filled in. Do not send placeholders to the user.

1. For this Tailscale-based enrollment track, inspect `agent status`. If signed out, run `agent login`, send the returned login link, and let the user sign in with the ClawPod Tailscale account. Poll status until connected. The pod ships with Tailscale; never reinstall or reconfigure its Tailscale as part of node onboarding.
2. Establish whether the target is macOS or Windows 11. Run `enroll generate` with that platform and the actual Agent Gateway MagicDNS endpoint, port, and TLS setting.
3. Send the generated script verbatim as a file or code block. Tell the user to run it in Terminal or PowerShell and, if asked, sign in to Tailscale with the same account as ClawPod. The script installs Tailscale and Node.js when missing. An `ACTION:` line indicates one required local action; the user can then rerun the idempotent script from the top.
4. Poll `enroll status --node-id <returned-id>` at a relaxed interval. `waiting_user` (exit 3) is expected until the script completes; relay only a reported action or error that needs user attention.
5. On one matching request, use `enroll approve --node-id <returned-id>` within the requested connection task. Retain the exact request ID and fingerprint as internal verification evidence. On `PAIRING_AMBIGUOUS`, use `pairing status` and resolve the exact request and identity before `pairing approve`; never guess.
6. Run `validate run --validation-level connection` and confirm the exact node is connected before reporting completion.

```text
clawpod-node-host --json agent status
clawpod-node-host --json agent login
clawpod-node-host --json enroll generate --platform macos --gateway-host <magicdns> --gateway-port 18789 --tls
clawpod-node-host --json enroll status --node-id <returned-id>
clawpod-node-host --json enroll approve --node-id <returned-id>
```

These commands do not require a plan/confirm handshake. The synthetic enrollment ID is valid only for that generated script; it cannot identify a standalone app's pairing request. Script rollback is the same script rerun with `OPENCLAW_NODE_ROLLBACK=1`, which removes its node service and package.

## Agent-driven SSH provisioning

Use this track for a headless target, multiple-machine provisioning, or an explicit SSH request. Resume at the first unmet stage with only redacted state. Before a mutation, state its concrete effect, generate the fresh exact plan, and apply its confirmation within the already authorized task; do not invent additional permission steps.

| Stage | Procedure |
| --- | --- |
| Target | Establish the user's target OS and requested lifecycle action. |
| Transport | On the node, use typed `tailscale install-status` → `install-plan`/`install-apply` as needed, `login-plan`/`login-apply`, then `status`, `address`, and `same-tailnet`. Login initiation pauses for the user's browser sign-in with the same Tailscale account as ClawPod. Keep node MagicDNS disabled with `--accept-dns=false`. Then use `ssh-server status` → plan/apply for macOS Remote Login or Windows OpenSSH Server with Tailscale-only scope. |
| Authentication | Password, key, SSH agent, and Tailscale SSH are supported. Use protected runtime injection and pass only `password-env:NAME`, `key-env:NAME`, `agent`, or `tailscale` references. Never re-echo or persist plaintext secrets in scripts, argv, state, recordings, plans, or logs. SSH bootstrap credentials are separate from Gateway authentication; this legacy Gateway flow uses token mode. |
| Inspect | Require the returned Tailscale IP, acquire the OpenSSH host key, compare its fingerprint with the target's locally displayed value, create an ephemeral mode-0600 known_hosts file, and run bounded noninteractive preflight. A host-key mismatch fails closed. |
| Plan and apply | Generate `bootstrap plan`, then `bootstrap apply` using the exact returned confirmation. Upload the deterministic script by content hash and execute with strict host-key checks, or hand over the same credential-free script for local execution. Resume its idempotent `preflight`, `upload`, `execute`, and `verify` stages from the first incomplete stage. |
| Service | Verify exact `openclaw@2026.4.11`. `openclaw node install` registers the provider-supported persistent service: launchd on macOS or Task Scheduler on Windows. Keep `OPENCLAW_ALLOW_INSECURE_PRIVATE_WS=1` before install when using the legacy private WebSocket setup so the registered service inherits it. Do not hand-roll services. |
| Pair | Re-list with `pairing status`, match one exact request to the expected fingerprint, and use `pairing approve <exact-requestId>`. Permission denial or unresolved multiple matches blocks approval. Do not substitute Gateway `nodes approve`. |
| Verify | Validate service, Gateway connection, and requested capabilities. Use safe `nodes invoke` calls such as `system.which`, or an optional harmless shell probe through `exec host=node`. Hand correct-provisioning connection failures to `node-connect`. |

These Tailscale and SSH-server changes concern the target only. Do not reinstall, reconfigure, or log out the agent's own Tailscale. Remote execution is restricted to the returned Tailscale IP; do not fall back to public, DNS, or generic LAN SSH. Never automate a user's browser credentials, MFA, consent, or local OS permission prompts.

Changed target, transport, endpoint, package version, or identity evidence requires replanning. Store only opaque credential reference kind, hashes, redacted facts, exact plan binding, and stage status. On partial effects, identify one retry or rollback/revoke action and resume at the first unmet stage.

## Legacy lifecycle and recovery

Global options precede the two-word command:

```text
clawpod-node-host --json --state <owner-state> --openclaw-version 2026.4.11 --gateway-host <magicdns> --gateway-port 18789 --tls install plan
```

Apply with the returned plan ID, request ID, and exact confirmation challenge. Plans expire after 15 minutes; Tailscale evidence expires after five minutes. For service actions, request an action-bound plan with `service status --lifecycle-action start|stop|restart`. Status is observational until apply. On runtime `2026.4.11`, start uses provider-supported `node restart` and reports that operation.

Status distinguishes CLI, service registration/process, transport, pairing/connection, and capabilities. Legacy uninstall removes only the provider-backed user service, preserving the CLI, `node.json`, pairing records, exec approvals, and browser policy. This differs from the enrollment script's rollback, which also removes its package. Rollback uses a same-target authenticated Harness backup. Do not apply any of these operations to app-managed `~/.clawpod-node` state.

Default tests use fixtures and command recording. Real legacy OS integration requires an explicitly disposable macOS or Windows host. This capability's Tailscale support is limited to onboarding install and login initiation; Serve/Funnel, ACL policy, tailnet administration, logout/removal, and Gateway lifecycle belong elsewhere.
