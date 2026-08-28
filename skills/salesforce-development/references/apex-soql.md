# Apex and SOQL Reference

Read this for Apex classes, triggers, tests, governor-limit work, and SOQL-only query changes or reviews.

## Boundary and rules

- Use with `salesforce-development`; do not treat this reference as a standalone approval path.
- Do not mutate a Salesforce org.
- Read `dev-rules/02_soql_rules.md` and `dev-rules/03_apex_rules.md`.
- Preserve provisional status; do not turn unresolved standards into confirmed gates.

## Inspect and plan

- Inspect actual Apex source, callers, queried objects/fields, and existing tests.
- For SOQL-only work, inspect query context, downstream field use, expected cardinality, and evidence without inventing an Apex deliverable.
- Inspect existing Flow and trigger automation on the same object/event when overlap matters.
- State why Apex or SOQL is needed after considering Configuration and Flow under `DR-CMN-006`.
- Define the smallest source and test scope.

## Minimal TDD

- RED: smallest focused Apex test or SOQL validator for the approved behavior.
- GREEN: smallest Apex/query change.
- BLUE: compare actual diff with `DR-APEX-*`, `DR-SOQL-*`, and `DR-CMN-*`; remove unsupported logic.

Test scope should cover changed classes/triggers, affected callers, major branches, invalid/empty input where applicable, bulk input for bulk-capable entry points, and permission-sensitive behavior when material.

Tests must create their own data and must not use `SeeAllData=true`. Use `HttpCalloutMock` for callout paths and read `integration.md` for the external contract.

## Verify Apex and SOQL

- Keep bulk-capable entry points list- or map-based.
- Keep SOQL and DML outside loops.
- Inspect governor limits, callout-before-DML ordering, and sync/async boundaries.
- Use `with sharing` for user-data classes where required; treat Field-Level Security (FLS) and object access separately.
- Make data access intent explicit with `WITH USER_MODE`, `as user`, or the applicable access level without overstating provisional `DR-APEX-006`.
- Prefer static SOQL and bind variables. For unavoidable dynamic SOQL, validate identifiers and escape only string literals as the canonical rule specifies.
- Do not invent selectivity thresholds. Require official evidence or measurement and label missing large-data selectivity proof `[UNVERIFIED]`.

## Related references

- Flow automation overlap: `flow.md`
- Metadata, fields, Permission Sets, FLS: `metadata.md`
- Callouts, Named Credentials, Platform Events, REST: `integration.md`
- Org mutation: `salesforce-org-change` only after explicit authorization.
