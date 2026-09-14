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

## Obtain and hand over the actual connection values

Use the requesting user's existing authorization to read the Gateway's effective connection details with the available local tools. Provide the actual values to that user during installation; telling them only to obtain a token elsewhere does not complete the handoff.

1. Identify the Gateway host/service serving this Agent and its active startup options, configuration path, and authentication mode. Do not assume a fixed config path or read another pod's configuration. Startup auth overrides take precedence; after those are applied, a resolved config token takes precedence over `OPENCLAW_GATEWAY_TOKEN`. Read the effective source used by this running service, not an unrelated shell's environment or a stale config value. Configuration can use environment substitution or a SecretRef: obtain the resolved active value through the available authorized local access, rather than handing over the reference object.
2. Gateway `config.get` and CLI `openclaw config get` redact secrets. They can help inspect configuration but cannot supply the plaintext token. Obtain the active credential from its actual authorized runtime/configuration/secret source. In password mode, resolve and provide the active password. If the value is inaccessible, explain that specific access limitation; never present a redaction marker, placeholder, or unresolved SecretRef as a working credential. For `none` or `trusted-proxy` mode, explain the concrete mismatch with this app's token/password fields rather than inventing a token or silently changing Gateway authentication.
3. On the actual Gateway host/service, inspect `tailscale status --json` and verify `Self.DNSName` and `Self.TailscaleIPs`. These must describe the Gateway's route, not the user's node or an arbitrary agent pod. Provide its verified Tailscale DNS name and/or IP. If Tailscale is absent or disconnected, state that finding and use an existing reachable Gateway route when one is available; do not fabricate a Tailscale address or force enrollment.
4. Check the effective listener and any Tailscale Serve/reverse-proxy mapping before constructing the complete WebSocket endpoint. Use the verified externally reachable scheme and port; do not assume that the listener's port, `18789`, or TLS port `443` is the client endpoint. The root URL must reach this Gateway from the user's computer. A Cloud Portal or Agent dashboard URL is not a node endpoint, and a loopback address refers to the user's computer rather than the remote Agent pod.

Send a concise handoff containing the matching **installer link**, **Gateway Tailscale address**, **Gateway WebSocket URL including scheme and port**, **authentication mode**, and **actual token or password** as separate labeled values. Supply verified values, not an example template. When Tailscale is unavailable, label that fact and give the verified alternative route. Keep the credential in its separate user-facing authentication value; never append it to the endpoint, download/setup URL, public repository file, or diagnostic log.

## Enter settings in the app

Open **ClawPod Node** from the application menu, Finder, or Start menu. Its setup page opens in the default browser.

- Copy the supplied complete root WebSocket URL into the Gateway address field. An optional trailing slash is allowed; URL credentials, paths, queries, and fragments are not.
- Use `wss://` for public and Tailscale endpoints. The explicit private `ws://` setting accepts supported private LAN addresses and `.local` names; it does not make a public address or Tailscale IPv4 `100.64.0.0/10` private to the app. Installing the app does not provision a Gateway, public proxy, or network route.
- Enter a display name, select the supplied token/password authentication mode, and copy the actual credential provided by the agent into the separate local authentication field. TLS certificate SHA-256 pinning is optional when the deployment provides a fingerprint.
- Select **Save settings**, then **Start node**. Do not introduce Tailscale setup if the endpoint already works.

## Pair and verify the actual device

Inspect pending device pairing in the Agent Control UI or the available device-pairing tool. Match the exact pending request and device identity to the user's computer; display names can collide. Approve the matched request as part of the requested connection. If identity evidence is insufficient or several requests match, resolve that ambiguity before approving.

The installer passes a display name to the bundled node process and uses its independently generated identity under the app state directory. Legacy `enroll generate` creates a synthetic `nodeId`, so its `enroll status --node-id` and `enroll approve` correlation cannot identify an app installation. Do not generate an enrollment script merely to watch app pairing, and do not use `nodes approve` as a substitute for device pairing.

Confirm the exact device appears connected in the Gateway's node status. App **Running** is a local process observation and does not establish successful authentication, pairing, or connection. For a requested capability, use a safe call such as `system.which` after connection. If correct setup still fails, give `node-connect` the redacted endpoint, local state/error timestamps, and device-pairing/connection observations.
