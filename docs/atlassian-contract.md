# Atlassian Cloud capability contract

The capability exposes 26 service-namespaced commands over Jira Cloud REST v3 and Confluence Cloud REST v2, with v1 limited to CQL search and attachment upload where v2 lacks equivalents. `command_contracts.json` is generated and is the machine-readable inventory.

All output is a JSON envelope with `ok`, `schemaVersion`, `command`, `requestId`, `effects`, `provenance`, and either `data` or a stable `error` (`code`, `message`, `retryable`, `ambiguousCommit`). Secrets are reference-only and recursively redacted.

Reads have bounded 30-second timeouts and at most three retries for 429/502/503/504, honoring bounded `Retry-After`. Mutations never execute without a one-time, installation-key-bound durable confirmation issued by a successful dry-run, fingerprinted to site, command, and request, and valid for five minutes. Network/timeout failure after a mutation is marked ambiguous and must be reconciled before retry. Attachment paths must remain beneath an explicit transfer root and cannot be symlinks. Site aliases bind an HTTPS origin and credential provider, preventing cross-tenant credential selection.

Official semantic sources: Atlassian Jira Cloud REST API v3 reference, Confluence Cloud REST API v2 reference, Confluence Cloud REST API v1 search and content attachment references, and Atlassian Cloud rate-limit guidance.
