# Notion capability contract

`notion` v0.1.0 is a new, first-principles AgentSkill plus stdlib Python Harness around the official REST API, pinned to `Notion-Version: 2026-03-11`. Classification: **CREATE + COMPOSE** with ClawPod registry, lifecycle approval, and protected-secret infrastructure. The installed built-in Notion Skill was gap evidence only; no built-in file was copied, patched, overlaid, or modified.

The Harness emits one JSON object on stdout, centralizes validation, redaction, bounded pagination/retries/timeouts, disables mutation retries, requires preview intent hashes for writes, marks transport-uncertain mutations, and retrieves pages after supported writes. It accepts credentials only from protected runtime injection (`NOTION_TOKEN`; webhook verification uses `NOTION_WEBHOOK_SECRET`).

## Residual limits

OAuth exchange/refresh/revoke, upload byte transfer/multipart finalization, view endpoints, schema property-level CRUD, durable webhook dedupe storage, local operation journal, exact Markdown stale-content preconditions, root allowlist persistence, and live capability probing are not complete in v0.1.0. API endpoint details newly introduced in 2026-03-11 require fixture/live-read confirmation before production use. No live network, credentials, installation, trust, or external mutation was used during construction.
