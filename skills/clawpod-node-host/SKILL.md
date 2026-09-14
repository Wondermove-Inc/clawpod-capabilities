---
name: "clawpod-node-host"
description: "Use when a user wants to connect a Linux, macOS, or Windows computer to ClawPod. Guide agent and computer Tailscale sign-in, select the standalone ClawPod Node installer, provide Gateway connection values, verify device pairing, and explain app recovery or removal. Use node-connect when available for an already configured node that fails to connect or pair."
---

# ClawPod Node Host

Use the linked `clawpod-node-host` Harness through `cli_harness`. Follow these eight stages for a new computer connection. Reuse verified completed stages; resume at the first unfinished stage. The Node app does not install Tailscale.

1. **Agent Tailscale sign-in.** Run `agent.status`. If it reports `NeedsLogin`, run `agent.login`, send the returned sign-in link to the user, and recheck `agent.status` after they sign in. Continue only when it reports `Running`. Keep an already connected agent unchanged. A returned login link is not proof of sign-in.
2. **Computer Tailscale installation and sign-in.** Help the user install Tailscale from [the official download page](https://tailscale.com/download) if missing and sign in to the same intended tailnet on their computer. Verify both devices can communicate. Do not confuse the computer's login with the agent's login. Ask only for missing platform information needed at this stage; reuse it below.
3. **Confirm the user's computer.** Establish the user's target computer OS and CPU from conversation or target evidence, not the agent pod. Supported Node packages are Linux x64 (Debian/Ubuntu desktop), macOS arm64 (Apple Silicon) or x64 (Intel), and Windows x64.
4. **Select the installer.** Run `installer.info` with `platform` and `arch`. Give the matching download link and checksum. This lookup is offline and does not perform the preceding sign-ins. The 0.1.0 preview is unsigned; Linux container installation was verified, while native macOS/Windows lifecycle validation remains outstanding. State that limitation once.
5. **Hand over connection values.** Obtain the actual Gateway host's Tailscale DNS/IP, verified full WebSocket URL (scheme and effective port), and actual active Gateway token using the available authorized tools. Give them to the requesting user as separate labeled values. Use the active password in password mode. `config.get` and `openclaw config get` redact secrets; never present masked output or a SecretRef as a usable credential. See [onboarding](references/onboarding.md) for active-source and endpoint checks. Tailscale sign-in alone does not create a Gateway endpoint.
6. **Install and start ClawPod Node.** Have the user install the DEB/PKG/EXE, open ClawPod Node, enter the supplied URL, display name, and token/password in their separate fields, then select **Save settings → Start node**. Node.js and the node runtime are bundled.
7. **Approve and verify the device.** Inspect actual pending device requests using the available Gateway device-pairing tools. Match the user's computer by its real device/request identity, approve that exact request within the connection task, then verify that exact node is connected. A display name alone is not an identity; resolve ambiguity before approval. Local app **Running** only describes its process.
8. **Use the connection.** Use existing `nodes` tools or `exec host=node` for requested work; verify a simple capability such as `system.which` first when needed. For a correctly configured node that still cannot connect or pair, use `node-connect` if available or report the specific diagnostic evidence.

The Harness commands are `agent.status`, `agent.login`, and `installer.info`. Do not generate node installation scripts, provision over SSH, or install a separate global CLI for this workflow. Device pairing is performed by the Gateway tools, not by a synthetic enrollment ID. Keep actual credentials out of URLs, public repository files, and diagnostic logs; the intended user receives the verified value separately.

If a stage cannot finish, explain the concrete missing action and resume that stage after it is resolved. Do not silently skip Tailscale setup or claim connectivity from login alone. Let the user complete their own browser sign-in and local OS prompts.

Use [app operations](references/operations.md) for Reconnect, Stop, startup, upgrades, and removal. The app's `.clawpod-node` state is separate from existing `.openclaw` state. This capability does not administer tailnet policy or the Gateway lifecycle.
