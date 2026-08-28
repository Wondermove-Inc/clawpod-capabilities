# Playbook — security hygiene

This playbook covers *hygiene and misconfiguration*. The moment evidence points to an intrusion, switch lanes: stop remediation, keep the Harness outputs (they contain command records and timestamps), and hand the analysis to `soc-event-correlation`; coordinate through `clawpod-org-operations` SOC/CSIRT templates.

| Finding / symptom | Confirm with | Hygiene cause | Action | Compromise signal → hand off |
|---|---|---|---|---|
| `BRUTE_FORCE_SOURCE`, `AUTH_FAILURE_VOLUME` | `security.auth-events --since 1d` (`topFailedSources`, `acceptedByUser`) | SSH exposed to the internet with password auth | Recommendation: key-only auth, fail2ban/firewall, move port behind VPN/Tailscale | any `accepted` login from a top failed source, or for an unexpected user |
| `MULTIPLE_UID0` | `security.users` | leftover admin/service account | Recommendation: remove or lock; verify with owner | an account nobody recognises |
| `SHADOW_PERMISSIONS`, sensitive file mtimes | `security.users.sensitiveFiles`, `change.recent --root /etc` | package upgrade, manual edit | Recommendation: restore mode; diff against config management | `/etc/sudoers` or `sshd_config` changed at an unexplained time |
| Admin group membership | `security.users.adminGroups` (`sudo`, `wheel`, `docker`) | onboarding drift | Recommendation: review against the access list | member added recently with no ticket |
| `authorizedKeys` counts | `security.users.interactiveAccounts[].authorizedKeys` | shared accounts accumulate keys | Recommendation: prune, rotate | a new key on root or a service account |
| `SECURITY_UPDATES_PENDING`, `REBOOT_REQUIRED` | `security.updates` | patch cadence | Recommendation: schedule patch window (package changes are not allowlisted) | — |
| Unexpected listener / process | `net.ports`, `host.processes`, `change.recent` | debug tooling, new service | Recommendation: close or document | binary in `/tmp`, `/dev/shm`, or a user home |
| Unexplained cron or unit | `change.recent --root /var/spool/cron`, `host.services` | automation drift | Recommendation: document or remove | persistence mechanism nobody set up |

Rules:

- The Harness never reads `/etc/shadow` contents, private keys, or credential files; it reports metadata (mode, mtime, counts) only. Keep it that way in the report.
- Do not lock accounts, kill processes, or change firewall rules from this Skill; those are recommendations for a human or a separately approved capability.
- Preserve evidence order: collect `security.*` and `change.recent` *before* any restart, because restarts rotate logs and reset process tables.
