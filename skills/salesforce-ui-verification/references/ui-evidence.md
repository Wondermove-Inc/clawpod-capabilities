# UI Evidence

This reference defines URL-only Salesforce UI verification with Playwright evidence and secret redaction.

## URL-Only Handling

- `sf org open --url-only --target-org <alias>` can display a navigation URL without launching a browser.
- Parse only the first `https://` URL. Do not pass the full command output to Playwright because warnings or explanatory text can make the URL invalid.
- Treat `frontdoor.jsp`, `otp=`, and session-bearing URLs as secrets. Keep them out of final evidence.
- If a frontdoor URL expires or lands on the login page, record the failure; do not force a pass from stale metadata.

## Playwright Evidence

Capture:

- An accessibility snapshot or targeted ARIA snapshot for page/component structure.
- Locator/text assertions for each positive acceptance criterion.
- Locator/text assertions for negative and regression criteria when required.
- A screenshot for reviewer inspection.
- Tool/version, command, timestamp, exit code, and redacted stdout/stderr.

Prefer stable selectors and accessible roles. Do not use Playwright to click controls that can save, edit, activate, delete, assign, publish, submit, or otherwise mutate Salesforce.

## Redaction and Scan

- Replace raw auth/session URLs with `<REDACTED_FRONTDOOR_URL>` immediately after capture.
- Scan final UI evidence for frontdoor paths, OTP/session query keys, authorization header names, bearer-token prefixes, access token patterns, and unredacted org-open output.
- The scan output itself can copy sensitive patterns. Keep raw scan hits temporary and publish only a clean final summary.
- If redaction cannot be verified, the UI result is `no-go` regardless of visible UI success.

## Confirmed Sources

| Claim | Official source | API version / release | Date confirmed |
| --- | --- | --- | --- |
| `sf org open --url-only` displays a navigation URL without launching the browser. | https://developer.salesforce.com/docs/platform/salesforce-cli-reference/guide/cli_reference_org_open.html | API version not applicable on CLI page | 2026-08-02 |
| Playwright ARIA snapshots compare a page or locator accessibility tree to an expected YAML-like snapshot and support partial matching. | https://playwright.dev/docs/aria-snapshots | API version not applicable; Playwright docs page | 2026-08-02 |
| Playwright supports page, full-page, and element screenshots for captured UI state. | https://playwright.dev/docs/screenshots | API version not applicable; Playwright docs page | 2026-08-02 |
| LWC record-page targets make components available for Lightning record pages; bundle existence alone does not prove page placement. | https://developer.salesforce.com/docs/platform/lwc/guide/targets-lightning-record-page.html | API version not applicable on page | 2026-08-02 |

Project worklog basis: `docs/poc-sf-org/worklog/lessons.md` T-10, T-11, T-14, T-17, T-30, T-31, T-35, T-36, T-60, T-63, T-64, T-78, T-79, T-85, T-86, T-94, T-95, and T-119.
