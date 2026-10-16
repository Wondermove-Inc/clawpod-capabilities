# Find, read, and revise artifacts

Use this page when the user asks which artifacts exist, what an artifact contains, or what changed between its versions, or asks you to edit one. Verified against admin-api source (`routes/internal.ts`, `routes/chat-rooms.ts`, `chat-artifact.service.ts`). Run the matching command below directly. Do not probe other URLs: the endpoints listed here are the only artifact reads an agent can use.

## What an agent can and cannot query

| Need | Agent path | Notes |
|---|---|---|
| Rooms you participate in | `GET /internal/agent-rooms?agent_slug=$AGENT_ID` | Returns `{rooms:[{id, name, room_type, last_message_at, participant_slugs, …}], count}`. |
| One artifact, latest version | `GET /internal/chat-rooms/$ROOM_ID/artifacts/<identifier>?from_agent_id=$AGENT_ID` | Full record including `content`. |
| One artifact, exact version | same URL plus `&version=N` | `N` ≥ 1. Every version stays readable. |
| Artifacts you saved, in any room | the save ledger (`$ARTIFACT_LEDGER`, below) | One local file read; no API call. |
| **All artifacts in a room** | **not available to agents** | `GET /api/chat-rooms/:id/artifacts` exists only for signed-in people (portal JWT). An agent gets `401`. |
| **Version list of an identifier** | **not available as one call** | `GET /api/chat-rooms/:id/artifacts/:identifier/versions` is also people-only. Read versions `1…latest` individually (below). |
| **Filter by author** | **not supported** | Responses never include who saved an artifact. Your ledger is the only record of what you wrote. |
| **Search by title or content** | **not supported** | Filter your ledger locally; for anything else you need the identifier. |

All agent calls use `--header "X-Gateway-Token: $GATEWAY_TOKEN"`. Runtime provides `ADMIN_API_URL`, `GATEWAY_TOKEN`, and `AGENT_ID`.

The person in the room can always browse every artifact of the room in the portal (the artifact card, or top-right **Workspace → Artifacts**). When they mean an artifact you did not save, ask them for its identifier, or use one that appears in the conversation, then read it directly.

## The save ledger

The save command in [publishing-contract.md](publishing-contract.md) appends one JSON line per successful save to `${ARTIFACT_LEDGER:-/workspace/state/artifact-ledger.jsonl}`:

```json
{"room_id": 1692, "identifier": "minu-alert-routing", "version": 3, "type": "markdown", "title": "Minu Alert Routing", "saved_at": "2026-10-17T02:11:09Z"}
```

`/workspace` persists across restarts. The ledger lists what *you* saved, which answers "내가 작성한 것" directly. Other agents and people can also save new versions under the same identifier, so for exact current state, verify with the live read below.

### Artifacts saved before the ledger existed (once)

Run this once if the ledger is missing or the user mentions an older artifact of yours. It scans your own session transcripts, including archived reset and deleted sessions, for earlier **save** commands (reads are ignored), confirms each candidate with a live read, and appends only artifacts that exist. The recorded version and time are the current live ones.

