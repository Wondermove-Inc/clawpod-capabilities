# Notion capability contract

`notion` v0.1.1 is a new, first-principles AgentSkill plus stdlib Python Harness around the official REST API, pinned to `Notion-Version: 2026-03-11`. Classification: **CREATE + COMPOSE** with ClawPod registry, lifecycle approval, and protected-secret infrastructure. The installed built-in Notion Skill was gap evidence only; no built-in file was copied, patched, overlaid, or modified.

## Stable execution contract

The current Gateway serializer requires `valueType: string` inputs to already be strings; it does not JSON-encode object/array values. The public Harness schema therefore accepts structured bodies and root lists as JSON strings, while `command_contracts.json` retains their full object/array schemas. `notion.py` parses and revalidates them before use. `scripts/update_notion_transport.py` regenerates both layers and rejects value types outside `string`, `number`, `integer`, `boolean`, `enum`, and `path`.

Gateway command inputs retain their typed object/array JSON Schemas. The scalar-only Gateway `argMap` contract transports those structured values as canonical JSON strings to `notion.py`, which parses and revalidates bodies and root lists before use. `scripts/update_notion_transport.py` regenerates this mapping and rejects value types outside `string`, `number`, `integer`, `boolean`, `enum`, and `path`.

The Harness emits one JSON object on stdout. Every envelope includes `operation_id`, canonical `request_digest`, effects, retry state, warnings, and redacted errors. It centralizes command-specific validation, protected credential injection, bounded pagination/retries/timeouts, 500 KB request limits, 100-item arrays, 1,000 block elements, 2,000-character text/URL fields, presigned-URL redaction, and no automatic mutation retries.

Each write requires a canonical preview and matching intent hash. If typed `allowedRoots` are supplied, every write target or parent must be provably inside the allowlist before preview or execution. Supported page, block, data-source, and file-upload writes are verified by exact resource retrieval. Commands without a safe retrieve path explicitly return unsupported verification rather than pretending completion. Callers should journal operation ID, digest, target IDs, timestamps, and result IDs in protected state, but never credentials or full sensitive bodies.

## Resumable protected onboarding

Installation begins disconnected. Read-only `onboard.plan` recommends team-owned Internal Integration, personal PAT, or bounded OAuth navigation. `onboard.start/status/inspect/resume/cancel` implement an atomic, mode-0600, secret-free, revisioned state machine with idempotent restart, stale-revision rejection, timeout, cancellation cleanup, and exact handoffs. State is confined beneath an existing owner-only `outputRoot` using bounded relative `session` and `stateName` values; traversal, symlink roots/children/files, missing or non-private roots, and non-regular targets fail closed. Production commands expose no arbitrary fixture path.

Read-only `onboard.desktop.plan/task` emits the concrete desktop-layer task: navigate to Notion integration settings, fill only safe fields, verify the exact workspace and minimum capabilities between actions, connect exact roots, and stop before final submit/permission/root confirmations. It always stops on CAPTCHA/human verification, UI drift, and secret fields. It prohibits screenshots, DOM capture, and token scraping. Provider selectors are explicitly not live-validated; recovery reports the last verified step and visible non-secret labels. Test-only fixtures require explicit internal test environment gates and never perform live browser actions.

The capability never scrapes or stores a token. It emits `secret_capture_required`; the owner agent captures the value into protected secret storage and injects `NOTION_TOKEN` only at runtime. `auth.onboarding.verify` then calls `user.me`, verifies the workspace and 1-50 typed roots, returns specific 403/404 guidance, establishes `allowedRoots`, and supports a bounded read-only smoke. Audit/state redaction excludes credentials and secret-bearing screens. Revocation means provider revocation/root disconnect, protected-pointer deletion, and local cancellation.

`operation.plan` deterministically describes resolve → inspect → preview → approve → execute once → exact verification for any supported command, including safety, allowlist, payload, pagination, prompt-injection, and verification preflight.

## Command coverage

The typed catalog covers status/onboarding/doctor, resolve and operation planning, search, users, pages/properties/Markdown, blocks plus bounded trees, databases and contained data sources, data-source query/templates/schema update, typed page/discussion/reply comments, file-upload create/status/complete, and webhook verification/parsing. `database.list_data_sources` uses database retrieval as source of truth. `data_source.templates.list` is exposed against the documented versioned endpoint but remains fixture/live-read confirmation-dependent before production use.

## Residual limits

OAuth provider-client registration/exchange/refresh/revoke, live browser automation validation, upload byte transfer/multipart chunk sending, view endpoints, property-level schema CRUD, durable webhook dedupe storage, persistent operation journals, exact Markdown stale-content preconditions, and persistent root-policy storage remain outside v0.1.0. Comment writes have no safe individual retrieve endpoint in this contract and report unsupported verification. The official/version behavior of templates and newly introduced 2026-03-11 fields requires approved fixture or live-read confirmation before production use. No live network, credentials, installation, trust, or external mutation was used during construction.
