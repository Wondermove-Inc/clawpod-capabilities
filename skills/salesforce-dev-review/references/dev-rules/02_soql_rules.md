# SOQL Rules

Use for static SOQL, dynamic SOQL, Tooling/setup object queries, Apex selectors, and query-only analysis.

| Rule ID | Level | Portable obligation |
| --- | --- | --- |
| `DR-SOQL-001` | MUST | Do not run SOQL inside loops; query once and index with collections. |
| `DR-SOQL-002` | MUST | Add bounded filters and limits when result size can grow, unless the query is structurally limited such as by a unique Id. |
| `DR-SOQL-003` | MUST | Select only fields that downstream code or evidence actually uses. |
| `DR-SOQL-004` | MUST | Make user-data access mode explicit with `WITH USER_MODE` when applicable, while preserving version-specific limitations. |
| `DR-SOQL-005` | MUST NOT | Do not concatenate untrusted user input into dynamic SOQL. |
| `DR-SOQL-006` | MUST | For unavoidable dynamic SOQL, validate object/field/order identifiers with allowlists or schema describe and escape only string literals. |
| `DR-SOQL-007` | SHOULD | Use relationship queries or subqueries instead of multiple ad-hoc queries when metadata relationships support it. |
| `DR-SOQL-008` | SHOULD | Use aggregate SOQL for counts or grouping instead of retrieving all rows to count in code. |
| `DR-SOQL-009` | SHOULD | Treat selectivity and large-data behavior as `[UNVERIFIED]` until official guidance or measurement supports the query plan. |
| `DR-SOQL-010` | MUST | Before querying Tooling API, setup, or metadata-like sObjects, verify the object reference, required filters, and available fields by official reference or describe output. |
