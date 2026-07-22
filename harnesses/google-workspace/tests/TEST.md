# Google Workspace harness test plan

Tests use synthetic `.invalid` identities and scripted HTTP only. They cover manifest inventory and safety, closed schemas, CLI discovery, one-object output, previews and confirmations, account selection, credential file permissions, request mapping, provider error taxonomy, retry behavior, pagination, MIME/header defense, calendar zone/recurrence validation, ETags, atomic transfer output, traversal/symlink rejection, and audit/secret redaction. No test calls Google or loads production credentials.

Manual protected E2E remains required before release: incremental OAuth consent, refresh/revocation, controlled Gmail draft/send, dedicated Calendar CRUD, isolated Drive resumable transfer/share/revoke, and test receiver channel lifecycle. Permanent delete, transfer ownership, and admin sharing require separate approval.
