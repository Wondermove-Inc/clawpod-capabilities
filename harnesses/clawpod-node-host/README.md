# clawpod-node-host CLI Harness

Select a standalone ClawPod Node installer for Linux x64, macOS arm64/x64, or Windows x64, and guide its setup and daily operation. The entrypoint uses only Python's standard library. Put the package directory on disk and invoke `clawpod_node_host.py`, or run `scripts/install.py --bin-dir <user-bin>` to create the `clawpod-node-host` command without network access or administrator access.

```sh
python3 clawpod_node_host.py --json installer info \
  --platform macos --arch arm64 --gateway-url wss://gateway.example.com:18789
```

Use the target computer's platform and architecture, which may differ from the agent's host. `--gateway-url` is optional; when supplied it must be a credential-free WebSocket root URL. Dashboard paths, query strings, fragments, and embedded credentials are rejected. The app allows public/Tailscale endpoints over `wss://`, and private LAN `ws://` with explicit opt-in in the app. This installer path does not require Tailscale or a globally installed Node.js/OpenClaw.

`installer info` reads the package-local `installer-manifest.json` and returns the selected filename, SHA-256, byte size, pinned download URL, installer/runtime versions, release validation, and app-native instructions. It performs no network call or state mutation. `remoteAvailability: unchecked` means the output alone does not prove a release exists. Check the release before promising a download is available. The manifest is synchronized from `node/release.json` by the repository release tooling and travels with a standalone harness install.

Open the installed **ClawPod Node** app, enter the Gateway root URL and credential locally, save settings, and select **Start node**. Approve the matching device in the Agent Control UI and verify the connection there. **Running** in the app indicates the local process only. **Reconnect**, **Stop**, and **Start when I sign in** control this app. Its state lives in `.clawpod-node`; native removal instructions are returned for the selected platform.

Existing commands remain available for legacy macOS/Windows CLI installations pinned to OpenClaw `2026.4.11`. Their `install`, `service`, `repair`, `uninstall`, and enrollment commands do not manage the standalone app's separate state or startup service.

Legacy tests set `CLAWPOD_NODE_HOST_FIXTURE` and optionally `CLAWPOD_NODE_HOST_RECORD`; they never mutate a real service or network. Live service mutation additionally requires `CLAWPOD_NODE_HOST_DISPOSABLE_INTEGRATION=1` on an explicitly disposable supported host.

The `bootstrap` commands cover the pre-Node path. Remote behavior is fixture-driven unless the separate disposable integration gate is present; tests only record strict noninteractive SSH command shapes. Credentials are opaque protected references and are never read or persisted. `bootstrap generate` emits the deterministic credential-free local alternative.

See `TEST.md` and the linked Skill for safety and routing boundaries.
