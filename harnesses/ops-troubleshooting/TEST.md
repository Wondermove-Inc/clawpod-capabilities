# Ops Troubleshooting validation evidence

Validated on 2026-08-28. Unit tests use fake `kubectl`, `systemctl`, `journalctl`, `ss`, `df`, `ps`, `ip`, `last`, `find`, and `apt` executables installed into a temporary `--tool-root`; no test inspects or mutates the real host or cluster. Read-only commands were additionally smoke-run against a real Ubuntu 24.04 host with a k3s v1.34 cluster (no remediation applied).

## Commands and results

- `python3 -m unittest tests.test_harness` (from `harnesses/ops-troubleshooting`) → `33 passed`
- `python3 scripts/generate_manifest.py --check` → `harness.json is current`
- `python3 scripts/sync_registry.py --check` and `python3 scripts/validate.py` → see repository CI
- Real-host smoke (read-only): `version`, `host.overview`, `host.disk`, `host.processes`, `host.services [--unit k3s]`, `host.journal --since -10m --priority err`, `net.ports`, `net.dns`, `net.route`, `net.reach --tls` (self-signed k3s API: certificate decoded, `TLS_VERIFY_FAILED` finding), `security.*`, `change.recent`, `k8s.context/nodes/pods/events/describe/logs/rollout`, `triage.host`, `triage.k8s`, `remediate.plan` (plan file written 0600; nothing applied) → all `ok:true`

## Coverage

- Envelope shape, evidence records, version self-report, manifest/CLI sync, safety classes (only `remediate.apply` carries `externalSideEffect`).
- Fail-closed inputs: missing required option, bad tool root, unavailable tool (exit 3), timeout (exit 7), invalid window, oversized tail capped, disallowed change root, namespace/selector validation, disallowed describe kinds (Secrets/ConfigMaps never reach kubectl).
- Findings: disk/inode thresholds, failed units and restart loops, zombie processes, exposed ports, missing default route and down interfaces, brute-force sources, pending security updates, CrashLoopBackOff/OOMKilled/Unschedulable pods, NotReady/MemoryPressure nodes, stalled rollouts.
- Redaction: secrets in journal lines, describe output, and event messages are replaced; JSON parsing is not corrupted by redaction.
- Triage: sections fail independently and are noted in evidence.
- Remediation: plan is 0600 and mutates nothing; apply requires the exact challenge; expired plans, consumed plans, stale preconditions (generation drift), unmanaged pods, and non-0700 state roots are rejected before any action; success path runs the action exactly once and verifies.

## Known limits

- Linux only (`/proc`, systemd, iproute2). macOS/Windows hosts are out of scope for 0.1.0.
- `net.reach --tls` decodes untrusted certificates through CPython's private `_test_decode_cert`; if it is absent, only the fingerprint and error are reported.
- `security.updates` supports apt and dnf; other package managers return `UNSUPPORTED_PACKAGE_MANAGER`.
