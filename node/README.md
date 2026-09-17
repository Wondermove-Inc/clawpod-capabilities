# ClawPod Node downloads

Install ClawPod Node on your computer to connect it to an existing ClawPod Agent.
Download just the installer matching **that computer's** operating system and CPU.
You do not need access to the Agent source repository, npm, or a separate Node.js
installation. Installation is offline; connecting requires access to your Gateway.

## Download 0.2.4 preview

| Computer | Installer |
| --- | --- |
| Linux x64, Debian/Ubuntu desktop | [Download DEB](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.2.4/ClawPod-Node-0.2.4-linux-x64.deb) |
| macOS Apple Silicon | [Download PKG](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.2.4/ClawPod-Node-0.2.4-darwin-arm64.pkg) |
| macOS Intel | [Download PKG](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.2.4/ClawPod-Node-0.2.4-darwin-x64.pkg) |
| Windows x64 | [Download EXE](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/download/node-v0.2.4/ClawPod-Node-0.2.4-win32-x64.exe) |

[Release page and individual SHA-256 files](https://github.com/Wondermove-Inc/clawpod-capabilities/releases/tag/node-v0.2.4)
· [Release notes](RELEASE-NOTES-0.2.4.md)

Final installer hashes and exact byte sizes are recorded in
[release.json](release.json). See [validation scope](VALIDATION.md) for execution
coverage and remaining limits.

Version 0.2.4 improves accessibility observation of deeply nested controls and
reports scope, completeness, and limits instead of silently treating partial
results as complete. Update both the Node app and the controlling Agent.
Version 0.2.3 introduced monitor switching and shared image/observation coordinates.

Version 0.2.2 fixed opening the setup page from the app on macOS, Windows, and
Linux, including after a silent installer restart. Open the installed app to
show its settings in the default browser without stopping the existing node.

Version 0.2.1 introduced improvements to commands on the connected computer. The Agent can start
background commands, inspect output, provide terminal input, and cancel the same
execution through ClawPod Node. No SSH server is needed. Update the controlling
Agent as well as the Node app; updating this capability alone upgrades neither.
Existing remote desktop control and Desktop setup remain available.

Both Mac installers have verified Developer ID signatures, Apple notarization,
and stapled tickets, and passed Gatekeeper assessment. Windows publisher signing
is not included.

Private/Tailscale IP `ws://` support, app icons, saved settings, and device identity
are retained. Use `ws://` for a plain listener and `wss://` for an actual TLS endpoint.

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
6. Install the DEB/PKG/EXE and open **ClawPod Node**. Check **Desktop setup**
   using the OS guidance below. Enter the supplied URL,
   display name, and token/password in their respective fields. Select
   **Save settings**, then **Start node**.
7. The agent identifies and approves your exact pending device request at the
   Gateway, then verifies that the device is connected.
8. Ask the agent to work on the connected computer. It selects the Node ID and
   uses `remote_computer` for GUI, `exec host=node` for CLI, or `browser target=node`
   for a compatible installed browser. Every route selects the intended node;
   local `computer` still operates the agent pod.

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

## Desktop setup

| Platform | Required environment and setup |
| --- | --- |
| macOS | Allow **ClawPod Node** in Screen & System Audio Recording and Accessibility (Device Control & Data Access on macOS 27). These are normal OS permission requests owned by the installed app. |
| Windows | Use your logged-in, unlocked desktop. No macOS-style permission switch is needed. UAC/secure desktops and elevated windows may reject ordinary input. |
| Linux X11 | A reachable X display and XTest are required. The native helper requires glibc 2.36 or newer, such as Debian 12 or Ubuntu 24.04. |
| Linux Wayland | RemoteDesktop/ScreenCast portals are required. When control starts, choose a screen and approve input in the system sharing dialog. Real compositor validation is still pending. |

On Linux, accessibility `observe` requires a working session D-Bus and AT-SPI.
Missing accessibility services do not establish that screenshot or input is unavailable.

On macOS, use **Open settings** and **Check again** when a permission prompt does
not appear. If the switches are enabled but a fresh check still denies access
after an ad-hoc signed update, remove stale entries and add the current **ClawPod
Node** from Applications. An existing desktop session may need **Reconnect** after
grants change; this restarts the node, so coordinate it with active work.
There is no separate ClawPod Remote Computer app to install or grant permissions.
Desktop permission and Gateway pairing are separate: missing GUI permission does
not prevent configuring the CLI connection.

Clipboard paste on X11 needs a clipboard manager to preserve an existing
clipboard; Wayland paste needs the Clipboard portal. These paste limitations do
not mean all desktop observation or control is unavailable. The macOS permission
label mentions audio, but this release captures screens only.

## Switch monitors during remote desktop work

The agent keeps the explicit Node ID on every `remote_computer` call. After
acquiring the desktop, it switches monitors with a fresh `screenshot` or `observe`
request using `display_id` and omitting `frame_id`. Supplying the old monitor's
frame still returns `STALE_FRAME`. Subsequent inputs use the new response's
`frameId` as `frame_id` and coordinates within `viewport.imageWidth` × `viewport.imageHeight`, including
text-only observations. Do not rescale or add monitor offsets. Zoom attachment
pixels are not input coordinates. Release desktop
control before handing it to the user or another agent session.

Update both ClawPod Node to **0.2.4** and the controlling Agent. Skill/Harness
**0.7.5** supplies the updated guidance; installing it alone updates neither app.

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

## Accessibility observations

An `observe` query matches names or readable values, not element roles. Check
`observation.scope`, `complete`, and `reasons`; empty partial results do not prove
absence. Linux Wayland observations remain desktop-wide and coordinate-free.
Nodes without this metadata have unknown completeness. Use screenshots when an
application does not expose useful accessibility information.

Key input uses `text`, such as `Enter`, `meta+a`, or `ctrl+a`; literal multilingual
text uses `paste`. A Chrome installation is not required for remote GUI control.
Use an installed browser, and check compatible executable configuration before
using the separate `browser target=node` route.
