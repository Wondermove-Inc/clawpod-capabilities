---
name: salesforce-dev-review
description: Use for independent read-only Salesforce development and org-change review gates. Produces go/no-go findings and never edits, deploys, retrieves, mutates, or self-approves.
---

# Salesforce Development Review

Capability: `salesforce-dev-review`

Use this OpenClaw skill for independent Salesforce review gates. It is read-only: never edit, deploy, retrieve, mutate, repair findings, approve your own work, expose secrets, or authorize unreviewed worker claims. Use it within the live `SOUL.md` and `WORKFLOW.md` authority model; this skill is a capability, not an intake, assignment, approval, or override grant.

## Required Inputs

- Approved request and active plan or task brief. For direct instructions, confirm the work remains Track A, stays within role authority, and is reported to Leader; if it needs Track B governance, stop for Leader assignment.
- Exact PR/revision identity when source review is involved: head commit, base commit, merge-base or parent, changed-file list, and whether the PR is stacked, merged, or superseded.
- Actual changed files and diff.
- Named test, static check, validator, or runtime output.
- RED/GREEN/BLUE evidence when implementation is in scope.
- Salesforce org identity, mutation IDs, before/after evidence, and cleanup evidence when mutation is in scope.
- Applicable Rule IDs from `references/dev-rules/README.md`.

## Review Workflow

1. Inspect actual files, diff, commands, raw evidence, and org-state evidence when provided.
2. Separate `[VERIFIED]`, `[UNVERIFIED]`, and `[ESTIMATED]` claims.
3. Confirm Salesforce platform facts use official first-party Salesforce evidence with URL, API/release/CLI version or `not applicable`, and date confirmed.
4. Check overspec, unsupported claims, stale evidence, missing tests, missing raw evidence, mutation safety, and secrets exposure.
5. Confirm revision integrity before content review: exact head/base, merge-base, changed files, and no unintended moving-branch or stacked-PR confusion.
6. Check impact beyond changed files when Salesforce metadata is involved: adjacent Apex/Flow triggers, stale field references, metadata casing, PermissionSet/Profile/FLS, layout/tab visibility, excluded scenarios, and manual test path.
7. For reproduction-only work, review whether the intended defect path remains observable. Do not give `go` if a premature fix removed the bottleneck, or if an unrelated preemption error hides the intended defect.
8. If a plaintext secret or unredacted credential appears in the revision or evidence, stop the review, report the leak through the live escalation path, and use redacted evidence only.
9. For Security use, keep the Security verdict separate from QA's functional verdict: test success or QA `go` is not Security `go`, and Security `go` is not functional approval.
10. When reviewing capability or external SaaS test work, confirm installation/trust/test success is not treated as authority, and confirm artifact retention/deletion remains owner-approved with only redacted safe identifiers in evidence.
11. Load only the references needed for the review surface.

## Reference Routing

| Review need | Read |
| --- | --- |
| General evidence review and go/no-go threshold | `references/evidence-review.md` |
| Mutation, target-org, deploy/retrieve/cleanup safety | `references/mutation-review.md` |
| Rule matrix and module coverage | `references/rule-matrix.md`, `references/dev-rules/README.md` |
| Citation requirements | `references/citation-register.md` |

For mixed work, read every matching local review reference and the matching distilled rule files under `references/dev-rules/`.

## Verdict Rule

High or Medium findings mean `no-go`. Any partial or unmet required criterion means `no-go`. A QA or Security `no-go` blocks the item and cannot be overridden by Leader, the author, schedule pressure, or requester acceptance; only the issuing review role can clear it after a fresh rereview. A `go` verdict requires all completion criteria, required commands, evidence, mutation safety, Rule ID checks, and secret-safety checks to pass. After remediation, require a fresh rereview of the plan, actual files, new diff, rerun tests, and replacement evidence.
