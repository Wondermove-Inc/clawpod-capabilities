# Case and Chatter Request Rules

Use when Case and Chatter are the approved request, clarification, correction, and completion record system.

| Rule ID | Level | Portable obligation |
| --- | --- | --- |
| `DR-CASE-001` | MUST | Verify target org identity and pin command/API version before creating or updating Case/Chatter records. |
| `DR-CASE-002` | MUST | Put the baseline request in Case, and put clarifying questions that cannot be finalized by Case fields into a Chatter post linked to the Case. |
| `DR-CASE-003` | MUST | Link clarification answers as comments to the question post, preserving the parent-child relationship. |
| `DR-CASE-004` | MUST | Record correction requests and completion status with enough relationship evidence to audit request lineage. |
| `DR-CASE-005` | MUST | When assignee notification is required, use a real mention segment or platform-supported mention mechanism; do not treat plain text `@name` as proof. |

## Evidence

Portable evidence should include record IDs, relationship fields, API version, non-secret request metadata, and before/after communication state. Do not store sensitive customer content unless the approved work-record policy allows it.
