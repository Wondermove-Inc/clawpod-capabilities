# App operations and recovery

Use these controls for the standalone ClawPod Node app.

## Local controls

- Closing the setup browser tab leaves the node running. Reopening the app reuses its setup server.
- **Reconnect** restarts the node using saved settings.
- **Stop** persists across reopening the app and signing in again. Select **Start node** to reconnect.
- **Start when I sign in** registers startup for the current user and their logged-in desktop. It is not a pre-login system/root service.
- A blank authentication field preserves the saved secret only when the authentication mode is unchanged. Switching token/password modes requires a new value. **Clear the saved authentication value** stops the node.

Read timestamped local errors, check the saved endpoint/authentication mode, and compare with Gateway device status. Keep diagnostic evidence redacted. When the requesting user needs the active credential to reconnect, follow the verified credential handoff in [onboarding](onboarding.md). Local **Running** alone does not prove connection. Use `node-connect` when available for failures to connect or pair after correct setup.

## State, upgrade, and removal

The app keeps settings, Gateway authentication, device identity, and CLI state under `~/.clawpod-node` (`%USERPROFILE%\.clawpod-node` on Windows). It does not migrate or modify `~/.openclaw` or existing OpenClaw services.

| Platform | Application | Login startup | Removal |
| --- | --- | --- | --- |
| Linux | `/opt/clawpod-node` | systemd user unit `clawpod-node.service` | `sudo dpkg -r clawpod-node` |
| macOS | `/Applications/ClawPod Node.app` | LaunchAgent `cloud.clawpod.node` | Run `Uninstall ClawPod Node.command` in the app's `Contents/Resources`, then move the app to Trash. |
| Windows | `%LOCALAPPDATA%\ClawPodNode` | Scheduled task `ClawPod Node <account hash>` | Use Installed apps. |

On a shared Mac, each configured account must run the unregister command before the shared app is moved to Trash; that command unregisters only the current account.

Upgrades stop app processes before replacing files, preserve settings and identity, and attempt to resume previously active users. Removal unregisters startup and removes application files while retaining user settings for reinstall. Explain that preserving the state also preserves saved authentication and paired identity. Remove the separate app state directory only when the user's requested removal includes discarding those values; do not delete it as a routine repair or touch `~/.openclaw`.

Installer `0.1.0` contains runtime `2026.4.11`; the Skill and Harness are version `0.4.0`. An app upgrade uses a matching installer.
