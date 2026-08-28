# Evidence Basics Reference

Read this when preparing implementation notes, checkpoint reports, or completion reports for Salesforce local development.

## Minimum evidence map

For every material claim, map:

- requirement or acceptance criterion;
- changed file or inspected source;
- applicable Rule IDs;
- test, validator, static check, or runtime evidence;
- raw evidence path or command/result identifier;
- claim state: `[VERIFIED]`, `[UNVERIFIED]`, or `[ESTIMATED]`.

## Required report separation

- Local source evidence proves only local source behavior.
- Static analysis proves only the checked static surface.
- Unit tests prove the tested path, not deployment or runtime behavior.
- Deployment success does not prove runtime acceptance.
- Requester acceptance does not replace technical review.
- Metadata XML does not prove org-side permissions, user visibility, or runtime state.
- Mocked integration tests do not prove endpoint availability, event delivery, subscriber processing, or credentials.

## Secret and safety evidence

- Report secret-scan result or state why it could not run.
- Never paste plaintext secrets, tokens, credentials, or environment values.
- For security-sensitive work, report presence/path/owner/mode/fingerprint only when safe.

## Review handoff to `salesforce-dev-review`

Before completion, provide the reviewer:

- approved request and plan;
- actual diff and changed files;
- RED/GREEN/BLUE evidence;
- commands run and raw outputs;
- rule mapping;
- mutation boundary statement;
- unverified gaps and residual risk.
