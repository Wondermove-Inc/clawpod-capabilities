# Integration Rules

Use for callouts, REST APIs, Platform Events, Named Credentials, payloads, external-system contracts, and retries.

| Rule ID | Level | Portable obligation |
| --- | --- | --- |
| `DR-INT-001` | MUST | Identify integration direction, owner, version, schema, and system boundary before implementation. |
| `DR-INT-002` | MUST | Use Named Credential or another approved secret mechanism for external authentication. |
| `DR-INT-003` | MUST NOT | Do not hardcode, log, paste, or expose secrets. |
| `DR-INT-004` | MUST | Validate payload schema, required/optional fields, null/missing behavior, and unexpected-field behavior. |
| `DR-INT-005` | MUST | Keep outbound payloads minimized and redacted. |
| `DR-INT-006` | MUST | Define timeout, retry, backoff, idempotency, and safe retry boundaries when retry is in scope. |
| `DR-INT-007` | MUST | Map errors explicitly and preserve useful redacted diagnostics. |
| `DR-INT-008` | MUST | For Apex callouts, test with `HttpCalloutMock`; do not use real external endpoints in unit tests. |
| `DR-INT-009` | MUST | Keep callout-before-DML and transaction-boundary rules explicit. |
| `DR-INT-010` | SHOULD | Separate publication success from subscriber delivery success for event-based integration. |
| `DR-INT-011` | MUST | Do not treat endpoint reachability, event delivery, or downstream processing as verified without runtime proof. |
| `DR-INT-012` | SHOULD | Maintain compatibility strategy for versioned contracts. |
| `DR-INT-013` | MUST | Verify permissions and metadata references for Named Credentials, External Credentials, endpoints, and event objects when applicable. |
| `DR-INT-014` | MUST | Avoid real external calls during local development verification. |
| `DR-INT-015` | SHOULD | Define observability fields that do not leak sensitive payloads. |
| `DR-INT-016` | PROVISIONAL | Treat platform-event replay, delivery timing, and subscriber processing assumptions as `[UNVERIFIED]` until measured in the target environment. |
