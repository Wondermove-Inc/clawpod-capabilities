# Errors and recovery

Classify failures before retrying:

- Input/contract: `INVALID_ARGUMENT`, `NOT_FOUND`, `CONFLICT`, `SCHEMA_VIOLATION`, `UPSTREAM_CONTRACT_INVALID`, `TOOL_NOT_FOUND`, `TOOL_NOT_ALLOWED`.
- Runtime/integrity: `RUNTIME_NOT_FOUND`, `DIGEST_MISMATCH`, `PLAINTEXT_SECRET_FILE_FORBIDDEN`, `DEPENDENCY_FAILURE`, `PATH_VIOLATION`, `SECRET_FILE_PERMISSIONS`.
- Credential/provider: `AUTH_REQUIRED`, `AUTH_INVALID`, `VERIFIER_UNAVAILABLE`, `PROVIDER_UNAVAILABLE`, `UPSTREAM_TOOL_FAILED`, `UPSTREAM_EXCEPTION`, `UPSTREAM_PROTOCOL_ERROR`.
- Approval/cost: `APPROVAL_REQUIRED`, `COST_CEILING_REQUIRED`, `COST_CEILING_EXCEEDED`, `GATE_PENDING`.
- Lifecycle: `TIMEOUT`, `CANCELLED`, `PARTIAL_FAILURE`, `WORKER_LOST_OR_PID_REUSED`, `OWNERSHIP_MISMATCH`, `BACKLOT_START_FAILED`, `INTERNAL_ERROR`.

Never retry input, contract, auth, approval, cost, path, digest, permission, ownership, or schema failures unchanged. Retry only explicitly retryable network/provider failures and honor provider backoff. Never resubmit a paid request when provider acceptance is ambiguous.

Preserve partial outputs and the exact completed-operation checkpoint. Report attempted stage/tool, plan and operation digests, known spend, artifact state, external-side-effect ambiguity, retry safety, and exact recovery action. Resume only when the pipeline manifest, plan digest, runtime digest, provider set, approval ceiling, and prior checkpoint still match. Re-approval is required when provider, model, operation, input, quantity, cost ceiling, or expiry changes.
