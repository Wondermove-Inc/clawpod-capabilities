---
name: "leader-workboard-delegation"
description: "Use for leader delegation routing through Tasks-first delivery, with Workboard limited to private progress."
---

# Tasks-first Leader Delegation Routing

Use this skill whenever a leader or coordinating agent delegates work to a practitioner agent. First classify the delegation route. Use Track A only for clearly immediate, low-risk direct delegation. Use Track B for Tasks-governed delegation and team-visible execution records.

This skill is a delegation routing skill. It does not authorize production, external, destructive, credential, secret-bearing, legal, payment, release, failed-gate-risk, Salesforce org mutation, or approval-sensitive actions.

## Leader boundary quick rules

- The Leader does not implement, technically review, merge, check-only validate, deploy, or perform Salesforce org mutation.
- Do not use hidden subagents, private coding helpers, or non-visible workers as official Development, QA, Security, or DevOps performers. If an internal helper is needed for non-authoritative analysis, disclose it and get approval first.
- Official practitioner work must be routed to the named/assigned practitioner on the visible delivery surface, with scope, non-goals, evidence, and stop conditions.
- A QA/DevOps/Security no-go or failed validation does not authorize immediate remediation. First run failure impact analysis, report options to the requester/Leader, and wait for the needed approval.
- Leader reports should be short: conclusion, risk/blocker, options, recommendation, and exact approval/input needed. Avoid long evidence dumps unless requested.

## Source of truth rule

- **Tasks is the practitioner-visible system of record** for Track B delegation, handoff, evidence, status, and closeout.
- **Workboard is private scratch/progress tracking only** unless the local workspace operating procedure explicitly says otherwise for the current agent's own work.
- Do not rely on Workboard for practitioner delivery, cross-agent visibility, or completion evidence.
- Do not build Workboard-to-Tasks sync, cross-agent Workboard discovery, secret/token passing, or hidden coordination mechanisms. In this repo/workspace, Tasks-first routing is unconditional for practitioner-visible Track B delivery.
- Room/chat messages are delivery or fallback evidence surfaces only. Backfill durable state to the governing Task.

## Routing decision

### Track A, direct delegation

Use Track A only when **all** of the following are true:

1. A single practitioner can complete the work immediately.
2. The work is read-only or has no material impact.
3. No plan review is needed to bound risk.

Material impact includes external-state mutation, production systems, code or configuration change, cost commitment, customer-facing, legal, privacy/data, release, Salesforce org action, or security-sensitive impact.

If any criterion is uncertain or false, route to Track B. Ambiguity fails to Tasks-governed delegation.

Track A requirements:

- No Task is required for the practitioner assignment.
- The leader delegates directly with bounded scope and expected result, supplying only the execution context defined in the leader procedure (step 2) and only the parts of it that remove ambiguity for this assignment.
- The practitioner reports the result directly to the leader.
- Before acting, the practitioner checks only the required supplied context against the actual execution environment. Preserve pre-existing modifications. If required context is missing, stale, or mismatched, stop and report the mismatch to the leader; do not guess paths, branch, HEAD, target org, or approval state.
- If mutation, material impact, classification doubt, or plan-review need appears, the practitioner stops and reports to the leader. The leader creates or updates Track B Task(s) before work resumes.
- Practitioners do not create their own escalation Tasks by default unless the leader or operating procedure explicitly assigns that responsibility.

### Track B, Tasks-governed delegation

Use Track B when any of the following is true:

- Track A criteria do not all hold.
- The work is multi-step or involves more than one practitioner.
- The work has material impact.
- The leader cannot confidently classify the work.
- The leader must verify practitioner evidence before final reporting.
- Work may continue after the current turn.
- Preventing orphan practitioner work records matters.
- Salesforce org action, source/config change, QA, Security, DevOps, HITL, release, credential, or approval boundary may be involved.

## Track B core rule

Use **leader-created or leader-accepted Tasks** as the governing execution records by default.

Do **not** use Workboard parent/child links as the practitioner delivery model. In this workspace Workboard is private per-agent progress, and historical parent/child dependency mechanics can block claim/complete. Workboard may mirror progress privately, but it is not the team delivery source of truth.

## Required Track B leader procedure

1. Create or identify the leader coordination Task.
   - The leader Task tracks request source, scope, non-goals, source of truth, role owners, evidence requirements, human-gate state, approval boundary, and closeout condition.
