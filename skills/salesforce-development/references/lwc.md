# Lightning Web Components Reference

Read this for Lightning Web Components (LWC) bundles, UI behavior, and Apex data binding.

## Boundary and rules

- Use with `salesforce-development`; keep work local and minimal.
- Do not deploy, retrieve, assign a component, change data, or create runtime state.
- Read `dev-rules/05_lwc_rules.md`.
- Preserve provisional UI guidance, especially `DR-LWC-008` and `DR-LWC-013`.

## Inspect and minimize

- Inspect the actual LWC bundle: HTML, JavaScript, metadata XML, imports, callers, and existing tests.
- Inspect bound Apex methods and permission assumptions without absorbing their implementation; read `apex-soql.md` and `metadata.md` when relevant.
- Define the minimum component and public API surface needed.
- Avoid speculative `@api` properties, events, fields, styles, targets, and components.

## Establish UI RED

- Use focused Jest only when Jest is supported and fits the affected behavior.
- Otherwise use a deterministic focused RED substitute for a missing state branch, binding, event, import, target, or accessibility attribute.
- Mark unavailable automated coverage `[UNVERIFIED]`.
- Static parsing, linting, or a source assertion proves only its own surface and is not TDD completion or UI runtime proof.
- Use browser verification only when visible or interactive behavior must be checked.

## Implement and verify UI states

- Treat explicit error handling as the confirmed `DR-LWC-006` gate.
- Implement loading, empty, and success states only when the approved request requires them; repository-standard patterns remain `[UNVERIFIED]` unless verified.
- Verify accessibility through semantic structure, labels, keyboard/focus behavior, and accessible status/error feedback when applicable.
- Do not claim client rendering enforces object access or Field-Level Security.
- For `@wire` Apex binding, verify read-only and `cacheable=true`; retain the complete wire result when refresh is required.
- Use imperative Apex only for explicitly requested data changes and call `refreshApex` when cached data must refresh.
- Never render a secret.

## Related references

- Apex data binding and Apex tests: `apex-soql.md`
- Fields, Permission Sets, FLS, layouts: `metadata.md`
- Callouts and external payloads: `integration.md`
- Flow behavior: `flow.md`
- Org mutation/runtime setup: `salesforce-org-change` only after explicit authorization.
