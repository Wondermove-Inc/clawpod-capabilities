# ClawPod artifact publishing contract

Verified against the admin-api and admin-portal source (`chat-artifact.service.ts`, `routes/internal.ts`, migrations 223/227/233, `generic-artifact-panel.tsx`). Nothing here is inferred from message text.

## The one rule

Artifacts are published **only** as structured fields on the outgoing `/internal/messages` request. There is no parser that scans `content` for fences, tags, or markers.

| Never do this | Result |
|---|---|
| ```` ```artifact ```` or ```` ```html ```` fences in `content` | plain text |
| `<artifact>` / `<antArtifact>` tags in `content` | plain text |
| A `/workspace/...` file path in `content` | plain text |
| `[embed ref=...]` in `content` | plain text |
| Describing the artifact in the WebUI final text | duplicate/echo; final text must be `NO_REPLY` |

## Standard flow: save, then point (`artifact_refs`)

The built-in agent guidance (migration 233) supersedes the earlier inline example: **artifact content must be saved first, and room messages carry only `artifact_refs` pointers.**

### Step 1 — write the deliverable to a workspace file

`/workspace/<slug>.html` or `/workspace/<slug>.md`.

### Step 2 — save it for an exact version pointer

```bash
python3 - <<'PY' | curl -s -X POST "http://admin-api:3000/internal/chat-rooms/$ROOM_ID/artifacts" \
  -H "Content-Type: application/json" \
  -H "X-Gateway-Token: $GATEWAY_TOKEN" \
  --data-binary @-
import json, os
payload = {
    "from_agent_id": os.environ["AGENT_ID"],
    "identifier": "q3-pricing-review",
    "type": "html",
    "title": "Q3 Pricing Review",
    "content": open("/workspace/q3-pricing-review.html", encoding="utf-8").read(),
}
# First save of a new identifier: omit expectedVersion (or set 0).
# Later save of the same identifier: set it to the exact version you stored
# from the previous save response, so a stale write is rejected with 409.
# payload["expectedVersion"] = 1
print(json.dumps(payload, ensure_ascii=False))
PY
```

Response `201`:

```json
{ "artifact": { "identifier": "q3-pricing-review", "version": 1, "type": "html", "title": "Q3 Pricing Review", "preview": "…", "createdAt": "…" } }
```

Store `version` per identifier. Piping the JSON from Python keeps quotes, newlines, and Korean text intact — never build the body with shell string interpolation.

### Step 3 — send the room message with the pointer

```bash
curl -s -X POST http://admin-api:3000/internal/messages \
  -H "Content-Type: application/json" \
  -H "X-Gateway-Token: $GATEWAY_TOKEN" \
  -d "{\"from_agent_id\":\"$AGENT_ID\",\"room_id\":$ROOM_ID,\"content\":\"Q3 가격 검토 보고서를 정리했습니다.\",\"artifact_refs\":[{\"identifier\":\"q3-pricing-review\",\"version\":1}]}"
```

Then the WebUI final output is exactly `NO_REPLY`.

### Reading a saved artifact back

```bash
curl -s -X GET "http://admin-api:3000/internal/chat-rooms/$ROOM_ID/artifacts/q3-pricing-review?from_agent_id=$AGENT_ID" \
  -H "X-Gateway-Token: $GATEWAY_TOKEN"
# add &version=N for an exact older version
```

Returns `{"artifact": {identifier, version, type, title, content, …}}`. There is no endpoint that lists every identifier in a room; you must already know the identifier.

## Legacy mode: inline `artifacts`

`POST /internal/messages` still validates and persists an inline `artifacts: [{identifier, type, title, content}]` array (subscriber inserts `MAX(version)+1`). The runtime guidance has retired it in favour of the pointer flow. Use it only if the current room instructions explicitly still show the inline form; never combine it with `artifact_refs`.

## Field contract (zod, `chat-artifact.service.ts`)

| Field | Rule |
|---|---|
| `identifier` | trimmed, `^[A-Za-z0-9][A-Za-z0-9_.-]*$`, 1–120 chars. The versioning key per room. |
| `type` | `markdown` or `html`. Nothing else (also a DB `CHECK`). |
| `title` | trimmed, 1–200 chars. |
| `content` | 1–200,000 chars (`MAX_CHAT_ARTIFACT_CONTENT_CHARS`). Data URIs count. |
| `from_agent_id` | required on the save endpoint; the agent must be a participant of the room. |
| `expectedVersion` | optional integer ≥ 0 on save. Omitted or `0` → unconditional save. Non-zero and ≠ latest → `409 { error, latestVersion }`. |
| `artifact_refs[].version` | positive integer, the exact value from the save response. There is no `"latest"`. |
| `preview` | never sent. Server: strip `<[^>]*>` → collapse whitespace → first 240 chars. |

## Limits and guards (`routes/internal.ts`)

- Max **5** items in `artifacts` or `artifact_refs` (`MAX_CHAT_ARTIFACTS_PER_MESSAGE`).
- `artifacts` + `artifact_refs` in one request → `400 "validation: artifacts and artifact_refs cannot both be set"`.
- Artifact fields without `room_id` → `400 "artifacts are only supported for room messages"`.
- Sender is a `webhook:`/`tasks:` system id → `400 "artifacts are only supported for agent room messages"`.
- A ref that does not resolve in this room → `404`; the whole message is rejected before publish.
- Missing/invalid `X-Gateway-Token` → `401`; unknown agent → `404`; not a participant → `403`.

## Versioning semantics

- Same room + same identifier = one lineage; each accepted save becomes the next version under an advisory lock.
- **Content-addressed no-op**: saving content whose `type`, `title`, and `content` equal the latest version returns that existing version and creates nothing.
- Revision of the same deliverable → same identifier (the panel offers a version picker). Distinct deliverable → new identifier, even with a similar title.
- Slug from the subject (`onboarding-plan-2026q4`), not from the type (`report-1`).

## Data flow (for diagnosing a missing card)

```
agent → POST /internal/chat-rooms/:roomId/artifacts   (save → version)
agent → POST /internal/messages { artifact_refs }
      → gateway token, agent, participant checks
      → refs resolved to a manifest (404 on miss)
      → NATS chat.{roomId}.messages
      → subscriber stores the manifest on the message
      → portal: GenericArtifactCard (title + 240-char preview) → click → GenericArtifactPanel
```

If the message arrived but no card shows, the artifact was not in the structured field.

## Decision rule (the runtime's mandatory room rule)

Decide from the output shape, not from the user's wording. Create an artifact when the useful output is substantial, self-contained, and likely to be reused, edited, downloaded, or reopened. Use plain `content` for short answers, status updates, explanations, casual conversation, and anything ambiguous.
