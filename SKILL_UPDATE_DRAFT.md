---
name: clawpod-capability-registry
description: Discover, assess, install, validate, update, or roll back capabilities with mandatory registry-first WORKFLOW onboarding.
---

# ClawPod Capability Registry

Use `https://github.com/Wondermove-Inc/clawpod-capabilities` as the only capability registry. Do not search other GitHub repositories.

## Registry-first gate

Before creating or materially duplicating an AgentSkill or CLI Harness:

1. Inspect capabilities already installed in the current agent environment.
2. Search the canonical registry by intent, domain, backend, and nearby terms.
3. Assess same and similar candidates for scope, compatibility, prerequisites, safety, approval requirements, and limitations.
4. Record evidence and explicitly classify the decision as `reuse`, `refine`, `compose`, or `create`.
5. Choose `create` only when no adequate installed or canonical-registry capability exists. Improve the original when the boundary is the same.

Use direct execution for genuinely one-off work. Choose a Skill for reusable judgment and procedure, a Harness for deterministic typed execution, or both when a Skill selects and a Harness executes.

## Install and update

Select packages with explicit `type`. Verify canonical identity, paths, declared SHA-256 digests, compatibility, and safety metadata. Treat a Skill and its exact linked Harness as one transactional installation unit with explicit Skill and Harness roots.

When installing or updating `clawpod-capability-registry`, pass an explicit path to the agent-owned, existing `WORKFLOW.md`. Installation must transactionally activate the versioned registry-first managed block. It must preserve every byte outside the exact begin/end markers, write atomically, and stop without mutation on missing, duplicate, nested, reversed, or unclosed markers. It must not silently create a missing `WORKFLOW.md`.

Do not report installation complete when WORKFLOW onboarding is absent or failed. For unrelated capability installs, do not mutate WORKFLOW policy.

Installation never authorizes risky invocation. Obtain the required approval separately for credentials, account access, external side effects, destructive actions, privilege expansion, publication, deployment, and production changes.

## Evidence and validation

After install or update:

- Validate installed files against registry digests.
- Validate every Harness through the current Gateway lifecycle, establish trust only after validation, and exercise one bounded `prepare → run` path.
- Read `workflow-status` and record the policy status, managed policy version, hashed workflow path, changed or unchanged result, and recovery guidance. Never include WORKFLOW contents or secrets in evidence.
- For credentialed capabilities, deliver the post-install onboarding handoff and do not claim operational readiness while authorization is pending.

## Rollback and recovery

Keep the last known-good package until replacement and onboarding both succeed. If package installation or WORKFLOW activation fails, restore the package and the exact prior WORKFLOW bytes. Never overwrite local modifications silently.

Use `workflow-status` for read-only diagnosis. On malformed markers, repair only with owner review, then retry activation. On a missing workflow, obtain approval to create the agent-owned file before retrying. Use capability rollback to restore an approved package backup, then revalidate package digests and policy status.

## Completion

Report the selected capability and classification evidence, versions and destinations, validation results, WORKFLOW policy evidence, approval decision, side effects, rollback path, onboarding readiness, and residual limitations. Stop on partial side effects and state the verified recovery action.
