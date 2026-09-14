---
name: "clawpod-node-host"
description: "Use when a user wants to install ClawPod Node on Linux, macOS, or Windows and connect a computer to ClawPod. Select the standalone installer, guide Gateway setup and pairing, and explain app recovery or removal. Retain CLI/SSH provisioning for legacy installations. Use node-connect instead when an already configured node fails to connect or pair."
---

# ClawPod Node Host

Use the linked `clawpod-node-host` Harness with JSON output. Default onboarding uses the public standalone ClawPod Node installer. The target computer needs no separate Node.js, npm, repository checkout, or CLI installation.

## Install and connect

1. Establish the **user's target computer** OS and CPU from conversation or target evidence. Ask only for missing information, in the user's language. Never infer them from the agent pod's OS/CPU. Supported packages are Linux x64 (Debian/Ubuntu desktop), macOS arm64 (Apple Silicon) or x64 (Intel), and Windows x64. Do not select a different architecture when no matching package exists.
2. Run `clawpod-node-host --json installer info --platform <linux|macos|windows> --arch <x64|arm64> [--gateway-url <root-WebSocket-URL>]`. This reads the bundled release manifest offline and returns the matching download, checksum, setup, and recovery guidance; it does not install anything or verify release availability remotely.
3. Give the user the matching public installer link and the next local action. The public [release page](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/tag/node-v0.1.0) also provides the packages and checksums. These initial packages are unsigned; Linux container validation passed, while native macOS/Windows lifecycle checks remain untested. State that limitation once when handing over the installer.
4. Have the user open **ClawPod Node**, enter the actual Gateway WebSocket root URL and display name, and put the Gateway token or password in the separate local authentication field. Use an already known reachable Gateway endpoint; never fabricate one or substitute a Cloud Portal/dashboard URL. Never put credentials in download/setup links, commands, or messages. See [onboarding](references/onboarding.md) for endpoint and setup details.
5. After **Save settings** and **Start node**, inspect the actual pending device request in the Agent Control UI or available device-pairing tool. Match the target's device identity and exact pending request, then approve that request within the user's connection task. A display name alone is not an identity. Resolve multiple matches or insufficient identity evidence before approving. The app generates its own identity: do not call legacy `enroll status --node-id` or `enroll approve` with a synthetic enrollment ID.
6. Verify that the exact paired device is **connected at the Gateway**, and report the first useful next action. Local **Running** means only that the process started. If correct setup still fails to connect or pair, pass redacted evidence to `node-connect`.

Do not require Tailscale enrollment or agent login when the Gateway endpoint is already reachable. Prefer `wss://`; the app's explicit private `ws://` option applies only to supported private LAN addresses, not Tailscale IPv4 (`100.64.0.0/10`) or public addresses.

## Recovery and removal

Use the app's **Reconnect**, **Stop**, and **Start when I sign in** controls. Stop persists across reopening and sign-in. Startup runs under the logged-in user. Read [operations](references/operations.md) for authentication recovery, platform removal, upgrades, and preserved state. The app uses `~/.clawpod-node`; do not migrate or remove existing `~/.openclaw` state or operate legacy node services for an app user.

## Legacy CLI and SSH

Use [legacy provisioning](references/legacy.md) only for an existing CLI installation or an explicit CLI/script/SSH request. Existing enrollment, bootstrap, Tailscale, and lifecycle commands remain supported; they are not prerequisites for installing the app. Capability/Harness version `0.3.0`, installer version `0.1.0`, and bundled OpenClaw runtime `2026.4.11` have different meanings. Legacy CLI installs remain pinned to literal `2026.4.11`.

For routine work on an already connected node, use first-class `nodes` or `exec host=node`. General host diagnosis, Gateway lifecycle, and Tailscale administration belong to their respective tools. Local OS/browser consent remains user-driven; do not automate credential, MFA, or consent entry.
