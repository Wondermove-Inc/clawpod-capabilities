# Lightning Web Components Rules

Use for Lightning Web Components, Apex data binding, UI states, and bundle metadata.

| Rule ID | Level | Portable obligation |
| --- | --- | --- |
| `DR-LWC-001` | MUST | Apex methods used by `@wire` must be static, public/global, `@AuraEnabled`, and cacheable when the wire service requires it. |
| `DR-LWC-002` | MUST NOT | Methods marked `cacheable=true` must not perform DML or mutate data. |
| `DR-LWC-003` | MUST | Use imperative Apex calls for data-changing operations. |
| `DR-LWC-004` | MUST | Call `refreshApex()` or an approved refresh mechanism when stale wired data must update after mutation. |
| `DR-LWC-005` | MUST NOT | Do not overload `@AuraEnabled` methods exposed to LWC. |
| `DR-LWC-006` | MUST | Implement explicit user-facing error handling for material failure states. |
| `DR-LWC-007` | SHOULD | Keep public `@api` surface, custom events, imports, and state minimal. |
| `DR-LWC-008` | PROVISIONAL MUST | Keep bundle metadata explicit enough to prove target exposure and object/page scope; do not claim universal requiredness without official citation. |
| `DR-LWC-009` | SHOULD | Verify loading, empty, success, and error states when the approved UI behavior requires them. |
| `DR-LWC-010` | MUST | Do not render secrets or private payloads. |
| `DR-LWC-011` | MUST | Run relevant lint/static analysis when available and record the result. |
| `DR-LWC-012` | SHOULD | Verify accessibility with labels, semantic structure, keyboard/focus behavior, and status/error feedback when material. |
| `DR-LWC-013` | PROVISIONAL | Treat browser/runtime verification as required for visible behavior until a stronger automated UI test covers the same behavior. |
