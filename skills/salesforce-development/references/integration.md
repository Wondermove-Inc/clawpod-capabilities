# Integration Reference

Read this for callouts, REST API boundaries, Platform Events, payloads, Named Credential assumptions, and external-system contracts.

## Boundary and rules

- Use with `salesforce-development`; keep work local and limited to the approved contract.
- Do not mutate a Salesforce org and do not make a real external call.
- Do not deploy, retrieve, change credentials, publish events, create data, or probe endpoints.
- Read `dev-rules/06_integration_rules.md`.
- Preserve provisional status, especially `DR-INT-016`.

## Inspect the boundary

- Identify direction: Salesforce-to-external callout, external-to-Salesforce REST, or event publication/subscription.
- Inspect caller, consumer, tests, configuration references, and evidence.
- Define minimum payload/API surface: schema, version, required/optional fields, size bounds, null/missing handling, compatibility, and owning system.
- Do not add future-use fields or endpoints.

## Establish integration RED

- For Apex callout code, read `apex-soql.md` and add focused positive/error tests with `HttpCalloutMock`.
- Assert method, path or Named Credential reference, payload, timeout behavior when material, response mapping, and failure outcome.
- For non-Apex boundaries, use a deterministic contract RED such as fixture/schema assertion rejecting missing fields, unsafe payload, incompatible version, unredacted log, or invalid event mapping.
- Do not make real external calls during local tests.

## Verify safety

- Never put secrets in source, logs, prompts, or evidence.
- Use Named Credential or another approved secret mechanism.
- Redact authentication values and sensitive response data.
- Verify schema, version, size, null, missing, and unexpected-field behavior.
- Define timeout, retry, backoff, idempotency, and safe retry conditions from the approved contract.
- Make error mapping explicit and observability useful while redacted.
- Inspect bulk volume, governor limits, callout-before-DML ordering, and sync/async execution.
- Verify publication separately from subscriber delivery. Keep endpoint availability, event delivery, replay, and downstream processing `[UNVERIFIED]` without runtime proof.

## Related references

- Apex callout implementation: `apex-soql.md`
- Named Credential metadata, External Credential metadata, permissions, event definitions: `metadata.md`
- Live endpoint probe, event publication, credential change, deployment, runtime setup, data change, cleanup: `salesforce-org-change` only after explicit authorization.
