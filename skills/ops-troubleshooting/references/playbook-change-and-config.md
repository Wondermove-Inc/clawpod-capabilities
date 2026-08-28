# Playbook — "what changed?"

Most incidents are changes. Establish the change timeline before proposing a fix.

| Question | Command | What to read |
|---|---|---|
| Which files changed on the host recently? | `change.recent --root /etc --since 1d` (also `/opt`, `/usr/local`, `/var/lib`, `/home`) | `files[]` sorted by mtime; anything within minutes of first-seen |
| Which packages were installed/upgraded? | `change.recent` (`recentPackageOperations` from apt history or `rpm -qa --last`) | commandline + time |
| Is a reboot or security update pending? | `security.updates` | `rebootRequired`, `securityCount` |
| Did a service restart or fail at the symptom time? | `host.services --unit <unit>` (`ExecMainStartTimestamp`, `NRestarts`), `host.journal --unit <unit> --since 6h` | first failure line and what preceded it |
| Did a workload roll out? | `k8s.rollout --name <workload>` (`generation`, `observedGeneration`, `history`, `images`) | image tag change, revision count, `Progressing` condition |
| Did a node change? | `k8s.nodes` (`kubeletVersion`, taints, `unschedulable`), on node `change.recent` | cordon/drain, version skew |
| Did certificates rotate? | `net.reach --tls` (`notBefore`) | a `notBefore` after the symptom start means a rotation that clients may not trust |
| Did DNS or routes change? | `net.dns`, `net.route` | nameserver list, default route gateway |

Reasoning rules:

- Coincidence in time is a lead, not a cause; name the mechanism (for example "sshd_config changed at 10:02, sshd restarted at 10:02, failed logins begin 10:03").
- A change without an owner is a finding on its own; report it.
- Rollback options are part of the change record: package downgrade, config restore from management, `kubectl rollout undo`. None are allowlisted here; they are recommendations with exact commands.
