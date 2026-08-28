---
name: salesforce-development
description: Use for approved Salesforce local source planning, implementation, and local verification. This skill is read/write for repository files only and never authorizes Salesforce org mutation.
---

# Salesforce Development

Capability: `salesforce-development`

Use this OpenClaw skill for Salesforce source work that stays inside the repository. Do not deploy, retrieve from an org, activate or deactivate automation, create/update/delete org data, assign permissions, publish events, probe live endpoints, run cleanup, or expose secrets.

## Required Workflow

1. Read the approved request, active plan, repository instructions, actual source, tests, and evidence before making claims.
2. Separate claim states as `[VERIFIED]`, `[UNVERIFIED]`, or `[ESTIMATED]`.
3. Use official first-party Salesforce sources for Salesforce platform facts. Record URL, API/release/CLI version or `not applicable`, date confirmed, method, and limitation using the workspace citation log or `references/citation-register.md`.
4. Start with `references/dev-rules/README.md`, then load only the references needed for the touched surface.
5. Preserve user changes and choose the smallest approved change.
6. Before editing, confirm scenario type, trigger moment, success criteria, failure criteria, non-goals, and excluded cases/surfaces. If any of these are unclear, stop for Leader/requester clarification.
7. If the assignment is reproduction-only, preserve the approved defect path and do not optimize, bulk-fix, or move the root cause to another surface. If it is final-fix work, do not intentionally preserve the defect.
8. For object, field, layout, Flow, or UI-facing metadata, include PermissionSet, Profile, Field-Level Security, layout, tab, and user-visibility impact checks in the implementation notes or stop if the scope is not approved.
9. Use RED/GREEN/BLUE when implementation is approved: focused failing test or deterministic validator, minimal implementation, then diff/rule/evidence review.
10. Keep verification under this skill local. Route org-resident Apex test execution, Code Analyzer gate verdicts, and check-only/dry-run deploy validation to `salesforce-verification`.
11. Route Salesforce org mutation to `salesforce-org-change` only after explicit authorization.
12. Route final or checkpoint review to `salesforce-dev-review`.

## Reference Routing

| Work surface | Read |
| --- | --- |
| Common workflow, evidence, citation, Rule IDs | `references/core-workflow.md`, `references/evidence-basics.md`, `references/citation-register.md` |
| Apex, triggers, tests, SOQL | `references/apex-soql.md` |
| Flow XML, Flow tests, automation paths | `references/flow.md` |
| Lightning Web Components (LWC), UI state, Apex binding | `references/lwc.md` |
| Objects, fields, layouts, Permission Sets, Field-Level Security (FLS), metadata XML | `references/metadata.md` |
| Callouts, REST, Platform Events, payloads, external contracts | `references/integration.md` |
| Writing or receiving a maintenance work order (task brief) | `references/task-brief-template.md` |

For mixed work, read every matching reference and the matching files under `references/dev-rules/`. For mutation planning without authorization, produce only a read-only plan and do not load or execute mutation procedure details.

## Report

Lead with conclusion, then grounds. State changed files, tests or checks, evidence locations, unverified gaps, residual risk, and the next reviewer or approval gate.
