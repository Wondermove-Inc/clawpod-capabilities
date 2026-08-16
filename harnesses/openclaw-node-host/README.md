# openclaw-node-host CLI Harness

Offline-first macOS/Windows node-host onboarding for exactly OpenClaw `2026.4.11`. The entrypoint uses only Python's standard library. Put the package directory on disk and invoke `openclaw_node_host.py`, or run `scripts/install.py --bin-dir <user-bin>` to create the `openclaw-node-host` command without network access or administrator access.

Default tests set `OPENCLAW_NODE_HOST_FIXTURE` and optionally `OPENCLAW_NODE_HOST_RECORD`; they never mutate a real service or network. Live service mutation additionally requires `OPENCLAW_NODE_HOST_DISPOSABLE_INTEGRATION=1` on an explicitly disposable supported host.

See `TEST.md` and the linked Skill for safety and routing boundaries.
