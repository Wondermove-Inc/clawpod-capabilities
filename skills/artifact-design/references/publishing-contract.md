# ClawPod artifact publishing contract

Load this before the first publish in a session. It records how the ClawPod admin-api actually accepts artifacts; nothing here is inferred from message text.

## The one rule

Artifacts are published **only** as structured fields on the outgoing message. There is no parser that scans the message body for fences, tags, or markers.

| Never do this | Result |
|---|---|
| ```` ```artifact ```` or ```` ```html ```` fences in the body | plain text |
| `<artifact>` / `<antArtifact>` tags in the body | plain text |
| A workspace file path in the body | plain text |
| `[embed ref=...]` in the body | plain text |

## Where artifacts are accepted

- `POST /internal/messages` (admin-api), for **room messages and agent messages** only.
- Use the runtime's message-send tool that exposes these fields; do not construct raw HTTP calls with guessed base URLs or tokens.

## Two publishing modes

### 1. Inline — `artifacts`

Use for content authored in this turn (the normal case for this Skill).

```json
{
  "artifacts": [
    {
      "identifier": "q3-pricing-review",
      "type": "html",
      "title": "Q3 Pricing Review",
      "content": "<!doctype html>..."
    }
  ]
}
```

### 2. Save first, then point — `artifact_refs`

Preferred for **file outputs** (workspace files, generated documents). The current runtime guidance prioritises this mode for files.

1. `POST /internal/chat-rooms/:roomId/artifacts` with the same `identifier / type / title / content` body. Include `expectedVersion` when updating an existing artifact; a mismatch returns `409`.
2. Read `identifier` and `version` from the response.
3. Send the message with `artifact_refs: [{ "identifier": "...", "version": N }]`.

The server verifies each ref exists and belongs to the same room before accepting the message.

## Field contract

| Field | Rule |
|---|---|
| `identifier` | `^[A-Za-z0-9][A-Za-z0-9_.-]*$`, 1–120 chars. Stable per deliverable; it is the versioning key. |
| `type` | `markdown` or `html`. No other value exists (enforced by a DB CHECK). |
| `title` | 1–200 chars. Required. |
| `content` | 1–200,000 chars. Required. Data URIs count. |
| `preview` | Do **not** send. The server strips HTML from `content` and stores the first 240 characters. |
| `version` | Do not send on inline publishes. Re-sending an existing identifier stores `MAX(version) + 1` under an advisory lock. |

## Limits

- At most **5** artifacts per message (`MAX_CHAT_ARTIFACTS_PER_MESSAGE`).
- `artifacts` and `artifact_refs` are **mutually exclusive** in one message.
- `artifact_refs` must resolve within the current room.

## Data flow (for diagnosing a missing card)

```
agent → POST /internal/messages (artifacts | artifact_refs)
      → ref existence + room check
      → NATS publish chat.{roomId}.messages
      → subscriber inserts new chat_artifacts version
      → front-end GenericArtifactCard → click → generic-artifact-panel
```

If the message arrived but no card shows, the artifact was not in the structured field.

## Versioning guidance

- Same deliverable revised → same `identifier`. The room keeps the history; the card shows the latest.
- Different deliverable → new `identifier`, even if the title is similar.
- Slug the identifier from the subject (`onboarding-plan-2026q4`), not from the type (`report-1`).

## Decision rule (from the runtime's mandatory room rule)

Do not wait for the user to say "artifact". If the output is substantive, self-contained, and worth reusing, editing, downloading, or reopening, publish it as an artifact.
