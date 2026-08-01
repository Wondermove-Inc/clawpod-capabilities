# Notion capability contract

`notion` v0.1.0 is a new, first-principles AgentSkill plus stdlib Python Harness around the official REST API, pinned to `Notion-Version: 2026-03-11`. Classification: **CREATE + COMPOSE** with ClawPod registry, lifecycle approval, and protected-secret infrastructure. The installed built-in Notion Skill was gap evidence only; no built-in file was copied, patched, overlaid, or modified.

## Stable execution contract

The Harness emits one JSON object on stdout. Every envelope includes `operation_id`, canonical `request_digest`, effects, retry state, warnings, and redacted errors. It centralizes command-specific validation, protected credential injection, bounded pagination/retries/timeouts, 500 KB request limits, 100-item arrays, 1,000 block elements, 2,000-character text/URL fields, presigned-URL redaction, and no automatic mutation retries.

Each write requires a canonical preview and matching intent hash. If typed `allowedRoots` are supplied, every write target or parent must be provably inside the allowlist before preview or execution. Supported page, block, data-source, and file-upload writes are verified by exact resource retrieval. Commands without a safe retrieve path explicitly return unsupported verification rather than pretending completion. Callers should journal operation ID, digest, target IDs, timestamps, and result IDs in protected state, but never credentials or full sensitive bodies.

## Easy protected onboarding

Installation begins disconnected. `auth.onboarding.plan` recommends team-owned Internal Integration, personal PAT, or planned multi-user OAuth. After explicit credential-use approval and protected `NOTION_TOKEN` injection, `auth.onboarding.verify` calls `user.me`, reports normalized bot/workspace identity, verifies 1-50 typed page/database/data-source/block roots, and returns specific 403 capability-policy or 404 missing/wrong-workspace/unshared guidance. The token is never accepted as an argument or emitted. Recovery is status → identity → exact root sharing/capability correction → bounded re-verification. Revocation occurs in Notion plus protected-pointer deletion.

`operation.plan` deterministically describes resolve → inspect → preview → approve → execute once → exact verification for any supported command, including safety, allowlist, payload, pagination, prompt-injection, and verification preflight.

## Command coverage

The typed catalog covers status/onboarding/doctor, resolve and operation planning, search, users, pages/properties/Markdown, blocks plus bounded trees, databases and contained data sources, data-source query/templates/schema update, typed page/discussion/reply comments, file-upload create/status/complete, and webhook verification/parsing. `database.list_data_sources` uses database retrieval as source of truth. `data_source.templates.list` is exposed against the documented versioned endpoint but remains fixture/live-read confirmation-dependent before production use.

## Residual limits

OAuth exchange/refresh/revoke, upload byte transfer/multipart chunk sending, view endpoints, property-level schema CRUD, durable webhook dedupe storage, persistent operation journals, exact Markdown stale-content preconditions, and persistent root-policy storage remain outside v0.1.0. Comment writes have no safe individual retrieve endpoint in this contract and report unsupported verification. The official/version behavior of templates and newly introduced 2026-03-11 fields requires approved fixture or live-read confirmation before production use. No live network, credentials, installation, trust, or external mutation was used during construction.
