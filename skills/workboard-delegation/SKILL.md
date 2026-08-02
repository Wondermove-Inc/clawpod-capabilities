---
name: workboard-delegation
description: Delegate standalone Workboard execution cards with pure deterministic planning, exact approval, first-class mutations, and verified reconciliation.
---

# Workboard Delegation

Use the paired Harness for pure planning and validation. Perform every read and mutation through first-class scoped Workboard tools. Never let the Harness call Gateway or Workboard.

## Required workflow

1. Run Harness `plan` with leader id, expected leader owner when claimed, practitioner, scope, optional non-goals, done-when, evidence requirement, report-back target, tenant, board, and labels.
2. Show the exact packet and stable `planHash`; obtain explicit human approval for that exact intent.
3. Call `workboard_read` for the leader. Keep any returned claim token outside Harness input.
4. Run Harness `validate-leader` with approved plan JSON/hash, bounded leader snapshot JSON, and expected owner. Stop on dependencies, owner mismatch, or malformed state.
5. Before creation, call `workboard_list` with the plan practitioner, tenant, and board. Read only the bounded candidate cards needed to compare `metadata.automation.idempotencyKey` and `createdByCardId`. Reuse one exact match, stop on multiple matches, otherwise call `workboard_create` once with exactly `createFields`. Do not add parents. This is a related standalone card.
6. Call `workboard_read` for the child. Read the leader again immediately before mutation and stop if its claim owner changed. Call `workboard_comment` on the leader with the plan comment template resolved to the child id, supplying the leader claim token to the first-class tool when required.
7. Call `workboard_read` for both cards, then run Harness `validate-result` with the approved plan/hash and bounded snapshots. Completion requires successful final validation. Re-run the same candidate lookup and final validation to prove replay convergence without another card or comment.

## Partial failure

Use `workboard_list` and `workboard_read` to locate the existing idempotent execution card. Run Harness `reconcile-plan` with the exact approved plan and available snapshots. Execute only the returned missing actions through `workboard_create` or `workboard_comment`, respecting current claim/scope enforcement, then read and validate again.

If reconciliation reports conflicting execution fields or duplicate comments, stop for human review. Never duplicate a card, pass a claim token into the Harness, create dependencies, or mutate outside first-class Workboard tools.

## Duties

**Leader:** define and approve exact scope, retain source-of-truth coordination, provide claim only to scoped Workboard calls, and verify final evidence.

**Practitioner:** execute only the child scope, report progress and proof on that card, and complete or block it without changing leader coordination.