2. Create or accept each practitioner execution Task.
   - Set the assignee to the practitioner agent.
   - Set reporter according to the Tasks API requirements and workspace policy. If an API constraint requires a non-leader reporter for a leader-owned Task, record that this is an API compliance formality and does not transfer authority.
   - Use the shared milestone/project namespace when applicable.
   - Add labels for organization, role, trace, and task type.
   - Put the leader coordination Task id, delegated-by agent id, practitioner agent id, role owner, scope, non-goals, input artifact, output artifact, done-when criteria, evidence requirements, report-back target, approval/human-gate state, and next review owner in the Task description, plan, or comments.
   - Record only the execution context necessary for the assignment. Use fields such as practitioner/role, `repository_path`, `allowed_change_paths`, `target_org_alias` only for applicable authorized org-bound work, `approval_boundary`, constraints/non-goals, `evidence_required`, `stop_conditions`, and `report_back_target`; add `current_branch`, `current_head`, `expected_base_revision`, and `pre_existing_modified_files` only when source/config mutation or review depends on revision ownership.
3. Immediately record the practitioner Task id on the leader coordination Task.
4. Notify the practitioner with the Task id and bounded instructions.
5. Track status by reading the governing Task ids explicitly recorded on the leader Task.
6. Review practitioner comments, attachments, links, and evidence before reporting completion.
7. Complete the leader Task only after execution evidence and final reporting are complete, or record the blocker with owner/reason/next action and a wake/follow-up condition. Before completing, run `scripts/task-closeout-gate.py` against the practitioner's closeout report export and proceed only on exit 0.

## Tasks visibility recovery

Use this only when a governing Task should exist but the practitioner cannot see or update it.

Leader-only recovery mechanics:

1. Keep the intended Task id or leader coordination Task as the governing work id. Do not reclassify the work as Track A and do not treat chat delivery as completion.
2. Record the visibility failure on the leader Task when accessible. If the leader Task is also inaccessible, record the failure on the leader's available system of record and backfill later.
3. Designate a temporary evidence surface, such as the assigned room, only for the affected Task and only until Task access or leader backfill is restored.
4. Instruct the practitioner to report the blocker, result, proportional evidence, residual risk, and next action on that temporary surface without expanding scope or authority.
5. Backfill the Task with the temporary evidence, affected practitioner, visibility blocker, and recovery status as soon as the leader has access.
6. Close or block the governed Task only after the backfilled evidence satisfies the original scope and proportional evidence requirements.

This recovery path is an evidence transport fallback only. It does not grant Leader HITL approval, QA/Security verdict, no-go override, mutation, release, execution, credential, or secret-handling authority.

## Practitioner artifact submission default

For Track B assignments that produce repository artifacts, source changes, configuration files, tests, or durable documentation, use branch, commit, and pull request submission by default. Treat patches, file attachments, or chat-pasted diffs as fallback evidence only when repository push, PR creation, Task access, or network permissions are blocked.

Leader procedure for PR-based practitioner delivery:

1. Assign a bounded repository scope before edits begin: base branch or expected base revision, allowed change paths, non-goals, validation required, report-back room/Task, and explicit no-org-mutation/no-plaintext-secret constraints.
2. Require plan-before-edit when the work has material impact, source/config changes, or review gates. The practitioner must wait for leader approval before editing outside pre-approved scope.
3. Require the practitioner to create a branch from the approved latest base, apply only the approved scope, validate, commit, push, and open a PR.
4. Require the PR body or Task/room report to include scope, changed files, validation commands/results, residual risk, blocker status, and confirmation that no Salesforce org mutation and no plaintext credential/token/session/auth URL exposure occurred.
5. Review the PR diff and evidence before accepting or merging. If QA, Security, DevOps, HITL, or role-owner review is triggered, record the required verdicts before acceptance.
6. After merge or rejection, record the PR URL, head commit, merge commit when applicable, validation evidence, residual risk, and closeout state on the governing Task or approved fallback evidence surface.

This PR-based default is a delivery and review surface. It does not grant practitioners authority to expand scope, bypass plan approval, skip required gates, mutate Salesforce orgs, expose secrets, or merge their own work without leader authorization.

## Required Track B practitioner procedure

