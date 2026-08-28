# Activation, Data, Assignment, Cleanup, Endpoint, and Event Reference

Use only after explicit authorization for the named operation.

## Covered mutation surfaces

- Flow or automation activation/deactivation.
- Data create/update/delete.
- Permission or access assignment.
- Cleanup or compensating metadata/data change.
- Live endpoint probe.
- Event publication.
- Credential or endpoint metadata changes.

## Controls

- Keep each mutation surface as a separate unit unless approval explicitly combines them.
- Capture before and after state from the same surface.
- For Flow activation, preserve deployment state separately from activation state.
- For data changes, record object, record IDs, field scope, row count, and rollback/cleanup plan.
- For assignments, record assignee, permission artifact, scope, and before/after access evidence.
- For endpoint probes, never print secrets; record HTTP status, non-sensitive request/response summary, and redaction evidence.
- For event publication, separate publish result from subscriber delivery. Subscriber delivery remains `[UNVERIFIED]` without runtime proof.
- For cleanup, record cleanup ID or exact command/result and verify after state.

Do not call the operation complete until the approved success criteria and required after-state evidence are present.
