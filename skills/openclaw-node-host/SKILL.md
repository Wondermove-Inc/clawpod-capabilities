---
name: "openclaw-node-host"
description: "Connect or manage a ClawPod node on Mac/Windows by inspecting readiness, applying approved plans, and pairing. Use node-connect for diagnostics."
---

# OpenClaw Node Host

Use the linked `openclaw-node-host` Harness. Always request JSON output. The only accepted package version is literal `2026.4.11`; never use `latest`, a range, alias, URL, or inferred version.

## User interaction

- Start in the user's language with one short product-level question. In Korean, use: `ClawPod 노드 연결을 도와드릴게요. 연결할 컴퓨터는 Mac인가요, Windows 11인가요?`
- Do not expose implementation prerequisites at startup. Inspect safe prerequisites automatically after the platform is known. Keep OpenClaw and Node.js versions, network names and ports, TLS details, request IDs, fingerprints, and Tailscale policy internal unless a blocker, ambiguity, or safety decision makes one detail necessary.
- Progressively disclose only the next needed decision. When blocked, ask exactly one concise user action, then re-inspect instead of listing future steps.
- Before any mutation, summarize only the exact ClawPod-visible effect and ask one simple approval bound to the fresh plan. Do not show internal confirmation tokens unless the runtime requires the user to enter one.
- Treat pairing as a separate approval. Ask simply whether to approve the detected ClawPod node; retain the exact request ID and fingerprint as internal verification evidence unless ambiguity or safety requires showing them.
- Report completion and recoverable failures in ClawPod language. Keep diagnostic internals in redacted evidence, not the default user message.

Follow the explicit resumable dialogue state machine in [onboarding](references/onboarding.md). Do not skip its bootstrap-transport gate for a remote computer that is not already a connected node.

## Procedure

1. Start with the target OS. Generate the matching local readiness script so a human can install and log in to Tailscale, confirm the agent runtime is on the same tailnet, obtain the Tailscale IP, and approve macOS Remote Login or Windows OpenSSH Server plus its Tailscale-scoped firewall rule. Then verify SSH only over that Tailscale IP.
2. Password, key, SSH agent, and Tailscale SSH are equal supported choices. A user may provide a password naturally, but immediately place it in protected runtime injection and discard the captured plaintext. Pass only `password-env:NAME`, `key-env:NAME`, `agent`, or `tailscale` references—never secret values in argv, files, state, scripts, plans, logs, or responses.
3. Run bounded noninteractive preflight, then generate `bootstrap.plan`. Obtain exact plan-bound approval before `bootstrap.apply`; resume its idempotent preflight/upload/execute/verify stages from the first incomplete stage. On partial effects, provide one retry or revoke/rollback action.
4. The approved remote script installs exactly `openclaw@2026.4.11`, verifies that exact version, installs and starts the node, and checks pairing readiness. Continue through pair and verify; resume at the first incomplete idempotent stage.
5. Generate the matching lifecycle plan, obtain its separate exact approval, apply it, and verify observed postconditions. Preserve `node.json`, pairing records, exec approvals, and browser policy during uninstall/rollback.
6. Handle pairing as a separate exact-target approval: re-list current `devices` requests, require one fingerprint match, and approve with `devices approve <exact-requestId>`. Permission denial and multiple matches are blockers; never guess and never use `nodes approve`.
7. Validate service, connection, and requested system/browser capabilities. Use `nodes invoke` only for safe calls such as `system.which`; use `exec host=node` for an optional harmless shell probe. Hand connection diagnosis after correct provisioning to `node-connect`.

Default tests and evaluation use fixtures and command recording. Real OS integration requires an explicitly disposable macOS or Windows host gate. Read [operations](references/operations.md) for command and recovery details.

## Boundaries

- For a routine command on an already connected node, use first-class `nodes` or `exec host=node`.
- For QR/bootstrap/pairing/network diagnosis without provisioning, use `node-connect`.
- Compose with `desktop` for general GUI work and macOS permission prompts; consent is always user-driven.
- Reject Tailscale lifecycle, Serve/Funnel, ACL/account/tailnet mutation, and Gateway lifecycle requests.
- Runtime is Node, never Bun. On 2026.4.11, start uses provider-supported `node restart` and reports that operation.
