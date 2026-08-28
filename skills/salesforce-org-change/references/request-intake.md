# Request Intake Reference

Use before planning or executing any Salesforce org mutation.

## Intake Checklist

Confirm the request includes:

- requester or approving role;
- business reason and linked work item, Case, or Chatter thread when that is the approved tracking system;
- operation type: deploy, retrieve, activate/deactivate, data change, permission assignment, endpoint probe, event publication, credential/endpoint metadata change, cleanup, or rollback;
- exact target Salesforce org: org ID plus alias or username, environment type, and expected user;
- approved component, record, permission, endpoint, event, or cleanup scope;
- execution timing or window;
- success criteria and required evidence;
- stop conditions;
- rollback or bounded cleanup expectation.

If any item is missing, ambiguous, or conflicts with the observed org identity, do not mutate. Ask for a decision and provide only a read-only plan.

## Safety Notes

- Treat Salesforce deploy, retrieve, activation/deactivation, data create/update/delete, permission assignment, live endpoint probe, event publication, and cleanup as mutating.
- Verify target identity with read-only commands before and immediately before execution.
- Pin every mutating Salesforce command with `--target-org` or `-o`.
- Prefer check-only or dry-run validation.
- Preserve before/after state from the same surface.
- Record operation IDs and exact commands with secrets removed.
- Never include secrets, tokens, credentials, or private payload data in evidence or reports.
