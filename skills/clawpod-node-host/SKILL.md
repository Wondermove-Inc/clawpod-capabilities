---
name: "clawpod-node-host"
description: "Use when a user wants to connect a Mac or Windows 11 PC to ClawPod as a node without manually configuring networking, SSH, or the node service. Can guide the human-only sign-in and approval steps, then automate Tailscale, SSH readiness, node installation, pairing, verification, recovery, and removal. Use node-connect instead when an already configured node fails to connect or pair."
---

# ClawPod Node Host

Use the linked `clawpod-node-host` Harness. Always request JSON output. The only accepted package version is literal `2026.4.11`; never use `latest`, a range, alias, URL, or inferred version.

## User interaction

- Start in the user's language with one short product-level question. In Korean, use: `ClawPod 노드 연결을 도와드릴게요. 연결할 컴퓨터는 Mac인가요, Windows 11인가요?`
- Do not expose implementation prerequisites at startup. Inspect safe prerequisites automatically after the platform is known. Keep OpenClaw and Node.js versions, network names and ports, TLS details, request IDs, fingerprints, and Tailscale policy internal unless a blocker, ambiguity, or safety decision makes one detail necessary.
- Progressively disclose only the next needed decision. When blocked, ask exactly one concise user action, then re-inspect instead of listing future steps.
- Before any mutation, summarize only the exact ClawPod-visible effect and ask one simple approval bound to the fresh plan. Do not show internal confirmation tokens unless the runtime requires the user to enter one.
- Treat pairing as a separate approval. Ask simply whether to approve the detected ClawPod node; retain the exact request ID and fingerprint as internal verification evidence unless ambiguity or safety requires showing them.
- Report completion and recoverable failures in ClawPod language. Keep diagnostic internals in redacted evidence, not the default user message.

Follow the explicit resumable dialogue state machine in [onboarding](references/onboarding.md). Do not skip its bootstrap-transport gate for a remote computer that is not already a connected node.

## Procedure

1. Start with the target OS. Use the typed Tailscale install-status → install-plan/apply → login-plan/apply → status → address → same-tailnet commands. Each apply requires a fresh exact plan and approval. Login initiation pauses for one human browser action; never enter credentials, MFA, or consent. When `login-apply` returns `status: waiting_user`, give the user the **Tailscale login link** it surfaces and ask them to open it and sign in — with the **same Tailscale account as ClawPod** (the agent's tailnet), otherwise the node and the agent cannot reach each other. `same-tailnet` verifies the accounts match; treat a mismatch as a blocker and ask the user to log out on the node and sign in again with the correct account. Then use ssh-server status → plan/apply for macOS Remote Login or Windows OpenSSH Server with Tailscale-only scope. SSH only to the returned Tailscale IP. These Tailscale steps run **only on the node** — the agent runtime already runs Tailscale on its tailnet and is never reinstalled, reconfigured, or logged out. Join the node with Tailscale MagicDNS/accept-dns **disabled** (`--accept-dns=false`); never enable Tailscale DNS on the node during onboarding, because MagicDNS overwrites the node's DNS resolver and can break its networking.
2. Password, key, SSH agent, and Tailscale SSH are equal supported choices. A user may provide a password naturally in chat, and the agent then immediately places it in protected runtime injection and discards the captured plaintext. Pass only `password-env:NAME`, `key-env:NAME`, `agent`, or `tailscale` references—never re-echo, persist, or place secret values in argv, files, state, scripts, plans, logs, or responses. These are **SSH bootstrap credentials** for the agent's one-time SSH to the node — not the ClawPod Gateway's authentication. Keep the Gateway in **token-based connection mode**; never tell the user to switch the Gateway to password mode. The node connects through the Gateway token and the pairing approval, not a Gateway password.
3. Run bounded noninteractive preflight, then generate `bootstrap.plan`. Obtain exact plan-bound approval before `bootstrap.apply`; resume its idempotent preflight/upload/execute/verify stages from the first incomplete stage. On partial effects, provide one retry or revoke/rollback action.
4. The approved remote script installs exactly `openclaw@2026.4.11`, verifies that exact version, installs and starts the node, and checks pairing readiness. Continue through pair and verify; resume at the first incomplete idempotent stage.
5. Generate the matching lifecycle plan, obtain its separate exact approval, apply it, and verify observed postconditions. Preserve `node.json`, pairing records, exec approvals, and browser policy during uninstall/rollback.
6. Handle pairing as a separate exact-target approval: re-list current requests with `pairing status`, require one fingerprint match, and approve with `pairing approve <exact-requestId>`. Permission denial and multiple matches are blockers; never guess and never use the Gateway's `nodes approve`.
7. Validate service, connection, and requested system/browser capabilities. Use `nodes invoke` only for safe calls such as `system.which`; use `exec host=node` for an optional harmless shell probe. Hand connection diagnosis after correct provisioning to `node-connect`.

Default tests and evaluation use fixtures and command recording. Real OS integration requires an explicitly disposable macOS or Windows host gate. Read [operations](references/operations.md) for command and recovery details.

## Boundaries

- For a routine command on an already connected node, use first-class `nodes` or `exec host=node`.
- For QR/bootstrap/pairing/network diagnosis without provisioning, use `node-connect`.
- Compose with `desktop` for general GUI work and macOS permission prompts; consent is always user-driven.
- This capability supports only onboarding-scoped Tailscale install and login initiation. Route Serve/Funnel, ACL policy, tailnet administration, logout/removal, and Gateway lifecycle elsewhere.
- Runtime is Node, never Bun. On 2026.4.11, start uses provider-supported `node restart` and reports that operation.
