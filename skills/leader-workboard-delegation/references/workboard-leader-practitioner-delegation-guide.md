# Workboard Leader-Practitioner Delegation Guide

> **Historical — superseded (2026-08-13).** The Workboard execution-card procedure in this document is superseded by the Tasks-first model in SKILL.md; this document is retained as the empirical record of why Workboard delegation was abandoned.

## 1. Purpose

This document records the background, purpose, verified behavior, and operating process for using Workboard when a leader agent delegates executable work to a practitioner agent.

The goal is to make Workboard delegation traceable without losing ownership, creating orphan cards, or accidentally using dependency links as an organizational hierarchy.

## 2. Background

Empirical tests showed several important behaviors:

1. Cross-agent read access works.
2. Parent/child links are not an organizational tree for concurrent work because they behave as dependency gates.
3. A claimed parent blocks some cross-agent parent-linked mutations.
4. Reverse lookup from main card id is not automatically guaranteed.
5. Orphan card risk is real when practitioner-created cards omit back-reference, tenant, trace label, or comment-back.
6. The corrected leader-created execution card process works.

## 3. Mechanism Assessment

Workboard supports enough primitives to run a safe leader-to-practitioner delegation flow when the leader creates the practitioner execution card directly, but safety depends on workflow compliance. Workboard itself does not teach agents when to create cards or enforce Product/Planning versus practitioner boundaries.

Useful mechanisms:

- `workboard_create` can create a leader card and practitioner card.
- `agentId` can assign a card to the practitioner.
- `tenant` and `boardId` can keep cards in the same project scope.
- `createdByCardId` can record the leader card that created the execution card.
- `labels` can carry trace labels, for example `sot-<leader-short-id>`.
- `notes` can carry structured delegation packet fields.
- `workboard_comment` can write the returned practitioner card id back to the leader card.
- `workboard_read` lets the leader and practitioner inspect the cards by id.
- `workboard_claim`, `workboard_proof`, and `workboard_complete` let the practitioner operate the assigned execution card.

Known gaps:

- Workboard assigns `agentId`, but does not enforce role boundaries, human gates, evidence review, or 'do not mutate leader card' behavior.
- No proven direct reverse query from `main_card_id` to all related execution cards.
- No proven direct filter by `createdByCardId` in the exposed `workboard_list` schema.
- No automatic prevention of a practitioner creating an orphan card.
- No automatic enforcement that a practitioner must report a newly created card id back to the leader.
- Parent/child links impose dependency semantics, so they cannot be used as a simple organizational hierarchy for concurrent work.

## 4. Practical conclusion

The process is viable only if the leader-created execution card pattern is treated as the default.

Safe default:

1. Leader creates the leader SoT/orchestration card.
2. Leader creates every practitioner execution card.
3. Leader immediately records the returned practitioner execution card id on the leader card.
4. Practitioner receives an existing execution card id and operates only that card.
5. Leader tracks execution by reading the explicit ids recorded on the leader card.

## 5. When to create Workboard cards

Create a leader SoT/orchestration card when work:

- spans more than one step;
- will be delegated to another agent;
- needs follow-through, evidence, review, or completion tracking;
- may continue beyond the current message turn;
- has blockers, dependencies, or human-gate conditions;
- needs a final report based on verified practitioner evidence.

For a single quick answer or one-shot command that completes immediately, a Workboard card is usually unnecessary.

Create a separate practitioner execution card when:

- a specific role or agent owns an executable slice;
- the practitioner needs to claim, update, attach proof, and complete work independently;
- the leader must later verify status or evidence;
- concurrent work is expected.

Do not use Workboard `parents` for concurrent delegation. Use separate related execution cards instead.

A practitioner may create a card only when explicitly asked or when a necessary discovered subtask is outside the current execution card. The practitioner must immediately report the new card id back to the leader SoT card or agreed source of truth.

## 6. Standard operating process

### Leader procedure

