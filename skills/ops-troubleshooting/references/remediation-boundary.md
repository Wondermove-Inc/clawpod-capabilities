# Remediation boundary

## Allowlisted (plan → apply, chained in one turn)

| Action | Target | Preconditions snapshotted | Verification | Rollback note |
|---|---|---|---|---|
| `service.restart` | systemd unit | Id, LoadState, ActiveState, SubState, FragmentPath | unit active/activating after restart | none; inspect the unit journal and restore config/package |
| `k8s.rollout.restart` | `deployment/`, `statefulset/`, `daemonset/` + namespace | uid, generation, replicas, images, readyReplicas | `rollout status` completes within the timeout | `kubectl rollout undo` |
| `k8s.pod.delete` | managed pod + namespace | uid, owner kind/name, phase, node | owner recorded; controller recreates | inspect the replacement pod |

Plan facts: owner-only file, 15-minute expiry, `confirmationChallenge` bound to id + action + target + preconditions + expiry, single use, preconditions re-checked at apply, action never retried.

## How to report a plan as you apply it

Report, verbatim from `remediate.plan`: action, target (with namespace), `preconditions`, `commands`, `rollback`, `expiresAt`, and your one-line reason. State the blast radius (which users/requests see a blip) and what you will run to verify — then apply *this plan id* with its confirmation in the same turn. If anything about the intent changes, re-plan.

## Not allowlisted — recommend with exact commands and rollback

Config edits, scaling, `rollout undo`, node cordon/drain, package install/upgrade/downgrade, firewall changes, account or key changes, certificate issuance, deleting data or PVCs, anything on a database. These go in the report under "Recommended change" with owner, command, expected effect, rollback, and risk; execution belongs to a human or to a capability whose contract covers it.

## Refusals you will see and what they mean

| Error | Meaning | Do |
|---|---|---|
| `PLAN_REQUIRED` | no readable plan for that id | re-plan |
| `CONFIRMATION_MISMATCH` | confirm string is not this plan's challenge | use the exact value from the plan output; never guess |
| `PLAN_EXPIRED` | more than 15 minutes since plan | re-plan, re-approve |
| `PLAN_CONSUMED` | plan already applied | re-plan if a second action is really needed |
| `PLAN_STALE` | target changed (state, generation, owner) | re-diagnose; the world moved |
| `POD_UNMANAGED` | pod has no controller | do not delete; investigate why a bare pod exists |
| `VERIFY_FAILED` | action ran, recovery unconfirmed | follow rollback note; escalate; do not re-apply |
