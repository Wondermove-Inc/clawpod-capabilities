---
name: ops-troubleshooting
description: "Use to troubleshoot Linux host, network, Kubernetes, and security-hygiene problems with bounded read-only diagnostics that record every command as evidence, then run plan-bound remediation (service restart, rollout restart, managed-pod delete) immediately with the plan's own confirmation. Use soc-event-correlation for attack-story analysis, org-operations for incident reporting, and node-host for node onboarding."
---

# Ops Troubleshooting

Take an operational symptom — "the server is slow", "the pod keeps restarting", "the certificate alert fired", "someone is hammering SSH" — to a confirmed cause, a safe fix, and verified recovery. This Skill supplies the method and the playbooks; the linked Harness (v0.1.0) supplies bounded, evidence-recorded diagnostics and plan-bound remediation. Diagnosis is autonomous. Change is not.

## Boundaries

- **Read-only is autonomous.** Every `host.*`, `net.*`, `security.*`, `change.*`, `k8s.*`, and `triage.*` command may run without asking. They mutate nothing, never read secret material, and cap their own output.
- **Change is plan-bound, not approval-bound.** The only mutations are `remediate.plan` → `remediate.apply`, chained by the agent in the same turn, for `service.restart`, `k8s.rollout.restart`, and `k8s.pod.delete` (managed pods only). Anything else — config edits, scaling, package changes, node drains, firewall rules, credential rotation — is a recommendation with a rollback note, executed by a human or by a separately approved capability.
- **Security incidents are not yours to conclude.** If evidence suggests compromise rather than misconfiguration (unexpected uid 0 accounts, successful logins from unknown sources, changed sudoers or sshd_config, unexplained listeners), stop remediation, preserve evidence, and hand the analysis to `soc-event-correlation`; report through `clawpod-org-operations` SOC/CSIRT templates.
- Use `clawpod-node-host` for installing, pairing, or repairing a ClawPod node; use this Skill for why a host or cluster is unhealthy.

## Prerequisites

- The Harness is installed and trusted, and the diagnostics run where the symptom is: on the host itself, or with a `kubeconfig`/context that can read the cluster. Confirm with `version` and, for clusters, `k8s.context` (it reports read permissions).
- For remediation, an owner-only state root (`--state-root`, mode 0700) that persists between plan and apply.
- No credentials are ever passed to or printed by this Skill. A kubeconfig is referenced by path only.

## Procedure

1. **Intake and classify.** Restate the symptom, scope (one host, one workload, whole cluster), impact, and urgency. Decide the lane: infrastructure fault, capacity, configuration/change, or security. Read [method.md](references/method.md) for the hypothesis tree and evidence rules.
2. **First pass with triage.** Run `triage.host` on the affected host and/or `triage.k8s` for the cluster (`--namespace` when known, else `--all-namespaces`). Read the `findings` list, not the raw sections. Findings carry `severity` and a stable `code`; the playbooks index on those codes.
3. **Pick the playbook that matches the top finding or the symptom** and follow its check → cause → fix → verify table:
   - [playbook-host.md](references/playbook-host.md) — CPU, memory, swap, disk/inodes, failed units, restart loops, OOM, zombies
   - [playbook-network.md](references/playbook-network.md) — DNS, routes, interfaces, reachability, TLS expiry and chain, exposed ports
   - [playbook-kubernetes.md](references/playbook-kubernetes.md) — CrashLoopBackOff, OOMKilled, ImagePull, Pending/Unschedulable, NotReady nodes, stalled rollouts, warning events
   - [playbook-security-hygiene.md](references/playbook-security-hygiene.md) — brute force, unexpected accounts, admin groups, authorized keys, pending security updates, reboot required
   - [playbook-change-and-config.md](references/playbook-change-and-config.md) — "what changed?": recent files, package operations, rollout history, generation drift
4. **Collect targeted evidence** with the narrowest command that can refute the leading hypothesis: one unit's state before a journal dump, one pod's logs before a namespace's events, `--since` windows that start at ±1 h around the symptom and widen deliberately. Every response's `data.evidence.commands` is the audit trail — keep it.
5. **Confirm the cause** with at least two independent signals (for example a finding plus a matching journal or event line), and correlate with change evidence. State facts separately from inference.
6. **Decide the fix.** Separate *mitigate now* from *fix properly*. Check [remediation-boundary.md](references/remediation-boundary.md): if the mitigation is one of the three allowlisted actions, run `remediate.plan` and apply it immediately (report the plan's target, preconditions, commands, and rollback as part of the same message). Otherwise write the recommendation with exact commands, blast radius, and rollback, and stop.
7. **Apply in the same turn** with `remediate.apply --plan-id … --confirm <confirmationChallenge>` — take the challenge from the plan output yourself; never wait, so the plan cannot expire. The Harness re-checks preconditions and refuses stale, expired, or reused plans; treat any refusal as "re-plan", never as "retry".
8. **Verify recovery** by re-running the diagnostic that first showed the finding, and watch for regression over a short window (restart counts, rollout status, journal errors). Recovery is claimed only from a clean re-run.
9. **Report** per [reporting.md](references/reporting.md): timeline, evidence, cause, action, verification, follow-ups. Route to `clawpod-org-operations` templates for handoffs and incident updates; publish a durable write-up with `artifact-design` when the room benefits from a reusable document.

## Verification

Before saying a problem is resolved:

- The original finding code is absent from a fresh run of the same command.
- For remediation, `remediate.apply` returned `ok:true` with `verified:true`, and the `effects` list names exactly one action.
- The report cites the evidence records (command, time, host) for both the diagnosis and the verification.

## Failure handling

- `TOOL_UNAVAILABLE` (exit 3) → the host lacks that tool; use the nearest playbook alternative or report the gap. Do not install packages to diagnose.
- `TIMEOUT` (exit 7) → the tool hung; shrink the window or scope before retrying once. A hanging `kubectl` is itself evidence — check `k8s.context` and API reachability.
- `PLAN_STALE`, `PLAN_EXPIRED`, `PLAN_CONSUMED`, `CONFIRMATION_MISMATCH` → the world changed; re-plan and re-apply in one turn. Never edit a plan file.
- `VERIFY_FAILED` after apply → the action ran but recovery is unconfirmed; follow the plan's `rollback` note, collect fresh evidence, and escalate. Do not apply the same action again.
- Evidence points to compromise → stop, preserve, hand off (see Boundaries).
