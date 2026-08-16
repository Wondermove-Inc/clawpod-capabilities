# clawpod-node-host CLI Harness

Offline-first macOS/Windows node-host onboarding for exactly OpenClaw `2026.4.11`. The entrypoint uses only Python's standard library. Put the package directory on disk and invoke `clawpod_node_host.py`, or run `scripts/install.py --bin-dir <user-bin>` to create the `clawpod-node-host` command without network access or administrator access.

Default tests set `CLAWPOD_NODE_HOST_FIXTURE` and optionally `CLAWPOD_NODE_HOST_RECORD`; they never mutate a real service or network. Live service mutation additionally requires `CLAWPOD_NODE_HOST_DISPOSABLE_INTEGRATION=1` on an explicitly disposable supported host.

The `bootstrap` commands cover the pre-Node path. Remote behavior is fixture-driven unless the separate disposable integration gate is present; tests only record strict noninteractive SSH command shapes. Credentials are opaque protected references and are never read or persisted. `bootstrap generate` emits the deterministic credential-free local alternative.

See `TEST.md` and the linked Skill for safety and routing boundaries.
