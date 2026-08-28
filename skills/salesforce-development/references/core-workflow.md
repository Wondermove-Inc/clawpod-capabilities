# Core Workflow Reference

Read this for every Salesforce local development task.

## Evidence-first boundary

- Inspect actual source and evidence before making a claim.
- Do not guess from filenames, summaries, prior reports, or remembered platform behavior.
- Preserve existing changes and choose the smallest approved change.
- Explain Salesforce terms on first use. In this repository, `org` means a Salesforce tenant instance unless the document is discussing the ClawPod agent organization.

## Fact states and source of truth

- `[VERIFIED]`: confirmed by an official source, responsible person, or hands-on measurement.
- `[UNVERIFIED]`: stated but not confirmed by acceptable evidence; never use it as a completion claim.
- `[ESTIMATED]`: inferred; state assumptions and verification needed.
- Salesforce platform facts require official first-party Salesforce sources. Record each citation using `citation-register.md` when the active workspace has no stronger citation system.
- Keep raw command output under the applicable evidence directory. A prose summary is not a substitute.

## Canonical rule routing

Always start with `dev-rules/README.md`; then read only matching skill-local module documents:

- Metadata/configuration: `dev-rules/01_configuration_rules.md`
- SOQL and Apex: `dev-rules/02_soql_rules.md`, `dev-rules/03_apex_rules.md`
- Flow: `dev-rules/04_flow_rules.md`
- LWC: `dev-rules/05_lwc_rules.md`
- Integration: `dev-rules/06_integration_rules.md`
- Case/Chatter request records: `dev-rules/08_case_chatter_rules.md`

Use relevant Rule IDs in plans, implementation notes, and review matrices. Preserve provisional rule status.

## RED/GREEN/BLUE

1. RED: write the smallest focused failing test or deterministic validator assertion and preserve the faithful failure.
2. GREEN: implement the smallest change that passes.
3. BLUE: keep checks passing, compare actual diff to request and Rule IDs, remove speculative code/templates, and inspect unsupported claims, stale evidence, secrets, and mutation risk.

Run every mandatory test named by the plan, repository instructions, applicable rule documents, and changed technology. If a required test cannot run, mark the result `[UNVERIFIED]`, record why, and state residual risk.

## Local-only mutation boundary

This development skill never mutates a Salesforce org. Do not mutate a Salesforce org under this skill. Deploy, retrieve, activation/deactivation, data changes, permission assignment, live endpoint probing, event publication, and cleanup require `salesforce-org-change` with explicit authorization.
