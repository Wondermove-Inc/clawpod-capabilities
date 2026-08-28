# Flow Runtime Verification

Flow verification must distinguish metadata facts from runtime acceptance.

## Metadata Plane

Metadata evidence can show that a Flow file exists, deploy validation succeeded, a status value is represented, or an Apex invocable binding is present. This is necessary but not sufficient for acceptance.

Check:

- Flow XML parses and contains expected elements.
- Flow status and version claims are supported by Metadata API, Tooling API, retrieve output, or deploy validation evidence.
- Apex actions reference existing `@InvocableMethod` classes and method contracts.
- Activation/deactivation is not performed under this skill.

## Runtime Plane

Runtime evidence must observe the behavior users or downstream systems depend on:

- Flow test/run output when available.
- `Flow.Interview` or equivalent approved runtime invocation with valid fixture inputs.
- SOQL-read audit records or updated records that prove the expected outcome.
- Negative and regression cases when the acceptance criterion requires them.

Do not claim success from `tests 0/0`, deploy success, metadata retrieve success, or Apex binding presence alone. If a Flow calls Apex, the runtime fixture must satisfy the Apex action's input preconditions; failed transactions can roll back earlier DML, so verify the final observable record state.

## Confirmed Sources

| Claim | Official source | API version / release | Date confirmed |
| --- | --- | --- | --- |
| Flow is a Metadata API type with status values including Active and Draft; active deployment behavior depends on org type/settings. | https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_visual_workflow.htm | 67.0 (Summer '26) | 2026-08-02 |
| FlowDefinition exposes active version metadata, but API 44.0+ guidance favors the Flow object and FlowDefinition deployment can overwrite status. | https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_flowdefinition.htm | 67.0 (Summer '26) | 2026-08-02 |
| Apex transaction failure rolls back database changes made in the transaction. | https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/langCon_apex_transaction_control.htm | 67.0 (Summer '26) | 2026-08-02 |

Project worklog basis: `docs/poc-sf-org/worklog/lessons.md` T-01, T-22, T-29, T-38, T-39, T-42, T-57, T-59, T-134, T-155, and T-156.
