# Verification

Run `uv run --with pytest python -m pytest harnesses/clawpod-node-host/tests`.

- Agent status and sign-in: signed out, sign-in URL handoff, recheck to Running,
  already-connected no-op, stopped/authorization-pending states, missing CLI,
  malformed/status failures, login timeout, process cleanup, and failure output.
- Fake Tailscale executables exercise the real subprocess path; no live account
  or daemon is used. `CLAWPOD_NODE_HOST_FIXTURE` and command recording are optional
  local fixtures. Installer lookup ignores them and never initiates sign-in.
- All three command manifests are invoked through their real CLI mappings.
  Removed commands and arguments cannot generate scripts or mutate services.
- Four native installer targets, endpoint validation, independent package lookup,
  metadata/error handling, and local Harness wrapper registration remain covered.

Repository checks include Registry package installation, source/file inventories,
manifest synchronization, routing, and distribution asset integrity. Regenerate
`registry/index.json` using `python3 scripts/sync_registry.py` after package edits.
Version 0.7.3 points to Node 0.2.2 and tests automatic private/Tailscale IP ws://
acceptance, CIDR boundaries, and IPv4-mapped IPv6. These tests
are not proof of live Tailscale sign-in, Gateway pairing, or native OS installation.

The always-on repository test `tests/test_node_harness_schema.py` recursively
checks every command's input/output schema against the supported Agent execution
keywords. Manifest discovery and direct Python execution alone do not prove that
`cli_harness` can prepare a command.

With a local Agent source checkout and its dependencies installed, also run:

```sh
CLAWPOD_AGENT_SOURCE=/path/to/clawpod-agent python3 -m unittest discover -s tests -p test_node_harness_schema.py -v
```

This imports the actual Agent parser and prepare/run/output validator. It uses a
temporary installed package, prepares all three commands, and executes only the
read-only installer lookup for four targets with omitted, private ws, and TLS
URLs. It verifies that the old nested description reproduces the error both with
and without a URL, while missing inputs, wrong types, and unknown fields remain
rejected. It does not contact a Gateway, run Tailscale, or modify installed agents.
