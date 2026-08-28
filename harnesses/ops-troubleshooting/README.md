# Ops Troubleshooting Harness

Canonical `ops-troubleshooting` / **Ops Troubleshooting** Harness. Version 0.1.0.

Bounded, read-only diagnostics for Linux hosts, networks, Kubernetes clusters, and security hygiene, plus plan-bound remediation for three allowlisted actions. Python 3 standard library only; no shell, no network beyond the tools it wraps.

## Contract

Every command emits one JSON envelope: `{ok, schemaVersion, command, data, effects}` on success, `{ok:false, …, error:{code, message, kind, details}}` on failure. `data.evidence` always records the exact `argv` of every external tool executed, its exit code, duration, truncation and timeout flags, whether redaction fired, and notes about degraded sections. Findings are typed (`severity`, `code`, `message`) so a Skill can act on them without parsing prose.

Exit codes: `0` ok · `2` invalid input · `3` tool unavailable · `4` confirmation required · `5` precondition failed · `6` tool/verify failure · `7` timeout.

### Read-only groups

| Group | Commands | Tools |
|---|---|---|
| `host.*` | `overview`, `disk`, `processes`, `services`, `journal` | `/proc`, `df`, `ps`, `systemctl`, `journalctl` |
| `net.*` | `ports`, `dns`, `reach` (+TLS), `route` | `ss`, resolver, sockets/ssl, `ip -j` |
| `security.*` | `logins`, `auth-events`, `users`, `updates` | `last`, `journalctl`, `/etc/passwd`+groups, `apt`/`dnf` |
| `change.*` | `recent` | `find` (allowlisted roots), apt history / `rpm -qa --last` |
| `k8s.*` | `context`, `nodes`, `pods`, `describe`, `logs`, `events`, `rollout` | `kubectl` (JSON output, `--request-timeout`) |
| `triage.*` | `host`, `k8s` | one bounded pass over the groups above; sections fail independently |

Bounds: per-tool timeout (default 15 s, max 60 s), text output ≤ 256 KiB, JSON ≤ 8 MiB, journal ≤ 500 lines, logs ≤ 1000 lines, events ≤ 200, pods ≤ 500, windows ≤ 30 days. Names, namespaces, units, selectors, and patterns are validated before they reach a tool. `k8s.describe` refuses Secrets and ConfigMaps; no command reads credential files or shadow contents. Text output is redacted for bearer tokens, `token=`/`password=` pairs, JWTs, and private keys; JSON is parsed unredacted and only summarized fields are emitted.

`--tool-root <dir>` pins every external tool to one directory (used by the tests and by operators who ship a vetted toolchain). Without it, tools resolve from `PATH`.

### Remediation

`remediate.plan --action <service.restart|k8s.rollout.restart|k8s.pod.delete> --target … [--namespace …]` snapshots the target's preconditions (unit load/active state; workload uid/generation/replicas/images; pod uid/owner) into an owner-only (`0600`) plan under `--state-root/plans/`, and returns a `confirmationChallenge` (SHA-256 over id, action, target, preconditions hash, expiry). Plans expire after 15 minutes. `k8s.pod.delete` refuses pods without a controller owner.

`remediate.apply --plan-id … --confirm …` re-reads the plan, requires the exact challenge, rejects expired or already-consumed plans, re-snapshots preconditions and fails closed on any drift, marks the plan consumed, runs exactly one action, then verifies (unit active; rollout status complete; owner recorded). The action is never retried. `effects` lists what changed; `data.rollback` states how to undo.

## Safety classes

All diagnostics are `readOnly`. `remediate.plan` is `readOnly` + `writeSafe` (writes only the plan file). `remediate.apply` is `writeSafe` + `externalSideEffect` and must run only with current approval bound to the plan.

## Development

`scripts/generate_manifest.py` renders `harness.json` from the option tables in `ops_troubleshooting.py`; `--check` verifies they agree. Tests: `python3 -m unittest tests.test_harness` from this directory (fake tools only, no host access).
