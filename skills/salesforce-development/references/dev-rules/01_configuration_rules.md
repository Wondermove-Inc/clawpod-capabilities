# Configuration and Metadata Rules

Use for objects, fields, relationships, layouts, Permission Sets, Field-Level Security, Custom Metadata, and metadata XML.

| Rule ID | Level | Portable obligation |
| --- | --- | --- |
| `DR-CFG-001` | MUST | Prefer configuration when it satisfies the approved requirement; state why code is needed when moving to Flow or Apex. |
| `DR-CFG-002` | MUST | Justify every custom object, field, relationship, layout, Permission Set, and Custom Metadata field against a current requirement. |
| `DR-CFG-003` | MUST | Do not create fields or metadata for speculative future use. |
| `DR-CFG-004` | MUST | Review Field-Level Security, object permissions, and Permission Set coverage for every user-visible field or object. |
| `DR-CFG-005` | MUST | Treat Master-Detail, Lookup, requiredness, deletion behavior, ownership, and sharing implications as design decisions, not defaults. |
| `DR-CFG-006` | MUST | Keep metadata definition, permission assignment, data migration, deployment, activation, and cleanup as separate change boundaries. |
| `DR-CFG-007` | SHOULD | Use deterministic metadata validation when unit tests do not apply: XML assertion, inventory comparison, permission coverage assertion, or dependency assertion. |
| `DR-CFG-008` | MUST | Check every metadata reference used by Apex, Flow, LWC, layout, report, Permission Set, or integration contract. |
| `DR-CFG-009` | MUST | Surface destructive change, field type change, data-loss, permission, and rollback risks before mutation. |
| `DR-CFG-010` | MUST | Do not claim runtime visibility or formula behavior until measured in the target org or clearly mark it `[UNVERIFIED]`. |
| `DR-CFG-011` | PROVISIONAL | Preserve explicit metadata XML elements that protect deployability or reviewability when local evidence shows they matter; do not generalize this as a universal Salesforce requirement without official citation. |
