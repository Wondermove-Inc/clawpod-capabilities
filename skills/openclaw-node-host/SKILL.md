---
name: openclaw-node-host
description: "Use for onboarding, installing, starting, stopping, repairing, uninstalling, rolling back, or resuming an OpenClaw node host on macOS or Windows 11. Can verify readiness, exact OpenClaw 2026.4.11, preinstalled same-tailnet Tailscale connectivity, apply guarded service plans, hand off pairing, and validate capabilities. Use node-connect for post-provisioning connection diagnosis and nodes/exec host=node for routine connected-node operations; never installs or changes Tailscale."
---

# OpenClaw Node Host

Use the linked `openclaw-node-host` Harness. Always request JSON output. The only accepted package version is literal `2026.4.11`; never use `latest`, a range, alias, URL, or inferred version.

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
