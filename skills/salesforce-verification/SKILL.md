---
name: salesforce-verification
description: Verify Salesforce source, deploy-readiness, and runtime evidence for ClawPoD/OpenClaw work without authorizing actual org mutation.
---

# Salesforce Verification

Capability: `salesforce-verification`

Use this ClawPoD/OpenClaw skill when the assigned work is to verify Salesforce local quality, Apex test evidence, deploy readiness, Flow runtime evidence, or no-go conditions. This skill is a verification gate, not an implementation or deployment skill.

## Always Apply

1. Read the approved request, active handoff or plan, source allowlist, expected/negative/regression criteria, prior worklog evidence, and `references/verification-boundary.md`.
2. Mark claims as `[VERIFIED]`, `[UNVERIFIED]`, or `[ESTIMATED]`. Separate deploy-readiness from runtime acceptance.
3. Use only official first-party Salesforce sources for Salesforce platform facts. Every new platform citation must include URL, API version or "API version not applicable", and date confirmed.
4. Preserve user changes and do not edit source unless a separate development assignment authorizes it.
5. Do not run Salesforce mutations. This skill does not authorize actual deploy, retrieve-overwrite, activation/deactivation, metadata update, data create/update/delete, permission assignment, event publication, endpoint probe, or cleanup.
6. If a Salesforce org command is explicitly authorized for verification, pin `--target-org` or `-o`, record org identity first, and capture command, timestamp, exit code, stdout/stderr, tool versions, and redacted evidence.
7. Route any actual mutation, cleanup, rollback, or deployment execution to `salesforce-org-change` and require independent review before go/no-go.
8. On any failed test, no-go, manual-test failure, or unexpected reproduction result, perform failure impact analysis before recommending remediation. Do not treat the first failing line as the full scope.
9. For reproduction baselines, verify that the intended bottleneck/failure remains observable and that no earlier error masks the approved reproduction target.

## Verification Surfaces

| Surface | Minimal reference | Gate behavior |
| --- | --- | --- |
| Local quality and static analysis | `references/verification-boundary.md`, `references/citation-register.md` | Run local parsers, tests, and Salesforce Code Analyzer when dependencies exist. Code Analyzer output must be file-based, include plugin/JDK provenance, and have no High/Medium findings unless the reviewer accepts a documented exception. |
| Apex tests | `references/verification-boundary.md` | Apex tests execute in an org, so use only with explicit org-verification authorization. Pin target org, use named tests or classes, request code coverage when relevant, and do not claim local un-deployed source was tested by an org-resident test run. |
| Deploy readiness | `references/verification-boundary.md` | Prefer dry-run/check-only validation and component list inspection. Treat dry-run success as deploy-readiness only; it is not runtime or UI acceptance. Actual deploy is out of scope. |
| Flow runtime verification | `references/flow-runtime.md` | Distinguish Flow metadata status and bindings from runtime behavior. Verify observable outcomes through Flow test/run evidence, Flow.Interview, SOQL/audit records, or other approved read evidence. |
| Evidence, redaction, and handoff | `references/verification-boundary.md` | Preserve raw evidence only after secret redaction. Scan evidence for frontdoor URLs, OTPs, access tokens, bearer headers, signing material, and copied scan-output leaks. |

## Stop Conditions

Stop and return `no-go` when target org identity is missing, source hash or component allowlist is stale, Code Analyzer cannot run due to missing dependencies and no approved fallback exists, Apex tests fail or do not cover the changed Apex, dry-run/check-only fails, Flow runtime output is not observable, required evidence contains unredacted secrets, or the request asks for mutation under this skill.

When stopping on a failure, report the failure point, affected source/runtime surfaces, likely root-cause candidates, scenario conflict if any, and the smallest safe next decision. Do not route repair work yourself unless that separate authority is assigned.

## Report

Lead with go/no-go. Then list grounds, changed or inspected files, tests/checks, evidence paths, official citations, unsupported claims, and residual risk. Do not use deploy success, dry-run success, or metadata retrieval alone as proof that users can operate the feature.
