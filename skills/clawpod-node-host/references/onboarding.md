# Standalone installer onboarding

Use this flow for a new ClawPod Node app installation. Read [legacy provisioning](legacy.md) only for an explicit CLI, script, or SSH workflow.

## Choose the user's computer

`installer info` requires explicit platform and architecture; it never detects them from the agent runtime.

| Target computer | Platform | Architecture | Package |
| --- | --- | --- | --- |
| Debian/Ubuntu Linux desktop, x64 | `linux` | `x64` | `ClawPod-Node-0.1.0-linux-x64.deb` |
| Mac, Apple Silicon | `macos` | `arm64` | `ClawPod-Node-0.1.0-darwin-arm64.pkg` |
| Mac, Intel | `macos` | `x64` | `ClawPod-Node-0.1.0-darwin-x64.pkg` |
| Windows, x64 | `windows` | `x64` | `ClawPod-Node-0.1.0-win32-x64.exe` |

For example, after establishing that the user's Mac has Apple Silicon:

```text
clawpod-node-host --json installer info --platform macos --arch arm64
```

The Harness uses its bundled manifest, corresponding to public `node/release.json` in `Wondermove-Inc/clawpod-capabilities`. Send the returned download URL and use its SHA-256 value when verifying a downloaded file. A selection result describes the release; it does not prove an asset was downloaded or installed. If an asset cannot be downloaded, check the public release status rather than silently switching to npm or a different build.

Open the DEB in the Linux package installer, open the PKG on macOS, or run the EXE as the normal Windows user. The installation can run offline once downloaded. Connecting requires access to the Agent Gateway; browser automation separately requires a compatible installed browser.

## Gateway setup

Open **ClawPod Node** from the application menu, Finder, or Start menu. Its setup page opens in the default browser.

- Enter the actual Gateway root WebSocket endpoint, for example `wss://gateway.example.com:18789`. An optional trailing slash is allowed; URL credentials, paths, queries, and fragments are not. A Cloud Portal or Agent dashboard address is not this endpoint.
- Prefer a known endpoint from the current Agent configuration if reachable by the target computer. If it is missing, obtain the real root endpoint from the administrator. Installing the app does not provision a Gateway, public proxy, or network route.
- Use `wss://` for public endpoints and Tailscale IPv4 endpoints. The explicit private `ws://` setting accepts supported private LAN addresses and `.local` names; it does not make a public address or `100.64.0.0/10` private to the app. Loopback addresses refer to the user's computer, not the remote Agent pod.
- Enter a display name and select token or password authentication. The user enters the Gateway credential directly in the app's local field. Keep that value separate from endpoint/download links and agent output. TLS certificate SHA-256 pinning is optional when the deployment provides a fingerprint.
- Select **Save settings**, then **Start node**. Do not introduce Tailscale setup if the endpoint already works.

## Pair and verify the actual device

Inspect pending device pairing in the Agent Control UI or the available device-pairing tool. Match the exact pending request and device identity to the user's computer; display names can collide. Approve the matched request as part of the requested connection. If identity evidence is insufficient or several requests match, resolve that ambiguity before approving.

The installer passes a display name to the bundled node process and uses its independently generated identity under the app state directory. Legacy `enroll generate` creates a synthetic `nodeId`, so its `enroll status --node-id` and `enroll approve` correlation cannot identify an app installation. Do not generate an enrollment script merely to watch app pairing, and do not use `nodes approve` as a substitute for device pairing.

Confirm the exact device appears connected in the Gateway's node status. App **Running** is a local process observation and does not establish successful authentication, pairing, or connection. For a requested capability, use a safe call such as `system.which` after connection. If correct setup still fails, give `node-connect` the redacted endpoint, local state/error timestamps, and device-pairing/connection observations.
