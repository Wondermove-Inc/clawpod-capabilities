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

1. Inspect system, version, Tailscale, service, and onboarding status. Treat Tailscale only as a verification gate. Never install, update, reinstall, log in, log out, reset, configure, or otherwise mutate it.
2. Require a MagicDNS name or tailnet IP, port, and TLS intent. Credentials enter only through protected environment or existing protected config channels—never argv, state, plans, logs, service definitions, or responses.
3. Generate the matching fresh plan. Review its redacted effects and preconditions, then obtain the plan-bound confirmation required by its safety class. Never reuse a token for another action, target, request, or plan.
4. Apply the exact plan and verify observed postconditions. Resume interrupted work from the first unmet postcondition. Preserve `node.json`, pairing records, exec approvals, and browser policy during uninstall/rollback.
5. Handle pairing as a separate exact-target approval: re-list current `devices` requests, match one request to the node fingerprint, confirm it separately, and approve using `devices approve <exact-requestId>`. Never use `nodes approve`.
6. Validate service, connection, requested system/browser capabilities. Use `nodes invoke` only for safe calls such as `system.which`; use `exec host=node` for an optional harmless shell probe. Hand connection diagnosis after correct provisioning to `node-connect`.

Default tests and evaluation use fixtures and command recording. Real OS integration requires an explicitly disposable macOS or Windows host gate. Read [operations](references/operations.md) for command and recovery details.

## Boundaries

- For a routine command on an already connected node, use first-class `nodes` or `exec host=node`.
- For QR/bootstrap/pairing/network diagnosis without provisioning, use `node-connect`.
- Compose with `desktop` for general GUI work and macOS permission prompts; consent is always user-driven.
- Reject Tailscale lifecycle, Serve/Funnel, ACL/account/tailnet mutation, and Gateway lifecycle requests.
- Runtime is Node, never Bun. On 2026.4.11, start uses provider-supported `node restart` and reports that operation.
