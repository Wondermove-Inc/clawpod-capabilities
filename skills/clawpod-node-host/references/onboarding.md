# Standalone installer onboarding

Use the eight stages in SKILL.md. This reference expands Tailscale preparation, installer selection, and the actual connection handoff.

## 1. Sign the agent in to Tailscale

Run the Harness commands through `cli_harness`:

```text
clawpod-node-host --json agent status
clawpod-node-host --json agent login
```

Use `agent login` only when status reports `NeedsLogin`. Send its returned URL to the user and have them choose the intended tailnet. After sign-in, re-run `agent status` until `Running`; a sign-in URL or browser confirmation alone is insufficient. An already connected agent needs no new login. For a stopped daemon, pending device authorization, or a status failure, resolve that reported condition before advancing. The Harness starts `tailscale login`; it does not install or reconfigure the pod's Tailscale.

## 2. Install and sign in to Tailscale on the user's computer

Send [the official download page](https://tailscale.com/download) or [installation guide](https://tailscale.com/docs/how-to/quickstart) for the user's computer. Reuse an existing installation. Have the user open Tailscale, sign in to the same intended tailnet as the agent, and confirm the connection. This is a separate sign-in on the user's computer. If the OS is needed to choose Tailscale installation instructions, ask now and reuse it at stage 3.

Compare the real agent and computer device identities/tailnet and verify communication between them using available tools or the user's local observations. Do not treat two unrelated signed-in accounts as proof that the devices can communicate. Node app installation alone does not install Tailscale or join a tailnet. No SSH setup or generated node installation script is needed.

## 3–4. Confirm the computer and select its installer

`installer info` requires explicit platform and architecture; it never detects them from the agent runtime.

| Target computer | Platform | Architecture | Package |
| --- | --- | --- | --- |
| Debian/Ubuntu Linux desktop, x64 | `linux` | `x64` | `ClawPod-Node-0.2.0-linux-x64.deb` |
| Mac, Apple Silicon | `macos` | `arm64` | `ClawPod-Node-0.2.0-darwin-arm64.pkg` |
| Mac, Intel | `macos` | `x64` | `ClawPod-Node-0.2.0-darwin-x64.pkg` |
| Windows, x64 | `windows` | `x64` | `ClawPod-Node-0.2.0-win32-x64.exe` |

For example, after establishing that the user's Mac has Apple Silicon:

```text
clawpod-node-host --json installer info --platform macos --arch arm64
```

The Harness uses its bundled manifest, corresponding to public `node/release.json` in `Wondermove-Inc/clawpod-capabilities`. Send the returned download URL and use its SHA-256 value when verifying a downloaded file. A selection result describes the release; it does not prove an asset was downloaded or installed. If an asset cannot be downloaded, check the public release status rather than silently switching to npm or a different build.

## 5. Obtain and hand over the actual connection values

Use the requesting user's existing authorization to read the Gateway's effective connection details with the available local tools. Provide the actual values to that user during installation; telling them only to obtain a token elsewhere does not complete the handoff.

1. Identify the Gateway host/service serving this Agent and its active startup options, configuration path, and authentication mode. Do not assume a fixed config path or read another pod's configuration. Startup auth overrides take precedence; after those are applied, a resolved config token takes precedence over `OPENCLAW_GATEWAY_TOKEN`. Read the effective source used by this running service, not an unrelated shell's environment or a stale config value. Configuration can use environment substitution or a SecretRef: obtain the resolved active value through the available authorized local access, rather than handing over the reference object.
2. Gateway `config.get` and CLI `openclaw config get` redact secrets. They can help inspect configuration but cannot supply the plaintext token. Obtain the active credential from its actual authorized runtime/configuration/secret source. In password mode, resolve and provide the active password. If the value is inaccessible, explain that specific access limitation; never present a redaction marker, placeholder, or unresolved SecretRef as a working credential. For `none` or `trusted-proxy` mode, explain the concrete mismatch with this app's token/password fields rather than inventing a token or silently changing Gateway authentication.
3. On the actual Gateway host/service, inspect `tailscale status --json` and verify `Self.DNSName` and `Self.TailscaleIPs`. These must describe the Gateway's route, not the user's node or an arbitrary agent pod. Provide its verified Tailscale DNS name and/or IP. If Tailscale is absent or disconnected, return to stage 1 and resolve the reported condition before continuing this Tailscale workflow.
4. Check the effective listener and any Tailscale Serve/reverse-proxy mapping before constructing the complete WebSocket endpoint. Use the verified externally reachable scheme and port; do not assume that the listener's port, `18789`, or TLS port `443` is the client endpoint. The root URL must reach this Gateway from the user's computer. A Cloud Portal or Agent dashboard URL is not a node endpoint, and a loopback address refers to the user's computer rather than the remote Agent pod.

Send a concise handoff containing the matching **installer link**, **Gateway Tailscale address**, **Gateway WebSocket URL including scheme and port**, **authentication mode**, and **actual token or password** as separate labeled values. Supply verified values, not an example template. When Tailscale is unavailable, identify the unfinished setup stage rather than silently skipping it. Keep the credential in its separate user-facing authentication value; never append it to the endpoint, download/setup URL, public repository file, or diagnostic log.

## 6. Install and enter settings in the app

Open the DEB in the Linux package installer, open the PKG on macOS, or run the EXE as the normal Windows user. The installation can run offline once downloaded. Connecting requires access to the Agent Gateway; browser automation separately requires a compatible installed browser.

Open **ClawPod Node** from the application menu, Finder, or Start menu. Its setup page opens in the default browser.

Check **Desktop setup** in this same app; do not install a separate remote-computer helper.

| OS | Desktop setup |
| --- | --- |
| macOS | Allow **ClawPod Node** in Screen & System Audio Recording and Accessibility (Device Control & Data Access on macOS 27). The app requests access; the user grants it in System Settings. The permission label does not mean audio is captured: this release captures screens only. |
| Windows | Use the logged-in, unlocked interactive desktop. There is no macOS-style permission switch; UAC/secure desktops or elevated windows may be unavailable to ordinary input. |
| Linux X11 | Use a graphical session with a reachable X display and XTest. This build requires glibc 2.36 or newer. |
| Linux Wayland | Setup checks portal capabilities. When desktop control starts, approve the system screen/input sharing dialog and choose the monitor. Actual compositor behavior has not been verified for this preview. |

On macOS, use **Open settings** and **Check again** if the prompt does not appear.
After an ad-hoc signed app update, an enabled switch can refer to an older app
identity. If a fresh check still reports missing access, remove that stale entry
and re-add the current **ClawPod Node** from Applications, then check again.
If an already running desktop session still lacks access, **Reconnect** restarts
the node with saved settings; coordinate this with any active node work.
Do not request permission for a separate “ClawPod Remote Computer” app.
Missing GUI permissions do not prevent entering Gateway connection settings.


- Copy the supplied complete root WebSocket URL into the Gateway address field. An optional trailing slash is allowed; URL credentials, paths, queries, and fragments are not.
- For a plain Gateway listener on a private or Tailscale IP, use `ws://<IP>:<port>` (for example, `ws://100.64.1.2:18789`). This is always enabled; there is no checkbox. All RFC1918 IPv4 ranges, Tailscale CGNAT `100.64.0.0/10`, IPv6 ULA, loopback, link-local, and localhost/`.localhost`/`.local` names are supported.
- Use `wss://` only for an endpoint that actually provides TLS. Non-local hostnames, including Tailscale `.ts.net` names, require a TLS endpoint in this app; use the Tailscale IP for plain WebSocket access. Tailscale sign-in does not configure Gateway TLS. Do not change `ws://` to `wss://` merely because the address belongs to Tailscale.
- Enter a display name, select the supplied token/password authentication mode, and copy the actual credential provided by the agent into the separate local authentication field. TLS certificate SHA-256 pinning is optional when the deployment provides a fingerprint.
- Select **Save settings**, then **Start node**. The two Tailscale setup stages must already be verified.

## 7–8. Pair, verify, and use the actual device

Inspect pending device pairing in the Agent Control UI or the available device-pairing tool. Match the exact pending request and device identity to the user's computer; display names can collide. Approve the matched request as part of the requested connection. If identity evidence is insufficient or several requests match, resolve that ambiguity before approving.

The installer generates its own device identity under its app state directory. Use the Gateway's actual device-pairing API or Control UI for approval; no synthetic enrollment identifier is involved. In a CLI-only environment, inspect `openclaw devices list --json` and approve the exact pending request with `openclaw devices approve <requestId>`. Do not substitute the separate `nodes approve` flow.

Confirm the exact device appears connected in the Gateway's node status. App **Running** is a local process observation and does not establish successful authentication, pairing, or connection. For a requested capability, use a safe call such as `system.which` after connection. If correct setup still fails, use `node-connect` when available and provide the redacted endpoint, local state/error timestamps, and device-pairing/connection observations.