```bash
set -euo pipefail
: "${ADMIN_API_URL:?}" "${GATEWAY_TOKEN:?}" "${AGENT_ID:?}"
python3 - <<'PYTHON'
import glob, json, os, re, urllib.error, urllib.parse, urllib.request
ledger = os.environ.get("ARTIFACT_LEDGER", "/workspace/state/artifact-ledger.jsonl")
ident = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}"
known = set()
if os.path.exists(ledger):
    for line in open(ledger, encoding="utf-8"):
        if line.strip():
            row = json.loads(line); known.add((int(row["room_id"]), row["identifier"]))
candidates = set()
home = os.path.expanduser("~")
paths = []
for folder in ("sessions", "session-artifacts/reset", "session-artifacts/deleted"):
    paths += glob.glob(f"{home}/.openclaw/agents/*/{folder}/*.jsonl*")
for path in paths:
    for line in open(path, encoding="utf-8", errors="replace"):
        if "/artifacts" not in line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        for part in (event.get("message") or {}).get("content") or []:
            if not isinstance(part, dict) or part.get("type") != "toolCall":
                continue
            text = json.dumps(part.get("arguments"), ensure_ascii=False).replace('\\"', '"')
            # Only save calls: POST to the collection endpoint, never a read of /artifacts/<identifier>.
            if not re.search(r"/artifacts(?![/\w])", text) or not re.search(r"POST|--data|-d\b", text):
                continue
            rooms = set(re.findall(r"/internal/chat-rooms/(\d+)/artifacts", text)) | set(re.findall(r"\bROOM_ID=['\"]?(\d+)", text))
            names = set(re.findall(rf"\bARTIFACT_IDENTIFIER=['\"]?({ident})", text))
            names |= set(re.findall(rf"\"identifier\"\s*:\s*\"({ident})\"", text))
            candidates |= {(int(r), n) for r in rooms for n in names}
found = 0
os.makedirs(os.path.dirname(ledger), exist_ok=True)
with open(ledger, "a", encoding="utf-8") as out:
    for room, name in sorted(candidates - known):
        url = f"{os.environ['ADMIN_API_URL']}/internal/chat-rooms/{room}/artifacts/{urllib.parse.quote(name)}?from_agent_id={urllib.parse.quote(os.environ['AGENT_ID'])}"
        request = urllib.request.Request(url, headers={"X-Gateway-Token": os.environ["GATEWAY_TOKEN"]})
        try:
            artifact = json.load(urllib.request.urlopen(request, timeout=15))["artifact"]
        except urllib.error.HTTPError as error:
            if error.code in (403, 404):
                continue  # gone, wrong pairing, or a room you left
            raise
        out.write(json.dumps({"room_id": room, "identifier": artifact["identifier"], "version": artifact["version"],
                              "type": artifact["type"], "title": artifact["title"],
                              "saved_at": artifact["createdAt"], "source": "backfill"}, ensure_ascii=False) + "\n")
        found += 1
print(f"backfilled {found} artifact(s) into {ledger}")
PYTHON
```

## List artifacts by scope

One command covers all three scopes. Set `SCOPE` to `room` (needs `ROOM_ID`), `rooms` (every room you are still in), or `mine` (everything in your ledger, including rooms you left). With `VERIFY=1` each entry is re-read live, so title and version reflect saves made by others; entries in rooms you can no longer read are marked instead of failing.

```bash
set -euo pipefail
: "${ADMIN_API_URL:?}" "${GATEWAY_TOKEN:?}" "${AGENT_ID:?}" "${SCOPE:=room}"
if [ "$SCOPE" = room ]; then : "${ROOM_ID:?set ROOM_ID for SCOPE=room}"; fi
export SCOPE
python3 - <<'PYTHON'
import json, os, urllib.error, urllib.parse, urllib.request
api, agent, scope = os.environ["ADMIN_API_URL"], os.environ["AGENT_ID"], os.environ["SCOPE"]
headers = {"X-Gateway-Token": os.environ["GATEWAY_TOKEN"]}
def get(path):
    return json.load(urllib.request.urlopen(urllib.request.Request(api + path, headers=headers), timeout=15))
ledger = os.environ.get("ARTIFACT_LEDGER", "/workspace/state/artifact-ledger.jsonl")
latest = {}
if os.path.exists(ledger):
    for line in open(ledger, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            key = (int(row["room_id"]), row["identifier"])
            if key not in latest or row["version"] >= latest[key]["version"]:
                latest[key] = row
rooms = {}
if scope in ("rooms", "mine"):
    rooms = {int(r["id"]): r["name"] for r in get(f"/internal/agent-rooms?agent_slug={urllib.parse.quote(agent)}")["rooms"]}
if scope == "room":
    keep = lambda room: room == int(os.environ["ROOM_ID"])
elif scope == "rooms":
    keep = lambda room: room in rooms
elif scope == "mine":
    keep = lambda room: True
else:
    raise SystemExit("SCOPE must be room, rooms, or mine")
rows = [row for (room, _), row in latest.items() if keep(room)]
for row in rows:
    row["room_name"] = rooms.get(int(row["room_id"]))
    if os.environ.get("VERIFY") == "1":
        try:
            live = get(f"/internal/chat-rooms/{row['room_id']}/artifacts/{urllib.parse.quote(row['identifier'])}?from_agent_id={urllib.parse.quote(agent)}")["artifact"]
            row.update(version=live["version"], title=live["title"], type=live["type"], latest_at=live["createdAt"], status="ok")
        except urllib.error.HTTPError as error:
            row["status"] = {403: "no-longer-a-participant", 404: "not-found"}.get(error.code, f"http-{error.code}")
rows.sort(key=lambda r: (r.get("latest_at") or r["saved_at"]), reverse=True)
print(json.dumps({"scope": scope, "count": len(rows), "artifacts": rows}, ensure_ascii=False, indent=1))
PYTHON
```

