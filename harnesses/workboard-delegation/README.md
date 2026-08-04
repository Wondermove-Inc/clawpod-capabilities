# Workboard Delegation harness

A pure, deterministic companion for scoped Workboard delegation. It never calls a Gateway, Workboard, subprocess backend, configuration, or secrets. It only builds plans and validates bounded JSON snapshots supplied by the calling agent.

## Commands

- `status`: report the pure local contract.
- `plan`: emit an exact delegation packet, stable `planHash`, idempotency key, structured execution notes, create fields, comment marker, and comment template.
- `validate-leader`: verify a leader snapshot, approved plan hash, dependency state, and expected `metadata.claim.ownerId`.
- `validate-result`: verify leader/execution snapshots, exact automation metadata and notes, no execution parents, and exactly one matching cross-reference comment.
- `reconcile-plan`: inspect approved plan and snapshots and emit only the exact missing action list. It never performs an action.

All Harness commands are `readOnly`. Mutations are performed only by the paired Skill through first-class scoped `workboard_create` and `workboard_comment` tools, preserving agent claims, scope checks, approvals, and Workboard enforcement.

## Plan workflow

1. Invoke `plan` with leader, expected owner when claimed, practitioner, scope, optional non-goals, done-when, evidence requirement, report-back target, and routing fields.
2. Review and obtain exact human approval for the returned packet and `planHash`.
3. Read the leader with first-class `workboard_read`.
4. Pass the approved plan, hash, and bounded leader snapshot JSON to `validate-leader`. Never pass a claim token to the Harness.
5. The paired Skill performs the approved first-class Workboard mutations.
6. Read both cards and pass their bounded snapshots to `validate-result`.

Each snapshot and plan JSON string is limited to 65,536 bytes. Every stdout JSON envelope, including its trailing newline, has a conservative 1,900-byte UTF-8 budget below the Gateway `stdoutPreview` 2,000-byte transport ceiling. The Harness rejects a would-be successful response with stable `output_too_large` instead of truncating delegation semantics. Shorten the delegation packet and run `plan` again. Inputs and outputs are stable JSON. Error envelopes are bounded and never echo caller input; `performed` is always false because the Harness cannot mutate.

## Partial failure

Use first-class `workboard_list` and `workboard_read` to locate any existing idempotent execution card, then call `reconcile-plan` with the approved plan and snapshots. Execute only its missing action list through first-class tools. If an existing card conflicts or duplicate comments exist, stop for human review. Never create a duplicate.

## Test

```bash
python3 -m pytest -q harness/tests
python3 -m py_compile harness/workboard_delegation.py
git diff --check
```
