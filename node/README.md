# ClawPod Node downloads

Install ClawPod Node on your computer to connect it to an existing ClawPod Agent.
Download just the installer matching **that computer's** operating system and CPU.
You do not need access to the Agent source repository, npm, or a separate Node.js
installation. Installation is offline; connecting requires access to your Gateway.

## Download 0.1.0 preview

| Computer | Installer | Size |
| --- | --- | ---: |
| Linux x64, Debian/Ubuntu desktop | [Download DEB](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.1.0/ClawPod-Node-0.1.0-linux-x64.deb) | 161 MiB |
| macOS Apple Silicon | [Download PKG](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.1.0/ClawPod-Node-0.1.0-darwin-arm64.pkg) | 247 MiB |
| macOS Intel | [Download PKG](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.1.0/ClawPod-Node-0.1.0-darwin-x64.pkg) | 214 MiB |
| Windows x64 | [Download EXE](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.1.0/ClawPod-Node-0.1.0-win32-x64.exe) | 148 MiB |

[Release page and individual SHA-256 files](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/tag/node-v0.1.0)
· [Machine-readable versions, hashes, and exact byte sizes](release.json)

These initial installers are unsigned. macOS/Windows native installation and
desktop login startup have not yet been verified on those operating systems.
Linux offline installation, upgrade, and removal were verified in a Debian
container. See [validation scope](VALIDATION.md) before treating this preview as
a production-validated release.

## Install and connect

1. Install the downloaded file: open the PKG on macOS, run the EXE as your normal
   user on Windows, or use your desktop package installer on Debian/Ubuntu.
   Linux terminal alternative: `sudo dpkg -i ClawPod-Node-0.1.0-linux-x64.deb`.
2. Open **ClawPod Node** from your applications menu. A local setup page opens in
   your browser.
3. Enter the Gateway root WebSocket address, a display name for this computer,
   and the Gateway token or password supplied by your Agent administrator.
   Example address: `wss://gateway.example.com:18789`. Put the authentication
   value in its separate field. A Cloud room or dashboard URL is not a node endpoint.
4. Save settings and choose **Start node**.
5. In the Agent Control UI, identify this computer's actual pending device request
   and approve it. Confirm the device is connected before using it.

**Running** on the local setup page only means the local process has started.
It does not prove that the Gateway accepted authentication, approved pairing, or
connected the device. Use the Control UI's device/connection state for that.

The Gateway must be reachable from the remote computer. Use an existing suitable
route; Tailscale is an option when needed, not an installation prerequisite.
Use `wss://` for public and Tailscale endpoints. The app also accepts private-LAN
`ws://` addresses after you explicitly select that option. These are the existing
installer's connection rules, not a change to Gateway configuration.

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
your existing `.openclaw` installation. Legacy `openclaw node stop/uninstall`
commands do not manage this app's wrapper service; use the app and removal steps
above. Do not run both old and new installations for the same intended node
without checking which one is connected.

## Agent-assisted setup

Use the updated `clawpod-node-host` Skill with its linked Harness. For example,
through the agent's `cli_harness` tool, invoke the Harness command `installer.info`
with `platform` and `arch`. The CLI equivalent is:

```sh
clawpod-node-host --json installer info --platform macos --arch arm64
```

The response supplies the selected download, checksum, setup, and management
instructions. Selection is based on the user's computer, not the agent pod.
The Harness includes its release manifest, so this lookup requires neither a
checkout of this repository nor a network request. It does not claim a remote
download or Gateway connection was tested.

## Maintainers

See [release preparation](RELEASING.md). Installer source stays in the Agent
repository. This public repository carries download metadata, capability guidance,
and release assets. The installers contain distributable JavaScript runtime code,
dependencies, and license files; keeping the source repository private does not
hide the code shipped inside an installer.