Example output (`SCOPE=room VERIFY=1`):

```json
{"scope": "room", "count": 2, "artifacts": [
 {"room_id": 1692, "identifier": "minu-alert-routing", "version": 4, "type": "markdown", "title": "Minu Alert Routing", "saved_at": "2026-10-17T02:11:09Z", "room_name": null, "latest_at": "2026-10-17T03:40:12.511Z", "status": "ok"},
 {"room_id": 1692, "identifier": "elastic-space-plan", "version": 1, "type": "html", "title": "Elastic Space Plan", "saved_at": "2026-10-16T08:02:44Z", "room_name": null, "status": "ok"}]}
```

A `version` higher than your last save means someone else saved after you. An empty result means you have saved nothing there (or the ledger needs the one-time backfill); it does not mean the room has no artifacts.

## Read content and versions

Latest version (full record):

```bash
curl --fail-with-body --silent --show-error \
  "${ADMIN_API_URL}/internal/chat-rooms/${ROOM_ID}/artifacts/${ARTIFACT_IDENTIFIER}?from_agent_id=${AGENT_ID}" \
  --header "X-Gateway-Token: ${GATEWAY_TOKEN}"
```

```json
{"artifact": {"identifier": "minu-alert-routing", "version": 4, "type": "markdown", "title": "Minu Alert Routing",
  "content": "# Minu Alert Routing\n…", "preview": "Minu Alert Routing …", "createdAt": "2026-10-17T03:40:12.511Z"}}
```

Live HTML artifacts also carry `live: true` and `liveSchemaVersions`. Add `&version=N` for an exact older version. Errors: `404 {"error":"Artifact not found"}` (no such identifier or version in this room), `404 {"error":"Room not found"}`, `403` (you are not a participant), `400 {"error":"validation: version must be a positive integer"}`.

Version history: versions are consecutive integers from 1 to the latest, and each one is immutable. Saving the same type, title, and content as the latest creates no new version. To list history or compare, read the latest, then each older version you need:

```bash
set -euo pipefail
: "${ADMIN_API_URL:?}" "${GATEWAY_TOKEN:?}" "${AGENT_ID:?}" "${ROOM_ID:?}" "${ARTIFACT_IDENTIFIER:?}"
python3 - <<'PYTHON'
import json, os, urllib.parse, urllib.request
base = (f"{os.environ['ADMIN_API_URL']}/internal/chat-rooms/{os.environ['ROOM_ID']}/artifacts/"
        f"{urllib.parse.quote(os.environ['ARTIFACT_IDENTIFIER'])}?from_agent_id={urllib.parse.quote(os.environ['AGENT_ID'])}")
headers = {"X-Gateway-Token": os.environ["GATEWAY_TOKEN"]}
read = lambda suffix="": json.load(urllib.request.urlopen(urllib.request.Request(base + suffix, headers=headers), timeout=15))["artifact"]
latest = read()
history = [read(f"&version={n}") for n in range(1, latest["version"])] + [latest]
print(json.dumps([{k: a[k] for k in ("version", "title", "type", "createdAt")} | {"chars": len(a["content"])} for a in history],
                 ensure_ascii=False, indent=1))
PYTHON
```

For a long history, read only the versions you need, for example the latest and the one before it, to describe the most recent change.

## Revise an existing artifact

1. Read the latest version (command above). Keep its `version` as `EXPECTED_VERSION` and write its `content` to a workspace file.
2. Edit that file. Keep the same `identifier`; change `title` only if the user asked to rename it.
3. Save with the standard command in [publishing-contract.md](publishing-contract.md), exporting `EXPECTED_VERSION` (sent as `expectedVersion`). The `201` response returns the new version (or the same version when nothing changed); the ledger line is written automatically.
4. On `409 {"error":"Artifact version conflict","latestVersion":N}` (printed by the save command), someone saved first: read version `N`, apply your change on top of it, and save again with `EXPECTED_VERSION=N`.
5. Send the room message with `artifact_refs: [{identifier, version}]` from the save response, then end with `NO_REPLY`.

To restore an older version, read it with `&version=N`, save its `content` as the next version with `EXPECTED_VERSION` set to the current latest, and publish that new version. History is never rewritten.
