# Test contract

Run `python3 -m pytest harnesses/openclaw-node-host/tests`. Tests are fixture/recording-only, include installed-command subprocess coverage, and perform no network, Tailscale, service, pairing, npm, or OpenClaw mutation.

Explicit disposable-host integration is excluded from the default suite and requires `OPENCLAW_NODE_HOST_DISPOSABLE_INTEGRATION=1` plus separate operator approval.

## Verified results

- `python3 scripts/validate.py`: 40 capability entries validated.
- Relevant Harness, registry, version, routing, and Gateway-manifest tests: 38 passed with 40 subtests.
- The repository-wide pytest collection is currently blocked by the pre-existing installed `clawpod-cloud-webhooks` package shadowing source imports in three unrelated test modules. No `openclaw-node-host` test failed.
