---
name: salesforce-org-change
description: Use only for explicitly authorized Salesforce org mutation, including deploy, retrieve, activation, data changes, permission assignment, endpoint probes, event publication, and cleanup.
---

# Salesforce Org Change

Capability: `salesforce-org-change`

Use this OpenClaw skill only when the requester has explicitly authorized Salesforce org mutation. Mutation includes deploy, retrieve that changes local source from org state, metadata update, activation/deactivation, data create/update/delete, permission assignment, live endpoint probe, event publication, and cleanup.

If mutation is not approved, provide a read-only mutation plan only. Do not interpret inspect, diagnose, review, plan, or verify as permission to mutate.

## Authorization Gate

Before any mutation planning or execution, read `references/request-intake.md` and `references/authorization-boundary.md`. Authorization must name the operation, target Salesforce org, scope, timing, success criteria, stop conditions, and rollback or cleanup boundary. If target or authorization is ambiguous, stop before mutation and request a decision.

This skill is not itself mutation authority. When the active `SOUL.md` or `WORKFLOW.md` requires a release boundary, pinned revision, QA/Security verdict, HITL result, or author/reviewer/executor separation for mutation, release, or execution, treat those as part of this gate. Requester authorization alone is not enough when those role or workflow gates apply.

## Mutation Safety

1. Verify target org identity with read-only evidence immediately before mutation.
2. Never rely on a default org. Pin every mutating command with `--target-org` or `-o`.
3. Do not use shell backticks, command substitution, globs, generated command strings, or unbounded paths for Salesforce mutation commands.
4. Prefer check-only or dry-run validation before actual mutation.
5. Keep deploy/retrieve, activation, data change, assignment, endpoint/event operation, and cleanup as separate units unless authorization explicitly combines them.
6. Preserve raw stdout/stderr, timestamp, exit code, exact command with secrets removed, IDs, and before/after state.
7. Use official first-party Salesforce sources for platform facts and record URL, API/release/CLI version or `not applicable`, and date confirmed.
8. Never expose secrets, credentials, tokens, customer payloads, or private record contents in source, evidence, prompts, or reports.
9. Route independent review to `salesforce-dev-review`.

## Check-only and actual deploy split

- Check-only/dry-run success is deploy-readiness evidence only. It is not approval for actual deploy.
- Actual deploy requires a separate explicit approval after check-only succeeds, unless the requester explicitly approved both the exact check-only and actual deploy operation together.
- Actual deploy must use the same approved target org, source revision or merge commit, component scope, and test set as the successful check-only. If any value changed, rerun check-only or stop for approval.
- A check-only no-go blocks actual deploy. First report failure evidence and impact analysis; do not repair, reroute, or deploy under this skill unless separately authorized.
- The deploy report must state validation id, actual deploy id when run, target org, source revision, tests, failures, coverage warnings, component errors, and whether scope matched the approved check-only.

## Reference Routing

| Mutation surface | Read |
| --- | --- |
| Intake, approval completeness, decision gate | `references/request-intake.md` |
| Authorization, target identity, command pinning, Case/Chatter tracking | `references/authorization-boundary.md` |
| Deploy, retrieve, check-only, metadata movement | `references/deploy-retrieve.md` |
| Activation/deactivation, data changes, assignments, cleanup, endpoint probes, event operations | `references/activation-data-cleanup.md` |
| Rollback planning, bounded cleanup, unintended mutation incidents | `references/rollback-incident.md` |
| Citation requirements | `references/citation-register.md` |

For technology-specific source concerns, read the matching distilled rules under `references/dev-rules/`. Stop before mutation when approval, target, scope, command, rollback/cleanup boundary, before-state evidence, or required reviewer direction is missing.
