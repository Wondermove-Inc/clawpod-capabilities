# Distilled Salesforce Development Rules

This is a portable, English, skill-local distillation of the Salesforce development rules. It is not a copy of any project worklog.

## How to use

1. Select the module files that match the work surface.
2. Apply all relevant `DR-CMN-*` controls.
3. Apply module-specific `DR-*` rules.
4. Preserve provisional status. A provisional rule can guide inspection but must not be reported as a confirmed Salesforce platform fact without new evidence.
5. Record official Salesforce citations using `../citation-register.md` when no workspace citation register exists.

## Modules

| Module | File | Scope |
| --- | --- | --- |
| Common | `common_rules.md` | target org identity, dry-run, evidence, fact states, command/source hygiene |
| Configuration | `01_configuration_rules.md` | metadata, fields, layouts, permissions, Field-Level Security |
| SOQL | `02_soql_rules.md` | query safety, limits, user mode, injection, Tooling/setup object queries |
| Apex | `03_apex_rules.md` | governor limits, tests, sharing, callouts, async, coverage |
| Flow | `04_flow_rules.md` | Flow design, Apex actions, record-triggered automation, loop/recursion risk |
| LWC | `05_lwc_rules.md` | wire/imperative Apex, UI states, refresh, accessibility, metadata |
| Integration | `06_integration_rules.md` | callouts, REST, Named Credentials, payloads, events, retries |
| Case/Chatter | `08_case_chatter_rules.md` | approved request records, questions, corrections, completion evidence |

## Common Rule IDs

| Rule ID | Level | Portable obligation |
| --- | --- | --- |
| `DR-CMN-001` | MUST | Verify target Salesforce org identity at work start and immediately before any mutation; pin Salesforce CLI commands with an explicit target org. |
| `DR-CMN-002` | MUST | Pass check-only or dry-run validation before actual deployment when deployment is in scope. |
| `DR-CMN-003` | MUST | Do not treat deployment success as completion; verify permissions, UI/runtime surface, and data result when applicable. |
| `DR-CMN-004` | MUST | Do not mix unrelated change units; keep new work, corrections, deployment, activation, endpoint, and cleanup boundaries separate. |
| `DR-CMN-005` | MUST | Run relevant static analysis before deployment when the surface supports it; record tool version/provenance. |
| `DR-CMN-006` | SHOULD | Evaluate Configuration before Flow before Apex unless the approved request or defect evidence requires a lower layer. |
| `DR-CMN-007` | MUST | Preserve raw command output or equivalent machine-readable evidence; prose summaries are not enough. |
| `DR-CMN-008` | MUST | Mark facts as `[VERIFIED]`, `[UNVERIFIED]`, or `[ESTIMATED]`. |
| `DR-CMN-009` | MUST NOT | Do not send secrets, private customer data, or sensitive Salesforce record content to external systems unless explicitly approved and minimized. |
| `DR-CMN-010` | MUST | Capture before-state evidence before mutation and comparable after-state evidence after mutation. |
| `DR-CMN-011` | MUST | Tie org-changing work to an approved request record and preserve correction/completion communication evidence. |
| `DR-CMN-012` | MUST | Before using unfamiliar CLI flags, API features, or platform behavior, check the official reference and record the citation. |
| `DR-CMN-013` | MUST | When building deploy input, include required source-format file pairs and verify the dry-run component list matches intended scope. |
