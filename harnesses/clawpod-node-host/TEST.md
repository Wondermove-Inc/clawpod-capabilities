# Test contract

Run `python3 -m pytest harnesses/clawpod-node-host/tests`. The default suite uses fixtures, command recording, and temporary fake provider executables. It performs no network, Tailscale, real service, pairing, npm, or OpenClaw mutation.

Real disposable-host integration remains excluded and requires `CLAWPOD_NODE_HOST_DISPOSABLE_INTEGRATION=1` plus separate operator approval. The fake-provider tests exercise the same bounded timeout/retry path without touching a host service.

## Adversarial coverage

- macOS and Windows 11 provider selection, explicit Linux rejection
- Tailscale human-assisted install/login, same-tailnet and Tailscale-IP gates, stale evidence, and unreachable Gateway
- Node.js below 22.14, exact OpenClaw pinning, install resolution drift, installed-version drift, and service PATH/version mismatch
- plan/confirmation binding and expiry, invalid input, interrupted-state resume, idempotent install/rollback, stale pairing, nested redaction
- provider failure timeout and bounded retry, supported restart mapping, system/browser probe command selection
- bootstrap success, missing SSH, authentication failure, strict host-key mismatch, bounded timeout, partial stage resume, permission denial, protected-reference redaction, deterministic local generation, retry/idempotency
- three positive routing examples, at least two negative examples, and collisions with node-connect, routine connected-node operations, Tailscale installation, Gateway installation, and desktop

## Environment limitations and completion plan

The CI-safe suite does not assert real launchd or Windows Task Scheduler side effects. Those are intentionally deferred to separately approved disposable macOS and Windows 11 hosts. Completion there is: run the exact same plan/apply/validate/rollback flow, capture provider-native status before and after, interrupt once between provider install and state commit, then verify resume and cleanup. Production hosts and real Tailscale state are never test targets.
