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

Version 0.5.1 selects the Node 0.1.1 installers and matches their automatic
private/Tailscale IP `ws://` support. There is no private-connection checkbox.
For a plain listener, provide `ws://<Tailscale-IP>:<port>`; use `wss://` only for
an actual TLS endpoint. The legacy response field `privateWsOptInRequired`
remains present and is always false. Token/password handoff and exact device
approval are still required. Update both Skill and Harness to 0.5.1.

Version 0.5.1 fixes the 0.5.0 execution-preparation error
`input.gatewayUrl uses unsupported schema keyword description`. Gateway URL
guidance is in the command description, which the Agent runner supports.
The Node 0.1.1 installers and connection behavior are unchanged.

See `TEST.md` for fixture and real-process validation. No live Tailscale account
is changed by the test suite.
