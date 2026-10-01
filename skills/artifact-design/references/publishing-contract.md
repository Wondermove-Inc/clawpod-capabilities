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

### Save the file, then publish its returned pointer

Set `ROOM_ID`, `ARTIFACT_FILE`, `ARTIFACT_IDENTIFIER`, `ARTIFACT_TITLE`, `ARTIFACT_TYPE` (`html` or `markdown`), and `MESSAGE_CONTENT` (in the user's language) for the current authorized room. Runtime provides `ADMIN_API_URL`, `GATEWAY_TOKEN`, and `AGENT_ID`. Export those task variables so Python sees them. For an update, export `EXPECTED_VERSION` from the last read; omit it for a first save.

```bash
set -euo pipefail
: "${ADMIN_API_URL:?}" "${GATEWAY_TOKEN:?}" "${AGENT_ID:?}" "${ROOM_ID:?}"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
python3 - <<'PYTHON' > "$work/save.json"
import json, os
payload = {
    "from_agent_id": os.environ["AGENT_ID"],
    "identifier": os.environ["ARTIFACT_IDENTIFIER"],
    "type": os.environ["ARTIFACT_TYPE"],
    "title": os.environ["ARTIFACT_TITLE"],
    "content": open(os.environ["ARTIFACT_FILE"], encoding="utf-8").read(),
}
if os.environ.get("EXPECTED_VERSION"):
    payload["expectedVersion"] = int(os.environ["EXPECTED_VERSION"])
print(json.dumps(payload, ensure_ascii=False))
PYTHON
curl --fail-with-body --silent --show-error --request POST \
  "${ADMIN_API_URL}/internal/chat-rooms/${ROOM_ID}/artifacts" \
  --header "X-Gateway-Token: ${GATEWAY_TOKEN}" \
  --header 'Content-Type: application/json' \
  --data-binary @"$work/save.json" > "$work/saved.json"
python3 - "$work/saved.json" <<'PYTHON' > "$work/message.json"
import json, os, sys
artifact = json.load(open(sys.argv[1], encoding="utf-8"))["artifact"]
if artifact["identifier"] != os.environ["ARTIFACT_IDENTIFIER"] or type(artifact["version"]) is not int or artifact["version"] < 1:
    raise SystemExit("Invalid artifact save response")
print(json.dumps({
    "from_agent_id": os.environ["AGENT_ID"],
    "room_id": int(os.environ["ROOM_ID"]),
    "content": os.environ["MESSAGE_CONTENT"],
    "artifact_refs": [{"identifier": artifact["identifier"], "version": artifact["version"]}],
}, ensure_ascii=False))
PYTHON
curl --fail-with-body --silent --show-error --request POST \
  "${ADMIN_API_URL}/internal/messages" \
  --header "X-Gateway-Token: ${GATEWAY_TOKEN}" \
  --header 'Content-Type: application/json' \
  --data-binary @"$work/message.json"
```

The save response is `201 {"artifact": {"identifier": "…", "version": 1, …}}`. After the message succeeds, final output is exactly `NO_REPLY`. Never use a file attachment instead of `artifact_refs`. JSON preparation failures stop before curl. Credentials are used in headers only and never put in payload files or printed.

### Recover the pointer after a failed message

```bash
curl --fail-with-body --silent --show-error \
  "${ADMIN_API_URL}/internal/chat-rooms/${ROOM_ID}/artifacts/${ARTIFACT_IDENTIFIER}?from_agent_id=${AGENT_ID}" \
  --header "X-Gateway-Token: ${GATEWAY_TOKEN}"
# Add &version=N for an exact older version.
```

Use that returned version for the room message. Do not resend successfully published messages automatically, since this flow does not introduce a message idempotency key.

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
