# App operations and recovery

Use these controls for the standalone ClawPod Node app.

## Local controls

- Closing the setup browser tab leaves the node running. On macOS, Windows, and Linux, reopening the app opens the setup page in the default browser and reuses its server, including after a silent installer restart. It does not stop the running node.
- **Reconnect** restarts the node using saved settings.
- **Stop** persists across reopening the app and signing in again. Select **Start node** to reconnect.
- **Start when I sign in** registers startup for the current user and their logged-in desktop. It is not a pre-login system/root service.
- A blank authentication field preserves the saved secret only when the authentication mode is unchanged. Switching token/password modes requires a new value. **Clear the saved authentication value** stops the node.

Read timestamped local errors, check the saved endpoint/authentication mode, and compare with Gateway device status. Keep diagnostic evidence redacted. When the requesting user needs the active credential to reconnect, verify that the saved Gateway secret still matches the active credential, update the same pointer if it changed, and deliver it with `room_send.useSecrets` as described in [onboarding](onboarding.md). Tell the user to save the updated value in Node before reconnecting. Local **Running** alone does not prove connection. Use `node-connect` when available for failures to connect or pair after correct setup.

## State, upgrade, and removal

The app keeps settings, Gateway authentication, device identity, and CLI state under `~/.clawpod-node` (`%USERPROFILE%\.clawpod-node` on Windows). It does not migrate or modify `~/.openclaw` or existing OpenClaw services.

| Platform | Application | Login startup | Removal |
| --- | --- | --- | --- |
| Linux | `/opt/clawpod-node` | systemd user unit `clawpod-node.service` | `sudo dpkg -r clawpod-node` |
| macOS | `/Applications/ClawPod Node.app` | LaunchAgent `cloud.clawpod.node` | Run `Uninstall ClawPod Node.command` in the app's `Contents/Resources`, then move the app to Trash. |
| Windows | `%LOCALAPPDATA%\ClawPodNode` | Scheduled task `ClawPod Node <account hash>` | Use Installed apps. |

On a shared Mac, each configured account must run the unregister command before the shared app is moved to Trash; that command unregisters only the current account.

Upgrades stop app processes before replacing files, preserve settings and identity, and attempt to resume previously active users. Removal unregisters startup and removes application files while retaining user settings for reinstall. Explain that preserving the state also preserves saved authentication and paired identity. Remove the separate app state directory only when the user's requested removal includes discarding those values; do not delete it as a routine repair or touch `~/.openclaw`.

Installer `0.2.2` contains runtime `2026.4.11`; the Skill and Harness are version `0.7.3`. An app upgrade uses a matching installer. Updating this capability alone does not upgrade an installed Node or the Gateway Agent.


## Use the selected node

Use `nodes` with `action: "status"` to identify the connected Node ID. Inspect
its advertised capabilities; an older Gateway Agent or Node may not provide
`remote_computer` even though CLI commands work.

- GUI: call `remote_computer` with `action: "status"` and `node`, then `acquire` with the same `node`. Use the returned `frameId` as `frame_id` for input. Choose `display_id` if needed. Keep `node` on every call and `release` when finished or handing the desktop over.
- CLI: use `exec` with `host: "node"` and the selected `node`. No SSH server is needed. On macOS/Linux use `/bin/sh` syntax; on Windows use `cmd.exe` syntax or explicitly invoke PowerShell.
- Browser: use `browser` with `target: "node"` and `node`. The node needs a compatible installed browser and browser proxy capability.

`computer` always targets the agent pod, not the connected computer. Desktop
ownership coordinates `remote_computer` calls; it does not lock unrelated CLI or
browser work. People and other tools can change the screen, so inspect fresh
observations before acting. Main agents and workers must use their own acquisition
and returned frame; release the desktop before another session takes over.
Use `paste` for literal Korean, English, and other multilingual text. A successful
input response means input was delivered, not that the app accepted or saved it.
System audio and microphone capture are not included.

X11 needs a clipboard manager to preserve an existing clipboard during paste;
Wayland paste needs a Clipboard portal. If paste reports unavailable, distinguish
that from screenshot or other input availability instead of declaring the whole
desktop unavailable.

## Managed CLI execution

Update both the controlling Agent and ClawPod Node for managed execution. Node
0.2.1 and later advertise `system.process`; older nodes retain synchronous commands.
Use `background: true` for background work or `pty: true` for terminal programs.
When `exec` returns a running `sessionId`, use `process` with that handle for
status, logs, input, EOF, or cancellation. The handle keeps the selected node;
never replace this route with SSH or a command on the agent pod.

Worker completion returns to the worker that started the command, including
successful commands with no output. Cancellation/reset stops owned remote work.
A lost connection or restart invalidates process handles; inspect the actual
result before rerunning a command that may already have changed the computer.
GUI control and browser routing remain independent of this CLI lifecycle.
