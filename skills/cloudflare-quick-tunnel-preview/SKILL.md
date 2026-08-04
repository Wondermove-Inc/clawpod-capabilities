---
name: cloudflare-quick-tunnel-preview
description: Safely expose a loopback-only local preview through an accountless, TTL-bounded Cloudflare Quick Tunnel.
---
# Cloudflare Quick Tunnel Preview

Use only for temporary, accountless `trycloudflare.com` previews. Do not use for named tunnels, custom domains, production traffic, credentials, OAuth, or persistent hosting.

1. Obtain explicit approval before `start`, because it makes a local service externally reachable. Confirm the content has no secrets or privileged controls.
2. Run `preflight` with an absolute trusted `cloudflared`, loopback IP literal, port, and owner-only state root. Resolve failures rather than weakening checks.
3. Run `start` with the shortest practical TTL. Report the URL and expiry. Never promise availability or stable naming.
4. Use `inspect` or `status` to verify state. Treat malformed state, changed binaries, foreign PIDs, expiry, or auth/config-state findings as hard failures.
5. Run idempotent `stop` when done. It terminates only a process whose persisted ownership identity still matches.

The Harness keeps bounded sanitized logs and minimal mode-0600 state. Quick Tunnels are public Cloudflare endpoints without an SLA, access policy, or stable hostname.
