"""Contract-pinning tests for the artifact-design Skill.

The Skill encodes facts verified against the ClawPod admin-api and portal
source (artifact field limits, the save-then-artifact_refs flow, the sandboxed
iframe renderer). These tests keep those facts from silently drifting out of
the package.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "artifact-design"
REFERENCES = SKILL_DIR / "references"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class ArtifactDesignSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = read(SKILL_DIR / "SKILL.md")
        cls.contract = read(REFERENCES / "publishing-contract.md")
        cls.skeleton = read(REFERENCES / "html-skeleton.md")
        cls.choosing = read(REFERENCES / "choosing-the-type.md")
        cls.checklist = read(REFERENCES / "checklist.md")
        cls.everything = "\n".join(read(p) for p in sorted(SKILL_DIR.rglob("*.md")))

    def test_package_is_skill_only_and_write_safe(self) -> None:
        metadata = json.loads(read(SKILL_DIR / "capability.json"))
        self.assertNotIn("linkedHarness", metadata)
        self.assertFalse((ROOT / "harnesses" / "artifact-design").exists())
        self.assertEqual(metadata["safety"], {"risk": "write-safe", "approvalRequired": False})
        self.assertEqual(metadata["descriptionSource"], "skill-frontmatter")

    def test_every_referenced_support_file_exists(self) -> None:
        for match in re.finditer(r"\]\((references/[^)]+)\)", self.skill):
            self.assertTrue((SKILL_DIR / match.group(1)).is_file(), match.group(1))
        for name in ("publishing-contract", "design-fundamentals", "html-skeleton", "choosing-the-type", "markdown-craft", "checklist", "examples"):
            self.assertIn(f"references/{name}.md", self.skill, name)

    def test_publishing_contract_pins_verified_api_facts(self) -> None:
        for fact in (
            "POST /internal/chat-rooms/:roomId/artifacts",
            "/internal/messages",
            "X-Gateway-Token",
            "from_agent_id",
            "artifact_refs",
            "^[A-Za-z0-9][A-Za-z0-9_.-]*$",
            "1–120",
            "1–200 chars",
            "200,000",
            "`markdown` or `html`",
            "Max **5**",
            "cannot both be set",
            "expectedVersion",
            "409",
            "latestVersion",
            "404",
            "403",
            "240 chars",
            "Content-addressed no-op",
            "NO_REPLY",
        ):
            self.assertIn(fact, self.contract, fact)

    def test_pointer_flow_is_the_standard_and_inline_is_legacy(self) -> None:
        self.assertIn("supersedes", self.contract)
        self.assertIn("Legacy mode: inline `artifacts`", self.contract)
        self.assertIn("artifact_refs", self.skill)
        self.assertIn("Never send `artifacts` and `artifact_refs` in the same message", self.skill)

    def test_html_guidance_matches_the_sandboxed_iframe_renderer(self) -> None:
        for fact in ('sandbox=""', "No JavaScript runs", "prefers-color-scheme", "70 vh", "cdn.jsdelivr.net", "Google Fonts is blocked", "end of `<body>`"):
            self.assertIn(fact, self.skeleton, fact)
        self.assertNotIn("<script>", self.skeleton.split("## Skeleton")[1].split("```")[1])
        self.assertNotIn("fonts.googleapis.com", self.everything)
        self.assertNotIn("localStorage works", self.everything)
        self.assertIn("Does not run", self.choosing)

    def test_markers_and_paths_are_named_as_plain_text_traps(self) -> None:
        for trap in ("[embed ref=...]", "/workspace/...", "plain text"):
            self.assertIn(trap, self.contract, trap)
        self.assertIn("never become artifacts", self.skill)

    def test_checklist_covers_theme_preview_and_payload_gates(self) -> None:
        for gate in ("no `<script>`", "prefers-color-scheme: dark", "end of `<body>`", "artifact_refs", "NO_REPLY", "expectedVersion", "1–120", "1–200"):
            self.assertIn(gate, self.checklist, gate)

    def test_description_routes_away_from_adjacent_capabilities(self) -> None:
        description = next(line for line in self.skill.splitlines() if line.startswith("description:"))
        for capability in ("Claude Design", "Image Studio", "Video Studio"):
            self.assertIn(capability, description)
        self.assertIn("artifact_refs", description)


class FakeAdminApi(BaseHTTPRequestHandler):
    """The agent-facing artifact endpoints, as implemented in admin-api routes/internal.ts."""

    token = "test-gateway-token"
    rooms = {1692: "George", 1689: "George, Soeun"}
    store: dict = {}

    def log_message(self, *args):
        pass

    def reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        if self.headers.get("X-Gateway-Token") != self.token:
            self.reply(401, {"error": "Unauthorized"})
            return False
        return True

    def do_GET(self):
        if not self.authorized():
            return
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/internal/agent-rooms":
            rooms = [{"id": str(k), "name": v, "room_type": "direct"} for k, v in self.rooms.items()]
            return self.reply(200, {"rooms": rooms, "count": len(rooms)})
        match = re.fullmatch(r"/internal/chat-rooms/(\d+)/artifacts/([^/]+)", url.path)
        if not match:
            return self.reply(401, {"error": "No authorization token provided"})
        room, identifier = int(match.group(1)), match.group(2)
        if room not in self.rooms:
            return self.reply(403, {"error": "Agent is not a participant in this room"})
        versions = self.store.get((room, identifier), [])
        version = int(query["version"][0]) if "version" in query else len(versions)
        if version < 1 or version > len(versions):
            return self.reply(404, {"error": "Artifact not found"})
        return self.reply(200, {"artifact": versions[version - 1]})

    def do_POST(self):
        if not self.authorized():
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        match = re.fullmatch(r"/internal/chat-rooms/(\d+)/artifacts", self.path)
        if match:
            versions = self.store.setdefault((int(match.group(1)), body["identifier"]), [])
            expected = body.get("expectedVersion")
            if expected and expected != len(versions):
                return self.reply(409, {"error": "Artifact version conflict", "latestVersion": len(versions)})
            record = {"identifier": body["identifier"], "type": body["type"], "title": body["title"],
                      "content": body["content"], "preview": body["content"][:240],
                      "version": len(versions) + 1, "createdAt": f"2026-10-17T00:00:0{len(versions)}.000Z"}
            versions.append(record)
            return self.reply(201, {"artifact": {k: v for k, v in record.items() if k != "content"}})
        if self.path == "/internal/messages":
            return self.reply(201, {"message_id": "m1", "room_id": body["room_id"]})
        self.reply(404, {"error": "not found"})


def bash_blocks(text: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)```", text, re.S)


class ArtifactFindAndReviseTests(unittest.TestCase):
    """Runs the documented commands against a local fake of the agent endpoints."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.guide = read(REFERENCES / "finding-and-revising.md")
        cls.contract = read(REFERENCES / "publishing-contract.md")
        FakeAdminApi.store = {}
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeAdminApi)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        FakeAdminApi.store = {}
        self.env = {**os.environ, "HOME": str(self.home), "ADMIN_API_URL": f"http://127.0.0.1:{self.server.server_port}",
                    "GATEWAY_TOKEN": FakeAdminApi.token, "AGENT_ID": "george-lyhelb",
                    "ARTIFACT_LEDGER": str(self.home / "state" / "artifact-ledger.jsonl")}

    def run_block(self, script: str, **env) -> str:
        run = subprocess.run(["bash", "-c", script], env={**self.env, **env}, capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        return run.stdout

    def save(self, room, identifier, title, content, expected=None):
        source = self.home / f"{identifier}.md"
        source.write_text(content, encoding="utf-8")
        env = {"ROOM_ID": str(room), "ARTIFACT_FILE": str(source), "ARTIFACT_IDENTIFIER": identifier,
               "ARTIFACT_TITLE": title, "ARTIFACT_TYPE": "markdown", "MESSAGE_CONTENT": "ok"}
        if expected:
            env["EXPECTED_VERSION"] = str(expected)
        return self.run_block(bash_blocks(self.contract)[0], **env)

    def listing(self, **env):
        return json.loads(self.run_block(next(b for b in bash_blocks(self.guide) if "SCOPE" in b), **env))

    def test_guide_documents_paths_scopes_and_unsupported_filters(self) -> None:
        for fact in ("/internal/agent-rooms?agent_slug=$AGENT_ID", "&version=N", "artifact-ledger.jsonl",
                     "SCOPE", "room", "rooms", "mine", "not available to agents", "Filter by author",
                     "not supported", "Artifact version conflict", "latestVersion", "expectedVersion", "Version history"):
            self.assertIn(fact, self.guide, fact)
        self.assertIn("references/finding-and-revising.md", read(SKILL_DIR / "SKILL.md"))

    def test_save_records_ledger_and_listing_covers_each_scope(self) -> None:
        self.save(1692, "minu-alert-routing", "Minu Alert Routing", "# v1")
        self.save(1692, "minu-alert-routing", "Minu Alert Routing", "# v2", expected=1)
        self.save(1689, "elastic-space-plan", "Elastic Space Plan", "# plan")
        self.save(1777, "old-room-note", "Old Room Note", "# old")  # room later left
        FakeAdminApi.rooms = {1692: "George", 1689: "George, Soeun"}
        room = self.listing(SCOPE="room", ROOM_ID="1692")
        self.assertEqual([(a["identifier"], a["version"]) for a in room["artifacts"]], [("minu-alert-routing", 2)])
        rooms = self.listing(SCOPE="rooms")
        self.assertEqual({a["identifier"] for a in rooms["artifacts"]}, {"minu-alert-routing", "elastic-space-plan"})
        mine = self.listing(SCOPE="mine", VERIFY="1")
        status = {a["identifier"]: a["status"] for a in mine["artifacts"]}
        self.assertEqual(status, {"minu-alert-routing": "ok", "elastic-space-plan": "ok", "old-room-note": "no-longer-a-participant"})
        # Someone else saves a newer version: VERIFY reflects it.
        FakeAdminApi.store[(1692, "minu-alert-routing")].append({**FakeAdminApi.store[(1692, "minu-alert-routing")][-1], "version": 3, "title": "Renamed"})
        verified = self.listing(SCOPE="room", ROOM_ID="1692", VERIFY="1")["artifacts"][0]
        self.assertEqual((verified["version"], verified["title"]), (3, "Renamed"))

    def test_version_history_and_revision_conflict(self) -> None:
        self.save(1692, "minu-alert-routing", "Minu Alert Routing", "# v1")
        self.save(1692, "minu-alert-routing", "Minu Alert Routing", "# v2 longer", expected=1)
        history_block = next(b for b in bash_blocks(self.guide) if "history = " in b)
        history = json.loads(self.run_block(history_block, ROOM_ID="1692", ARTIFACT_IDENTIFIER="minu-alert-routing"))
        self.assertEqual([(h["version"], h["chars"]) for h in history], [(1, 4), (2, 11)])
        source = self.home / "stale.md"
        source.write_text("# stale", encoding="utf-8")
        run = subprocess.run(["bash", "-c", bash_blocks(self.contract)[0]], capture_output=True, text=True, timeout=60,
                             env={**self.env, "ROOM_ID": "1692", "ARTIFACT_FILE": str(source), "ARTIFACT_IDENTIFIER": "minu-alert-routing",
                                  "ARTIFACT_TITLE": "x", "ARTIFACT_TYPE": "markdown", "MESSAGE_CONTENT": "x", "EXPECTED_VERSION": "1"})
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("latestVersion", run.stdout + run.stderr)

    def test_backfill_recovers_pre_ledger_artifacts_from_transcripts(self) -> None:
        FakeAdminApi.rooms = {1692: "George", 1689: "George, Soeun"}
        self.save(1692, "minu-alert-routing", "Minu Alert Routing", "# v1")
        self.save(1689, "elastic-space-plan", "Elastic Space Plan", "# plan")
        self.save(1692, "someone-elses", "Someone Else's", "# theirs")  # exists, but this agent only read it
        shutil.rmtree(Path(self.env["ARTIFACT_LEDGER"]).parent)  # a pod that never saved since the ledger existed
        agent = self.home / ".openclaw" / "agents" / "main"

        def transcript(path, commands):
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as out:
                for command in commands:
                    call = {"type": "toolCall", "name": "exec", "arguments": {"command": command}}
                    out.write(json.dumps({"type": "message", "message": {"role": "assistant", "content": [call]}}) + "\n")

        # The older save sits in an archived (reset) session.
        transcript(agent / "session-artifacts" / "reset" / "old.jsonl.reset.1792000000000", [
            'export ROOM_ID=1692 ARTIFACT_IDENTIFIER=minu-alert-routing; curl -X POST "$ADMIN_API_URL/internal/chat-rooms/${ROOM_ID}/artifacts"',
        ])
        transcript(agent / "sessions" / "s.jsonl", [
            'curl "$ADMIN_API_URL/internal/chat-rooms/1689/artifacts" -d \'{"identifier": "elastic-space-plan"}\'',
            'curl "$ADMIN_API_URL/internal/chat-rooms/1692/artifacts/someone-elses?from_agent_id=$AGENT_ID"',
            'curl "$ADMIN_API_URL/internal/chat-rooms/1692/artifacts/deleted-one"',
        ])
        backfill = next(b for b in bash_blocks(self.guide) if "backfill" in b)
        self.assertIn("backfilled 2 artifact(s)", self.run_block(backfill))
        self.assertIn("backfilled 0 artifact(s)", self.run_block(backfill))  # idempotent
        mine = self.listing(SCOPE="mine")
        self.assertEqual({a["identifier"] for a in mine["artifacts"]}, {"minu-alert-routing", "elastic-space-plan"})

    def test_room_scope_requires_room_id(self) -> None:
        block = next(b for b in bash_blocks(self.guide) if "SCOPE" in b)
        run = subprocess.run(["bash", "-c", block], env={**self.env, "SCOPE": "room"}, capture_output=True, text=True, timeout=60)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("set ROOM_ID", run.stderr)

if __name__ == "__main__":
    unittest.main()
