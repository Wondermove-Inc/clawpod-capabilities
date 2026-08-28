# Flow Rules

Use for Salesforce Flow XML, Flow tests, record-triggered automation, Flow/Apex boundaries, and activation planning.

| Rule ID | Level | Portable obligation |
| --- | --- | --- |
| `DR-FLOW-001` | MUST | Confirm Flow is the right layer after evaluating configuration and before moving to Apex. |
| `DR-FLOW-002` | MUST | Inspect existing automation for the same object, event, and timing before adding or changing a Flow. |
| `DR-FLOW-003` | MUST | Keep deploy and activation separate; activation is an org mutation requiring explicit authorization. |
| `DR-FLOW-004` | SHOULD | Move reusable or test-critical decision logic into invocable Apex when Flow-only logic cannot be verified adequately. |
| `DR-FLOW-005` | MUST | Verify Flow input names/types match Apex action signatures before deployment. |
| `DR-FLOW-006` | MUST | Add fault handling for material external calls, Apex actions, or DML paths. |
| `DR-FLOW-007` | SHOULD | Prefer before-save record-triggered Flow for eligible same-record updates; document why after-save Flow or Apex trigger is used. |
| `DR-FLOW-008` | PROVISIONAL | Inspect recursion and re-entry risk for same-object automation; do not claim safety without runtime or graph evidence. |
| `DR-FLOW-009` | PROVISIONAL MUST NOT | Avoid data access or DML inside loops as a conservative limit-control rule unless official evidence or measurement supports the design. |
| `DR-FLOW-010` | MUST | If Flow tests are unsupported or unavailable, use deterministic XML/graph/path assertions and mark runtime behavior `[UNVERIFIED]`. |
