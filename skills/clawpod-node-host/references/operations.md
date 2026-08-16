# Operations and recovery

Invoke global options before the two-word command, for example:

```text
clawpod-node-host --json --state <owner-state> --openclaw-version 2026.4.11 --gateway-host <magicdns> --gateway-port 18789 --tls install plan
```

Apply with the returned plan ID, request ID, and exact confirmation challenge. Plans expire after 15 minutes; Tailscale evidence expires after five minutes. A target, provider, endpoint, version, or identity change requires replanning.

For service lifecycle actions, request an action-bound plan with `service status --lifecycle-action start|stop|restart`; this remains observational until separately confirmed and applied.

Status reports CLI, service registration/process, transport, pairing/connection, and capabilities separately. If Tailscale is absent, create and approve `tailscale install-plan`, then run `tailscale install-apply`. If logged out, approve `tailscale login-plan`/`login-apply`; the apply initiates login and pauses for the user's browser consent or MFA. Rerun `tailscale status`, `address`, and `same-tailnet` afterward. Never automate credential, MFA, or consent entry.

Uninstall removes only the provider-backed user service and preserves the CLI, `node.json`, pairing information, exec approvals, and browser policy. Rollback uses only a same-target authenticated Harness backup. If provisioning is correct but connection fails, pass the redacted evidence bundle to `node-connect`.
