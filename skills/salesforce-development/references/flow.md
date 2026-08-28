# Flow Reference

Read this for Salesforce Flow XML, Flow-only automation, record-triggered paths, Flow tests, faults, bulk behavior, recursion risk, and local deployment-state planning.

## Boundary and rules

- Use with `salesforce-development`; keep work local and minimal.
- Do not deploy, activate, deactivate, retrieve, create data, or cleanup.
- Read `dev-rules/04_flow_rules.md`.
- Preserve provisional ordering, loop, recursion, and Flow-test limitations.

## Choose the automation surface

- Use Flow for Flow-only design, elements, variables, connectors, formulas, state, paths, and local verification.
- Inspect existing Flow and Apex automation for the same object, event, and timing before choosing a record-triggered path.
- Follow Configuration-to-Flow-to-Apex selection order.
- Use before-save Flow for eligible same-record updates and after-save Flow for applicable related work.
- Route complex server logic or Apex actions to `apex-soql.md`.
- Keep metadata definitions, fields, Custom Metadata, Permission Sets, and FLS in `metadata.md`.
- Keep deploy and activation separate; activation belongs to `salesforce-org-change` after explicit authorization.

## RED and implementation

- Use Flow tests when supported by repository and affected Flow type.
- Otherwise use a deterministic RED substitute: XML assertion, missing decision outcome, fault connector, input binding, status, forbidden element, fixture validator, or graph/path inventory comparison.
- The substitute must fail for the intended pre-change reason and pass after the minimal edit.
- Mark automated Flow coverage and runtime behavior `[UNVERIFIED]` when supported Flow tests or runtime evidence are absent.

## Verify minimum

- Assert happy path and each material decision outcome.
- Inspect fault connectors and expected failure handling.
- Check bulk behavior, collection handling, and loop placement without treating provisional `DR-FLOW-008` or `DR-FLOW-009` as confirmed.
- Inspect security, FLS, object access, and Apex action access via matching references.
- Inspect recursion, same-object same-timing overlap, and re-entry conditions; record unsupported conclusions as `[UNVERIFIED]`.
- Match Apex action input names/types and avoid duplicated decision logic.
- Verify no unrelated elements, coordinates, variables, or status changes were introduced.
