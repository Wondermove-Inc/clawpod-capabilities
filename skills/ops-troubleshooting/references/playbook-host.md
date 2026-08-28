# Playbook — Linux host

Run `triage.host` first; then use the table for the finding code or symptom.

| Finding / symptom | Confirm with | Likely causes | Mitigation (approval class) | Verify |
|---|---|---|---|---|
| `ROOT_DISK_FULL`, `DISK_USAGE_HIGH` | `host.disk`; `change.recent --root /var/lib --since 1d`; `host.journal --pattern "No space left"` | logs, journal, container images, core dumps, runaway upload dir | Recommendation: rotate/vacuum logs, prune images, move data (human/other capability). No allowlisted action | `host.disk` below `warnPercent` |
| `INODE_USAGE_HIGH` | `host.disk` (inodes), `change.recent` on the mount | millions of small files (sessions, cache, mail queue) | Recommendation: delete the offending tree after owner confirms | `host.disk` inode percent drops |
| `MEMORY_LOW`, `SWAP_PRESSURE`, OOM lines in journal | `host.overview`, `host.processes --sort mem`, `host.journal --pattern "Out of memory"` | leak, undersized host, too many workers, cache growth | Allowlisted: `service.restart` of the leaking unit (mitigation only). Fix: limits, sizing | `host.overview` memory available recovers; no new OOM lines |
| `LOAD_ABOVE_CPUS` | `host.processes --sort cpu`, `host.journal` for the top command | runaway job, IO wait, cron storm | Recommendation: pause the job; `service.restart` only if the unit is the culprit | load returns below CPU count |
| `FAILED_UNITS`, `UNIT_NOT_ACTIVE` | `host.services --unit <unit>`, `host.journal --unit <unit> --since 1h` | bad config, missing dependency, port already in use, permissions | Allowlisted: `service.restart` **after** the journal explains the failure and the cause is addressed or transient | `host.services --unit` active, `NRestarts` stable |
| `UNIT_RESTART_LOOP` | as above with `--tail 200`; `net.ports` for port conflicts | crash on start, dependency flapping | Restarting a looping unit without a cause is not a fix — find the cause first | restart count stops increasing over 10 min |
| `ZOMBIE_PROCESSES` | `host.processes`, parent PID | parent not reaping children | Recommendation: restart the parent unit | zombies gone |
| Slow but nothing red | `host.overview` load/iowait proxy, `host.processes`, `net.dns` (slow DNS makes everything slow), `net.reach` to dependencies | DNS latency, dependency latency, disk saturation | Depends on cause | measured latency improves |
| Clock or certificate oddities | `net.reach --tls`, `host.journal --unit systemd-timesyncd` (or chrony) | time drift breaks TLS/auth | Recommendation: fix time sync | `net.reach --tls` verifies |

Notes:

- `host.journal` is capped at 500 lines; use `--unit`, `--priority err`, and `--pattern` rather than raising the tail.
- `security.updates` reports `REBOOT_REQUIRED`; a pending kernel/glibc update explains "it worked before the reboot" symptoms.
- Restarting a unit that failed due to configuration will fail again; the plan's rollback note says so.
