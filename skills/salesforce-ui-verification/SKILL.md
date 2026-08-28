---
name: salesforce-ui-verification
description: Verify Salesforce UI behavior with URL-only org access, Playwright snapshots, screenshots, and redacted evidence without performing Salesforce mutations.
---

# Salesforce UI Verification

Capability: `salesforce-ui-verification`

Use this ClawPoD/OpenClaw skill for Salesforce UI evidence after a UI-relevant change, page assignment, component visibility rule, or regression criterion. This skill verifies what the browser can observe; it does not authorize metadata changes, record updates, permission assignments, deploys, or cleanup.

## Always Apply

1. Read the approved UI criteria, target page or record, user/profile context, expected positive/negative/regression text, and `references/ui-evidence.md`.
2. Confirm whether UI verification is required. If no UI surface changed and no UI acceptance criterion exists, return that UI verification is not applicable.
3. Do not mutate Salesforce. Do not click Save, Edit, Activate, Delete, Assign, Publish, Submit, or any control that can change org data or metadata.
4. Use `sf org open --url-only --target-org <alias>` only when org UI verification is explicitly authorized. Extract only the `https://...` URL for navigation and do not persist the raw frontdoor URL.
5. Use Playwright evidence: accessibility snapshot for structure, targeted text/locator assertions for acceptance, screenshot for visual state, and failure evidence when the UI does not meet criteria.
6. Redact and scan all logs before final evidence is used. Raw frontdoor URLs, OTPs, session IDs, tokens, and bearer headers are never final evidence.

## Evidence Contract

| Evidence | Required handling |
| --- | --- |
| URL-only auth | Keep the raw URL in a process variable or temporary file with cleanup. Final logs must contain `<REDACTED_FRONTDOOR_URL>` only. |
| Playwright snapshot | Capture accessible structure for the target page or component. Prefer partial ARIA snapshots for stable roles/text over brittle full-page dumps. |
| Screenshot | Capture the final browser state for human review. Store only after URL/log redaction is complete. |
| Positive check | Prove expected UI text, component, button, or field is present for the intended record/user state. |
| Negative/regression check | Prove text or controls are absent or changed where the acceptance criteria require it. |
| Failure evidence | Save redacted error, current URL origin only, screenshot/snapshot if safe, and explain whether the failure is login, navigation, visibility, assignment, data, or tool usage. |

## Stop Conditions

Stop with `no-go` when the URL extraction includes warning text, browser lands on login instead of the target page, Playwright evidence contains unredacted frontdoor/session material, target record/user/profile is ambiguous, page assignment is unverified, the acceptance text is not visible, or requested interactions would mutate Salesforce.

## Report

Lead with UI go/no-go. Then state the target org alias and record/page identity with secrets removed, tested user/profile if known, assertions, snapshot/screenshot paths, redaction scan result, unsupported claims, and whether additional runtime or metadata verification is required.
