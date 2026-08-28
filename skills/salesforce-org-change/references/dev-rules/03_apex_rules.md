# Apex Rules

Use for Apex classes, triggers, invocable methods, tests, async work, and callout logic.

| Rule ID | Level | Portable obligation |
| --- | --- | --- |
| `DR-APEX-001` | MUST | Keep SOQL and DML outside loops; bulk read and bulk write with collections. |
| `DR-APEX-002` | MUST | Bulk-capable entry points such as triggers, invocable methods, batch, queueable, and API handlers must accept collection-oriented input where applicable. |
| `DR-APEX-003` | MUST | Execute callouts before DML in the same transaction, or split work into a safe async/transaction boundary. |
| `DR-APEX-004` | SHOULD | Move high-volume or long-running work to async patterns when synchronous limits are material. |
| `DR-APEX-005` | MUST | Use `with sharing` for user-data classes unless an approved system-context reason is recorded. |
| `DR-APEX-006` | PROVISIONAL MUST | Make object/FLS/data access mode explicit with `WITH USER_MODE`, `as user`, or a documented access level; verify behavior with a least-privilege user before calling it proven. |
| `DR-APEX-007` | MUST NOT | Do not create dynamic SOQL injection risk; follow `DR-SOQL-005` and `DR-SOQL-006`. |
| `DR-APEX-008` | MUST NOT | Do not hardcode secrets, tokens, passwords, endpoint credentials, or private keys in Apex or metadata. |
| `DR-APEX-009` | MUST | Keep test data isolated and deterministic. |
| `DR-APEX-010` | MUST | Deployment-scope Apex must meet applicable Salesforce test success and coverage requirements. |
| `DR-APEX-011` | SHOULD | Tests should cover happy path, negative path, bulk path, and permission-sensitive behavior when material. |
| `DR-APEX-012` | MUST | Tests must create their own data and avoid `SeeAllData=true` unless a documented platform exception applies. |
| `DR-APEX-013` | MUST | Use `HttpCalloutMock` or equivalent Salesforce test mock for HTTP callout tests; never call real external services in tests. |
| `DR-APEX-014` | SHOULD | Keep trigger logic in handlers or service classes when complexity exceeds trivial validation. |
| `DR-APEX-015` | SHOULD | Keep error handling explicit, observable, and redacted. |
| `DR-APEX-016` | SHOULD | Invocable methods exposed to Flow should use list-shaped input and output when Flow may pass multiple records. |
| `DR-APEX-017` | MUST | Do not treat local test pass as org runtime proof; record deployment/runtime gaps as `[UNVERIFIED]`. |