1. Create the leader SoT/orchestration card with request source, source of truth, scope, non-goals, owner roles, acceptance criteria, evidence requirements, human-gate state, and closeout condition.
2. Create the practitioner execution card directly with same tenant/board, `createdByCardId`, trace labels, and structured notes including `leader_sot_card_id`.
3. Record the returned practitioner card id on the leader card.
4. Send the practitioner the execution card id and bounded instructions.
5. Track status by reading execution card ids recorded on the leader card.
6. Review practitioner proof before reporting completion.
7. Complete the leader card only after practitioner evidence and final reporting are complete, or block it with owner/reason/next action and a wake/follow-up condition.

Required leader comment:

```text
Delegated execution card created by Leader.
leader_sot_card_id: <leader-card-id>
practitioner_card_id: <execution-card-id>
practitioner_agent_id: <agent-id>
role_owner: <role>
scope: <bounded scope>
expected_output: <artifact or report>
evidence_required: <proof expected>
dependency_mode: related-card, not parent-child dependency
next_review_owner: Product/Planning
```

### Practitioner procedure

1. Read the assigned execution card.
2. Read the leader SoT card only for context when needed.
3. Do not mutate the leader card unless explicitly instructed.
4. Do not create a new card unless explicitly instructed.
5. Claim only the assigned execution card.
6. Add progress comments on the execution card.
7. Add proof on the execution card.
8. Complete the execution card with result, evidence, blockers, residual risks, and next responsible role.

## 7. Forbidden or risky patterns

- Do not use Workboard parent/child links as an organizational hierarchy for concurrent delegation.
- Do not ask the practitioner to create their own execution card by default.
- Do not rely on `main card id` alone to discover all execution cards.
- Do not let a practitioner mutate the leader card during normal execution.
- Do not treat chat delivery as work completion.

## 8. Required safeguards

For delegated or background work, the leader must keep Workboard tracking plus a wake/follow-up condition until every execution card is done, blocked with owner/reason/next action, or explicitly cancelled. A Room progress report is transport only and does not complete the leader card.

Minimum safeguards:

- Leader creates execution cards by default.
- Leader records every returned `practitioner_card_id` on the leader card.
- Practitioner execution card includes `leader_sot_card_id` in notes.
- Execution card has `createdByCardId` pointing to the leader card when leader-created.
- Both cards share `tenant` and `boardId` when known.
- Both cards use trace labels.
- Practitioner claims only the assigned execution card.
- Practitioner proof and completion stay on the execution card.
- Leader reads the recorded execution card id before reporting completion.
- Any missing execution card id is treated as blocked or unknown, not complete.

## 9. Current sufficiency of the mechanism

Workboard mechanisms alone are not sufficient for leader and practitioner agents to know when to create cards or to enforce role-correct behavior.

Sufficient today:

- Leader can create both cards.
- Leader can record returned execution card id.
- Practitioner can claim and complete the leader-created execution card.
- Leader can verify completion through the recorded card id.

Not sufficient today:

- Workboard does not automatically enforce bidirectional references.
- Workboard does not automatically prevent orphan cards.
- Workboard does not expose a proven reverse lookup from leader card id to all related cards.
- Role-specific behavior depends on agents following the operating checklist.

Recommended future improvements:

1. A Workboard delegation helper that creates leader and execution cards atomically and writes both references.
2. A validator that flags delegated execution cards missing `leader_sot_card_id`, `createdByCardId`, tenant, board, or trace label.
3. A reverse lookup tool/filter for `createdByCardId` or `leader_sot_card_id`.
4. A reusable skill or workflow checklist that leader and practitioner agents must read before delegated Workboard work.

## 10. Final standard

```text
Leader creates main SoT card
Leader creates practitioner execution card
Leader records returned execution card id on main SoT card
Practitioner operates only assigned execution card
Leader verifies execution card evidence
Leader reports and completes main SoT card
```

This standard avoids parent/child dependency blocking and orphan cards caused by practitioner-created cards without back-reference.

## 11. Status

Status: reviewed operational guidance.

Use this as a workflow/checklist. Do not treat it as Workboard-enforced policy unless a future skill, validator, or tool-level guardrail is added.
