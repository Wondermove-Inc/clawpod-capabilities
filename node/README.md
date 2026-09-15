# ClawPod Node downloads

Install ClawPod Node on your computer to connect it to an existing ClawPod Agent.
Download just the installer matching **that computer's** operating system and CPU.
You do not need access to the Agent source repository, npm, or a separate Node.js
installation. Installation is offline; connecting requires access to your Gateway.

## Download 0.1.1 preview

| Computer | Installer | Size |
| --- | --- | ---: |
| Linux x64, Debian/Ubuntu desktop | [Download DEB](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.1.1/ClawPod-Node-0.1.1-linux-x64.deb) | 161 MiB |
| macOS Apple Silicon | [Download PKG](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.1.1/ClawPod-Node-0.1.1-darwin-arm64.pkg) | 247 MiB |
| macOS Intel | [Download PKG](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.1.1/ClawPod-Node-0.1.1-darwin-x64.pkg) | 214 MiB |
| Windows x64 | [Download EXE](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.1.1/ClawPod-Node-0.1.1-win32-x64.exe) | 149 MiB |

[Release page and individual SHA-256 files](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/tag/node-v0.1.1)
· [Machine-readable versions, hashes, and exact byte sizes](release.json)

These initial installers are unsigned. macOS/Windows native installation and
desktop login startup have not yet been verified on those operating systems.
Linux offline installation, upgrade, and removal were verified in a Debian
container. See [validation scope](VALIDATION.md) before treating this preview as
a production-validated release.

Version 0.1.1 adds ClawPod icons on macOS, Windows, and Linux and enables private
and Tailscale IP `ws://` connections without an extra option. Existing settings
and device identity are preserved when upgrading. If an old saved address uses
`wss://` against a plain listener, correct the address before starting.

## Install and connect

1. The agent checks its own Tailscale sign-in. If signed out, it starts sign-in,
   gives you the login link, and verifies the connection after you sign in.
2. Install [Tailscale](https://tailscale.com/download) on your computer if missing,
   sign in to the same intended tailnet, and verify communication with the agent.
   Existing installations and active sign-ins are reused.
3. Confirm your computer's OS and CPU with the agent.
4. Download the matching ClawPod Node installer listed above.
5. The agent provides the actual Gateway Tailscale address, complete WebSocket
   URL, and active Gateway token separately (or the password for password mode).
6. Install the DEB/PKG/EXE and open **ClawPod Node**. Enter the supplied URL,
   display name, and token/password in their respective fields. Select
   **Save settings**, then **Start node**.
7. The agent identifies and approves your exact pending device request at the
   Gateway, then verifies that the device is connected.
8. Ask the agent to perform work on the connected computer through its node tools.

**Running** on the local setup page only means the local process has started.
It does not prove that the Gateway accepted authentication, approved pairing, or
connected the device. Use the Control UI's device/connection state for that.

The Gateway must be reachable from your computer. This guided connection flow
prepares Tailscale on both sides before starting the Node app. The Node package
does not bundle or install Tailscale.
For a plain Gateway listener on a private or Tailscale IP, use `ws://IP:PORT`,
for example `ws://100.64.1.2:18789`. These connections are always enabled, without
a checkbox. Localhost, `.localhost`, and `.local` names also support `ws://`.
Use `wss://` when the actual endpoint provides TLS. Other hostnames,
including Tailscale `.ts.net` names, require TLS in the app; use the Tailscale IP
for plain WebSocket access. Tailscale sign-in does not add TLS to the Gateway.

Node.js and the node-host runtime are included. A browser is not included: remote
browser automation needs a compatible browser installed on the computer. This
package does not run another AI agent or provision a Gateway.

## Daily use and removal

- Closing the setup browser tab leaves the node running.
- **Reconnect** restarts the node using saved settings.
- **Stop** stays in effect after reopening the app or signing in again. Choose
  **Start node** to resume.
- **Start when I sign in** uses your logged-in user account; it is not a system
  service that runs before login.
- Reinstalling the same app preserves its saved settings and device identity.

| Platform | Application | Removal |
| --- | --- | --- |
| Linux | `/opt/clawpod-node` | `sudo dpkg -r clawpod-node` |
| macOS | `/Applications/ClawPod Node.app` | Run `Uninstall ClawPod Node.command` in `Contents/Resources`, then move the app to Trash |
| Windows | `%LOCALAPPDATA%\ClawPodNode` | Uninstall **ClawPod Node** through Installed apps |

On shared Macs, each configured account should run the unregister command before
the shared application is deleted. Uninstallation retains the separate
`.clawpod-node` directory in your home folder for reinstall. It does not modify
your existing `.openclaw` installation. Use the app controls and removal steps above. Do not run both old and new installations for the same intended node
without checking which one is connected.

## Agent-assisted setup

Use the updated `clawpod-node-host` Skill with its linked Harness. For example,
through the agent's `cli_harness` tool, invoke the Harness command `installer.info`
with `platform` and `arch`. The CLI equivalent is:

```sh
clawpod-node-host --json installer info --platform macos --arch arm64
```

The response supplies the selected download, checksum, setup, and management
instructions. The agent should also look up and provide the Gateway host's actual
Tailscale DNS name/IP, the complete reachable WebSocket endpoint, and the actual
Gateway token separately, then show which app fields to fill. Password-mode
Gateways need the active password instead. These deployment values are obtained
with the agent's available tools; they are not part of the public manifest.
Selection is based on the user's computer, not the agent pod.
The Harness includes its release manifest, so this lookup requires neither a
checkout of this repository nor a network request. It does not claim a remote
download or Gateway connection was tested.

## Maintainers

See [release preparation](RELEASING.md). Installer source stays in the Agent
repository. This public repository carries download metadata, capability guidance,
and release assets. The installers contain distributable JavaScript runtime code,
dependencies, and license files; keeping the source repository private does not
hide the code shipped inside an installer.