1. Read the assigned execution Task.
2. Read the leader coordination Task only for context when needed.
3. Before acting, validate only the supplied context required for the assignment, such as path, allowed-change boundary, target org, approval state, or revision fields when they were explicitly provided. Preserve pre-existing modifications; confirm them only when source/config mutation or review depends on revision ownership.
4. Set or confirm the Task status according to workspace procedure.
5. For repository artifact work, use branch, commit, and PR delivery by default after plan approval. Keep edits within the approved scope and report PR URL, changed files, validation, residual risk, and no-org-mutation/no-secret-exposure confirmation.
6. Do not mutate the leader coordination Task unless explicitly instructed.
7. Do not create a new execution Task unless explicitly instructed or required by workspace procedure. On missing, stale, or mismatched required context, do not guess or proceed: record the mismatch and stop for leader direction. On out-of-scope discovery, mutation, material impact, or classification doubt, stop and report to the leader for Track B routing or re-routing.
8. Put progress, proof, blockers, and completion evidence on the execution Task.
9. Complete with result, evidence, blockers, residual risks, and next responsible role.

## Required leader Task comment format

```text
Delegated execution Task created or accepted by Leader.
leader_coordination_task_id: <leader-task-id>
practitioner_task_id: <execution-task-id>
practitioner_agent_id: <agent-id>
role_owner: <role>
scope: <bounded scope>
non_goals: <explicit non-goals>
expected_output: <artifact or report>
evidence_required: <proof expected>
execution_context: <only the execution context fields defined in leader procedure step 2 that this assignment needs>
dependency_mode: Tasks-governed delivery; Workboard private progress only
next_review_owner: <leader-decided role>
```

## Required practitioner start comment

```text
Accepted delegated execution.
leader_coordination_task_id: <leader-task-id>
execution_task_id: <this-task-id>
understood_scope: <summary>
context_validation: <required supplied context matched, or mismatch reported and stopped>
pre_existing_modified_files: <confirmed files, none, or not applicable>
planned_evidence: <evidence>
blockers: <none or list>
```

## Required practitioner completion summary

```text
Completion report.
leader_coordination_task_id: <leader-task-id>
execution_task_id: <this-task-id>
result: <summary>
evidence: <proof references>
blockers: <none or list>
residual_risks: <none or list>
next_responsible_role: <leader-decided role>
```

## Forbidden patterns

- Do not use Workboard as practitioner-visible delivery SoT when Tasks is available and designated for the workspace.
- Do not use Workboard `parents` for concurrent delegation unless dependency blocking is intended for private local progress.
- Do not rely on a Workboard card id to coordinate practitioner execution.
- Do not ask the practitioner to create their own execution Task by default unless the workspace procedure explicitly allows it.
- Do not leave practitioner-created Tasks without leader acceptance, trace labels, and leader coordination Task back-reference.
- Do not treat Room/chat delivery as Task completion.
- Do not let a practitioner mutate the leader coordination Task during normal execution unless explicitly instructed.
- Do not continue Track A work after mutation, material impact, or classification doubt appears.

## Required safeguards

Every Track B delegated execution Task must carry exactly the fields mandated above by the leader procedure, the practitioner procedure, the PR-delivery procedure, and the three comment templates. Do not add further required fields.

If any execution Task id is missing, status is unknown or blocked, the delegated work is not complete.

## Eval checklist

A valid eval must check at least:

1. Track A requires all three criteria: single immediate practitioner, read-only/no material impact, and no plan-review need.
2. Track B is used when Track A fails, when work is multi-step, when multiple practitioners are involved, when material impact exists, or when classification is uncertain.
3. The skill recommends leader-created or leader-accepted Tasks for Track B and demotes Workboard to private scratch/progress only.
4. The skill requires recording practitioner Task ids on the leader coordination Task.
5. The skill requires practitioner proof/completion on the execution Task and blocker/wake/follow-up handling for incomplete work.
6. The skill preserves required role, evidence, output, non-goal, traceability, residual-risk, and next-responsible-role fields.
7. The skill does not authorize source/config/production/destructive/Salesforce org/secret actions.
8. Support references resolve relative to the skill directory.
9. Repository artifact delivery defaults to branch, commit, and PR submission, with patches or chat/file diffs as fallback only.
10. Leader Task completion runs `scripts/task-closeout-gate.py` and proceeds only on exit 0.

## Evidence basis

The routing above rests on the workspace operating model plus these empirical coordination findings:

- Workboard is personal per-agent progress tracking in this workspace and is not reliable as practitioner-visible delivery SoT.
- Historical Workboard parent/child dependency links blocked concurrent practitioner claim/complete.
- Practitioner-created work without leader back-reference can become orphan-risk.
- Branch, commit, and PR delivery is the observed default repository artifact path.
