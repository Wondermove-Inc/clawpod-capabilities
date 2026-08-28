# Metadata Reference

Read this for objects, fields, relationships, layouts, Permission Sets, Field-Level Security, Custom Metadata, and metadata XML.

## Boundary and rules

- Use with `salesforce-development`; work only on minimum local metadata source.
- Do not deploy, retrieve, assign permissions, change data, or cleanup.
- Read `dev-rules/01_configuration_rules.md`.
- Preserve provisional rules such as `DR-CFG-011`.

## Inspect and plan dependencies

- Apply configuration before code when it satisfies the request.
- Inspect metadata XML, package structure, permission artifacts, source references, and validators.
- Build dependency list from requested component to current code, Flow, query, layout, Permission Set, or Custom Metadata consumer.
- First-pass dependency query: Tooling API `MetadataComponentDependency` (`sf data query --use-tooling-api`). Filter `WHERE` by component Id (`RefMetadataComponentId`), not name fields — name filters fail.
- Treat that query as partial evidence only: the object is Beta, returns at most 2,000 records per query, and omits some component types. Complete the dependency list with local source inspection; never mark impact analysis complete from this query alone.
- Do not create fields or configuration items for future consumers.
- Separate metadata definitions from assignments, runtime data, deployments, activation, and cleanup.

## Deterministic RED substitute

When unit TDD does not apply to declarative metadata, create a deterministic RED substitute before editing:

- XML structure or namespace assertion.
- Expected component, field, or reference inventory assertion.
- Dependency or Permission Set coverage assertion.
- Exact minimal-diff assertion for a layout or metadata type.
- Fixture showing a validator rejects missing or unsafe configuration.

The check must fail before the change and pass after the minimal edit.

## Implement and verify minimum

- Justify custom objects/fields.
- Choose relationship behavior deliberately.
- Keep layout changes scoped.
- Add only Custom Metadata fields already consumed by current code or Flow.
- Review Permission Set and FLS coverage with intended user visibility.
- Inspect naming, formula, object, field, and XML references.
- Review destructive changes and field type changes explicitly. Surface approval, data-loss, and rollback risks.
- Local structural success is not runtime proof; mark user visibility, permission assignment, formula evaluation, relationship behavior, or org-side metadata state `[UNVERIFIED]` unless measured.
