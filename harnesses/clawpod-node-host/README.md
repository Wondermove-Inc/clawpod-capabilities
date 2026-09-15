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
with available authorized tools and supplies them separately to the user.
Gateway `config.get` and `openclaw config get` redact credentials.

The package uses Python's standard library. `scripts/install.py --bin-dir <dir>`
creates only the local **Harness command wrapper**, for callers wanting a
`clawpod-node-host` executable. It does not generate a node installation script.

Version 0.6.0 selects Node 0.2.0 and adds OS-specific Desktop setup guidance.
All desktop components are included in ClawPod Node. macOS grants belong to
ClawPod Node; Windows and Linux use their interactive desktop facilities.
The existing automatic private/Tailscale IP `ws://` behavior, token/password
handoff, command schemas, and exact device approval remain unchanged.
Update both Skill and Harness to 0.6.0. Update the Node app separately; the
Gateway Agent must also provide the new `remote_computer` tool for GUI work.

Node GUI work uses `remote_computer` with an explicit `node`; CLI uses
`exec host=node` with `node`, and browser uses `target=node` with `node`.
The Skill explains acquire/frame/release and OS permission recovery. Local
`computer` remains the agent pod desktop. System audio is not captured.

See `TEST.md` for fixture and real-process validation. No live Tailscale account
is changed by the test suite.
