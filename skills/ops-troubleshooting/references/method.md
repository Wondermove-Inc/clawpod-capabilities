# Troubleshooting method

## Intake

Write down, in one line each: symptom (as observed, not as interpreted), first-seen time, scope, user impact, what already changed recently, and who owns the system. If the first-seen time is unknown, the first job is to find it from evidence (journal, events, restart timestamps), because every window below is anchored on it.

## Hypothesis tree

Work the layers from cheapest evidence to most expensive, and try to *refute* each candidate before collecting more:

| Layer | Cheapest refuting check | Typical causes |
|---|---|---|
| Capacity | `host.overview`, `host.disk`, `k8s.nodes` | disk/inode full, memory pressure, CPU saturation, pod limits |
| Process/unit | `host.services --unit`, `k8s.pods` | crash loop, failed start, OOM kill, bad image |
| Network | `net.route`, `net.dns`, `net.reach` | no route, DNS failure, port closed, TLS expired |
| Change | `change.recent`, `k8s.rollout`, `security.updates` | deploy, config edit, package upgrade, certificate rotation |
| Dependency | `net.reach` to upstreams, `k8s.events` | database down, upstream rate limits, missing PVC |
| Security | `security.auth-events`, `security.users`, `net.ports` | brute force, unexpected account, new listener |

Stop widening when a hypothesis survives two independent signals and the others are refuted, or when the window reaches the last known-good state.

## Evidence rules

- Every claim in the report maps to a `data.evidence.commands[]` record (argv, time, host) or a quoted line from a bounded output.
- Windows: start at ±1 h around first-seen, widen to 24 h, then 7 d; never start at 30 d.
- Counts beat samples: restart counts, event counts, failed-auth counts. Quote at most a few representative lines.
- Findings are typed. Reason from `code` and `severity`; do not re-derive them from prose.
- Absence is evidence only when the check could have seen the thing (a clean `host.journal` with `--priority err` says nothing about warnings).
- Never paste secrets, tokens, or full config files into the room; the Harness redacts, and the report must not undo that.

## Correlating with change

Before proposing a fix, answer "what changed?" explicitly: `change.recent` (files, package operations), `k8s.rollout` (generation/revision, images), `security.updates` (pending vs applied), and the timestamps of failed units or first crash. A cause that predates the symptom needs a trigger; a change that coincides with the symptom needs a mechanism. Say which you have.

## Mitigate vs fix

- *Mitigate*: restore service quickly with a reversible, bounded action (restart, rollout restart, delete a managed pod, roll back a rollout). Prefer the smallest scope.
- *Fix*: remove the cause (limit, configuration, dependency, capacity). Usually needs a change process and an owner.

Both go in the report; only the mitigation may run through `remediate.*`, and only after approval.
