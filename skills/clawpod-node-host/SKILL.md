---
name: "clawpod-node-host"
description: "Use when a user wants to connect a Mac or Windows 11 PC to ClawPod as a node. Default flow: hand the user one complete, credential-free script (Tailscale, openclaw install, gateway address baked in), then auto-detect and approve the pairing request. Can also drive SSH-based provisioning, verification, recovery, and removal. Use node-connect instead when an already configured node fails to connect or pair."
---

# ClawPod Node Host

Use the linked `clawpod-node-host` Harness. Always request JSON output. The only accepted package version is literal `2026.4.11`; never use `latest`, a range, alias, URL, or inferred version.

## User interaction

- Start in the user's language with one short product-level question. In Korean, use: `ClawPod 노드 연결을 도와드릴게요. 연결할 컴퓨터는 Mac인가요, Windows 11인가요?`
- Do not expose implementation prerequisites at startup. Keep OpenClaw and Node.js versions, network names and ports, TLS details, request IDs, fingerprints, and Tailscale policy internal unless a blocker, ambiguity, or safety decision makes one detail necessary.
- Progressively disclose only the next needed decision. When blocked, ask exactly one concise user action, then re-inspect instead of listing future steps.
- Before any mutation in the SSH-driven fallback, summarize the exact ClawPod-visible effect and ask one simple approval bound to the fresh plan. The self-service track needs no such approvals — the user runs the script themselves and the pairing approval is the agent's own act on its own pairing queue.
- Report completion and recoverable failures in ClawPod language. Keep diagnostic internals in redacted evidence, not the default user message.

## Default track: self-service enrollment (one script, zero SSH)

The default onboarding gives the user **one complete script and nothing else to decide**. Never send a script with placeholders, blanks to fill in, or "replace this" instructions — `enroll.generate` bakes in the real Gateway host, port, TLS flag, pinned `openclaw@2026.4.11`, and a generated node id.

0. **First, the agent's own Tailscale.** The agent pod ships with Tailscale installed but signed out. Run `agent status`; if it is not connected, run `agent login`, send the returned link to the user (in Korean: `이 링크를 열어 ClawPod의 Tailscale 계정으로 로그인해주세요.`), and poll `agent status` until it reports connected. This is a one-time human sign-in; never try to enter credentials yourself, and never reinstall or reconfigure the agent's Tailscale.
1. Ask only which OS the computer is (Mac or Windows 11).
2. Run `enroll generate --platform <os> --gateway-host <the agent's own Gateway MagicDNS name> --gateway-port 18789 [--tls]`. Use the Gateway endpoint the agent itself connects to; the user is never asked for an address.
3. Send the user the returned script verbatim (as a code block or file) with two sentences: run it in Terminal (macOS) or PowerShell (Windows), and sign in to Tailscale **with the same account as ClawPod** if the script asks. The script itself installs Tailscale and Node.js when missing, prints an `ACTION:` line and exits if a human sign-in is needed, and is safe to re-run from the top after that action.
4. Poll `enroll status --node-id <returned id>`. `waiting_user` (exit 3) just means the user has not finished — keep polling on a relaxed interval; do not re-ask the user unless they report an `ACTION:` line or an error.
5. When the request appears, approve it immediately with `enroll approve --node-id <id>` — do not ask the user for another confirmation; retain the exact request ID and fingerprint as internal verification evidence. Exactly one matching request is required; on `PAIRING_AMBIGUOUS`, fall back to `pairing status`/`pairing approve` with the exact request ID.
6. Verify with `validate run --validation-level connection`, then report the node as connected and state the first useful next action.

Rollback: the same script re-run with `OPENCLAW_NODE_ROLLBACK=1` removes the node service and package.

## Fallback track: agent-driven SSH provisioning

Use only when the user cannot run a script themselves (headless target, provisioning many machines, or the user explicitly asks the agent to do it over SSH). Follow the explicit resumable dialogue state machine in [onboarding](references/onboarding.md); do not skip its bootstrap-transport gate for a remote computer that is not already a connected node.

1. Use the typed Tailscale install-status → install-plan/apply → login-plan/apply → status → address → same-tailnet commands. Each apply requires a fresh exact plan and approval. Login initiation pauses for one human browser action; never enter credentials, MFA, or consent. When `login-apply` returns `status: waiting_user`, give the user the **Tailscale login link** it surfaces and ask them to sign in with the **same Tailscale account as ClawPod** (the agent's tailnet). `same-tailnet` verifies the accounts match; on mismatch ask the user to log out on the node and sign in again. Then use ssh-server status → plan/apply for macOS Remote Login or Windows OpenSSH Server with Tailscale-only scope. SSH only to the returned Tailscale IP. These Tailscale steps run **only on the node** — the agent runtime already runs Tailscale on its tailnet and is never reinstalled, reconfigured, or logged out. Join the node with MagicDNS/accept-dns **disabled** (`--accept-dns=false`); MagicDNS overwrites the node's DNS resolver and can break its networking.
2. Password, key, SSH agent, and Tailscale SSH are equal supported choices. When a password or other secret is needed, ask the user to send it in chat; on receipt, immediately place it in protected runtime injection and discard the captured plaintext. Pass only `password-env:NAME`, `key-env:NAME`, `agent`, or `tailscale` references — never re-echo or persist the secret in argv, files, state, scripts, plans, logs, or responses. These are **SSH bootstrap credentials** for the agent's one-time SSH to the node — not the ClawPod Gateway's authentication. Keep the Gateway in **token-based connection mode**.
3. Run bounded noninteractive preflight, then generate `bootstrap.plan`. Obtain exact plan-bound approval before `bootstrap.apply`; resume its idempotent preflight/upload/execute/verify stages from the first incomplete stage. On partial effects, provide one retry or revoke/rollback action.
4. The approved remote script installs exactly `openclaw@2026.4.11`, verifies that exact version, and installs and starts the node **as a reboot-persistent service through the platform service provider** (launchd on macOS, Task Scheduler on Windows) that `openclaw node install` registers; do not hand-roll a LaunchDaemon or scheduled task. Set `OPENCLAW_ALLOW_INSECURE_PRIVATE_WS=1` before `openclaw node install` (required for the node-to-Gateway private WebSocket connection) so the registered service carries it.
5. Generate the matching lifecycle plan, obtain its separate exact approval, apply it, and verify observed postconditions. Preserve `node.json`, pairing records, exec approvals, and browser policy during uninstall/rollback.
6. Handle pairing as an exact-target act: re-list current requests with `pairing status`, require one fingerprint match, and approve with `pairing approve <exact-requestId>`. Permission denial and multiple matches are blockers; never guess and never use the Gateway's `nodes approve`.
7. Validate service, connection, and requested system/browser capabilities. Use `nodes invoke` only for safe calls such as `system.which`; use `exec host=node` for an optional harmless shell probe. Hand connection diagnosis after correct provisioning to `node-connect`.

Default tests and evaluation use fixtures and command recording. Real OS integration requires an explicitly disposable macOS or Windows host gate. Read [operations](references/operations.md) for command and recovery details.

## Boundaries

- For a routine command on an already connected node, use first-class `nodes` or `exec host=node`.
- For QR/bootstrap/pairing/network diagnosis without provisioning, use `node-connect`.
- Compose with `desktop` for general GUI work and macOS permission prompts; consent is always user-driven.
- This capability supports only onboarding-scoped Tailscale install and login initiation. Route Serve/Funnel, ACL policy, tailnet administration, logout/removal, and Gateway lifecycle elsewhere.
- Runtime is Node, never Bun. On 2026.4.11, start uses provider-supported `node restart` and reports that operation.
