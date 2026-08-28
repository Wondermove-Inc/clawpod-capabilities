# Portable Citation Register Reference

Use this when the active OpenClaw workspace does not already provide a stronger citation register.

## Required fields

For every Salesforce platform fact, record:

- claim or rule supported;
- official first-party Salesforce URL;
- API version, release version, CLI version, or `not applicable`;
- date confirmed;
- confirmation method: documentation read, command help, command output, or responsible-person confirmation;
- limitation or unresolved gap.

## Source rules

- Use official Salesforce documentation, Salesforce developer documentation, Salesforce CLI reference, Metadata API reference, Tooling API reference, REST API reference, or other first-party Salesforce-owned sources.
- Community posts, blogs, generated summaries, and forum answers are leads only.
- If no version exists on the source, explicitly write `version: not applicable` and keep the confirmation date.
- Do not treat a local project worklog as a Salesforce platform source of truth.
- Do not paste secrets, org credentials, customer payloads, or private record contents into citation notes.

## Reporting states

- `[VERIFIED]`: confirmed by official source, responsible person, or direct hands-on measurement.
- `[UNVERIFIED]`: not confirmed; do not use as completion evidence.
- `[ESTIMATED]`: reasoned assessment; state the basis and required verification.
