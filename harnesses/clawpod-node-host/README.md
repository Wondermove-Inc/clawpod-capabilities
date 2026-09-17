# clawpod-node-host CLI Harness

Guide ClawPod Node app onboarding with three commands. The agent pod already has
Tailscale installed; this Harness checks its connection and initiates sign-in when
needed. Tailscale installation instructions apply to the user's computer.

| Command | Behavior |
| --- | --- |
| `agent.status` | Read agent Tailscale state. `NeedsLogin` asks for sign-in; `Running` advances to computer Tailscale setup. |
| `agent.login` | Return the agent's sign-in link, then recheck status. Already connected agents are unchanged. |
| `installer.info` | Select an offline installer by the user's OS/CPU and return setup/operation guidance. |

Use these commands through `cli_harness`, or invoke the Python entrypoint:

```sh
python3 clawpod_node_host.py --json agent status
python3 clawpod_node_host.py --json agent login
python3 clawpod_node_host.py --json installer info --platform macos --arch arm64
```

Follow the Skill's eight stages: agent Tailscale sign-in → computer Tailscale
installation/sign-in → OS/CPU confirmation → installer selection → actual Gateway
address/token handoff → user installs/starts Node app → exact device approval and
connection verification → node-tool use. Reuse stages already verified. Device
pairing uses Gateway tools; this Harness neither generates enrollment IDs nor
approves a request by a display name.

`installer.info` performs no network access, authentication, installation, or
state mutation. It reads `installer-manifest.json`, synchronized from
`node/release.json`, and returns the matching installer URL/hash/size. It can run
without Tailscale: stage ordering belongs to the Skill, not metadata lookup.
It reports `remoteAvailability: unchecked`. An optional `--gateway-url` checks the
app's existing root-WebSocket contract; it does not test endpoint reachability.
The agent obtains actual Gateway Tailscale addresses, endpoint, and token/password
with available authorized tools. Follow the Skill to store a missing Gateway secret,
update the same pointer when the active value changes, and reuse it when unchanged.
The main delivers the value to the requesting user through `room_send.useSecrets`,
with the pointer and placeholder in tool arguments and plaintext only in the
delivered room message. Workers report to the main instead of sending to rooms.
Gateway `config.get` and `openclaw config get` redact credentials.

The package uses Python's standard library. `scripts/install.py --bin-dir <dir>`
creates only the local **Harness command wrapper**, for callers wanting a
`clawpod-node-host` executable. It does not generate a node installation script.

Version 0.7.5 adds Node 0.2.4 accessibility completeness, image-coordinate,
and key-input guidance. Installer checksums and signing status come from the bundled manifest.
Gateway secret storage, rotation, and room delivery remain unchanged.
Managed CLI and OS-specific Desktop setup guidance remain available.
All desktop components are included in ClawPod Node. macOS grants belong to
ClawPod Node; Windows and Linux use their interactive desktop facilities.
The existing automatic private/Tailscale IP `ws://` behavior, token/password
handoff, command schemas, and exact device approval remain unchanged.
Update both Skill and Harness to 0.7.5. Update the Node app to 0.2.4 and the
controlling Agent as well for the corrected `remote_computer` behavior.

Node GUI work uses `remote_computer` with an explicit `node`; CLI uses
`exec host=node` with `node`, and browser uses `target=node` with `node`.
To switch monitors, request a fresh screenshot or observe with `display_id` and
omit `frame_id`. The old monitor's frame still returns `STALE_FRAME`. Use the new
response's `frameId` as `frame_id` and coordinates within viewport.imageWidth × viewport.imageHeight for input. Text-only and image observations of the
same display share full-viewport coordinates. Release before handing the desktop
over. The Skill explains acquisition and OS permission recovery. Local
`computer` remains the agent pod desktop. System audio is not captured.

See `TEST.md` for fixture and real-process validation. No live Tailscale account
is changed by the test suite.

For managed CLI, update the controlling Agent as well as Node. Use `exec` with
`host: "node"` and the target `node`, then `process` with the returned handle for
background status, output, terminal input, and cancellation. No SSH is required.

Accessibility queries match names or readable values, not roles. Check the
returned observation scope, completeness, and reasons before treating an empty
result as absence. See the Skill operations reference for partial results and
key input through the text field.
