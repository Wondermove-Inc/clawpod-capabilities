# Write an agent snapshot

Run this from the authorized agent process, never inside HTML. Use the runtime's existing internal API base URL and gateway token. Do not print the token or embed it in output files. The agent must participate in the room; the artifact identifier must already exist there.

```sh
# Fail before curl if preparing or validating JSON fails.
set -e
# Set ROOM_ID and ARTIFACT_IDENTIFIER for the authorized target.
# ADMIN_API_URL, AGENT_ID and GATEWAY_TOKEN come from the existing runtime.
# GATEWAY_TOKEN authenticates the Admin API; OPENCLAW_GATEWAY_TOKEN is a different credential.
python3 - <<'PYTHON' > /tmp/live-artifact-body.json
import json, os
with open("snapshot.json", encoding="utf-8") as file:
    data = json.load(file)
encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
if len(encoded) > 65536:
    raise SystemExit("Snapshot exceeds 65536 UTF-8 bytes")
print(json.dumps({"from_agent_id": os.environ["AGENT_ID"], "schemaVersion": 1, "data": data}, ensure_ascii=False))
PYTHON
curl --fail-with-body --silent --show-error \
  --request PUT \
  --header "X-Gateway-Token: ${GATEWAY_TOKEN}" \
  --header 'Content-Type: application/json' \
  --dump-header /tmp/live-artifact-response.headers \
  --data-binary @/tmp/live-artifact-body.json \
  "${ADMIN_API_URL}/internal/chat-rooms/${ROOM_ID}/artifacts/${ARTIFACT_IDENTIFIER}/data"
```

Use the actual runtime endpoint and an URL-safe stable identifier. The body is `{from_agent_id, schemaVersion: 1, data}`; success is `200 {data:{revision}}`. Do not use guessed endpoints or browser credentials. Remove temporary body/header files after use; data must be appropriate for room participants.

Writes are limited to one successful write per second for each room/identifier, plus 120/minute per room and 120/minute per agent. The per-key interval is enforced atomically by PostgreSQL. Aggregate limits reuse the existing Redis rate limiter: initialization failure falls back to process memory and Redis runtime errors are fail-open. Do not treat aggregate throttling as a guaranteed distributed quota during outages. Maintain only the newest pending snapshot and send it when allowed. On `429`, wait the response's `Retry-After` seconds; do not busy-loop or send the accumulated backlog. Last successful write wins, including writes by other participating agents. On `404`, confirm the room/artifact exists before retrying. On `413`, reduce the encoded snapshot. Read other English error messages and correct the request; do not retry authorization failures blindly.

Weather integrations fetch externally in the agent process and push a compact snapshot such as `{ "city": "Seoul", "temperatureC": 21, "observedAt": "2026-09-30T00:00:00Z" }`. External providers must not call the shared-token internal endpoint directly. Schedule updates only if the task authorizes a persistent process.

Use the same schemaVersion as the HTML manifest schemaVersions["agent.data"]. Additive optional fields keep the version; field removals, type or meaning changes require a new version and compatible HTML. Verify the server and Portal support schema version checks before writing versions above 1; older servers can ignore the field. The server stores the declared version but does not validate arbitrary payloads against a registered JSON Schema.
