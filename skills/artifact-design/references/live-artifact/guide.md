# Live artifact (protocol v1)

Create one self-contained HTML file. Use a static artifact for a fixed report; use live mode only when data changes independently of the HTML. This reference extends [artifact-design](../../SKILL.md). Reuse its [design fundamentals](../design-fundamentals.md) and [publishing contract](../publishing-contract.md).

## Workflow

1. Choose the source. Use `agent.data` for an agent-produced JSON snapshot; use `org-package.checklist` for the checklist in its installation-owned room. Read [the contract](references/contract.md) for payloads and failure behavior.
2. Treat sample payload fields as examples, adapting them to the requested widget rather than imposing unrelated city or schema constraints. Start from [weather.html](samples/weather.html) or [checklist.html](samples/checklist.html). Add exactly one real head element:
   ```html
   <meta name="clawpod-live" content='{"v":1,"keys":["agent.data"],"schemaVersions":{"agent.data":1}}'>
   ```
   Declare only needed keys, at most eight. Declare each key's supported data version in schemaVersions; use 1 for the checklist display projection. The PUT schemaVersion must match agent.data's declared version. Missing declarations are legacy v1. Unknown keys and unsupported versions prevent execution. Comments and code examples do not count as a manifest.
3. Use the injected SDK; do not embed your own bridge. Check `clawpod.apiVersion === 1`, call `clawpod.ready()`, then `clawpod.data.subscribe(key, callback)`. The return value unsubscribes. The callback receives `(payload, meta)` where `meta` contains `revision`, `schemaVersion`, `kind: 'snapshot'`, and `stale`; failures pass `null` and `{error: code}`. Render missing/error/stale states. Keep the last rendered value when `meta.error` is `unavailable` or `rate_limited`, with a delayed-update notice; these follow stale snapshots. Clear displayed data on terminal `forbidden`, `gone`, `too_large`, or `schema_mismatch` errors. A null snapshot can be valid agent data, so use a schema check before accessing fields.
4. Replace the displayed state on each snapshot. Revision conveys order; never infer changed data solely from revision. Display dynamic strings with `textContent` and construct elements with DOM APIs. Do not insert data through `innerHTML`.
5. Keep scripts/styles inline, images/fonts embedded as data URLs. No fetch, XMLHttpRequest, WebSocket, external URL/CDN, navigation, forms, or secrets in HTML/data. The parent owns polling; do not poll inside the iframe. Sandbox restrictions do not make received data secret: navigation leakage remains a known platform limitation.
6. Run `node scripts/check-live-artifact.mjs <output.html>` relative to this reference directory. It is conservative authoring lint, not a security validator or runtime test. Review the result, then test the actual portal sandbox when available.
7. Save the HTML with `POST /internal/chat-rooms/:roomId/artifacts`, then publish its returned identifier/version in `POST /internal/messages` as `artifact_refs` before writing `agent.data`. Read [the shared publishing contract](../publishing-contract.md). A file attachment or path is not an artifact card. Keep its identifier stable. Read [writing data](references/write-data.md) for the JSON-safe curl example. Use the existing runtime `ADMIN_API_URL`, `AGENT_ID`, and Admin API `GATEWAY_TOKEN`; `OPENCLAW_GATEWAY_TOKEN` is a different credential for the agent gateway protocol. Abort before curl if JSON preparation fails. Only push the latest snapshot, coalesce locally, and obey `Retry-After`. Updating data does not create an HTML version.
8. Explain in the user's language that clicking the artifact card opens the live view. After a successful room message send, final output is exactly `NO_REPLY`. Do not claim publication before both save and message send succeed. This skill grants no new access or deployment permission.

For a malformed manifest, correct the version/keys and remove network code rather than weakening the sandbox. Do not weaken the sandbox to make invalid HTML run.

## Language and onboarding

Use the user's requested language for visible HTML text, status labels, and artifact title. Set `<html lang="ko">` for Korean (or the requested locale); preserve identifiers and protocol keys. File contents can contain localized UI strings even when identifiers must remain unchanged. Prefer checklist `displayTitle[locale]` / `displayText[locale]`, then their English display values, then the original title/text.

The platform creates the default onboarding card. Do not publish a duplicate. After changing progress, run `/opt/clawpod/bin/checklist save <candidate.json>` to validate, back up, atomically save, and sync the checklist. Use `/opt/clawpod/bin/checklist sync` to retry a failed sync without editing again. Read the checklist first after restart. Do not use the `agent.data` write endpoint for the platform checklist.
