"""open-design Harness tests.

Every test runs the CLI as a subprocess against an in-process fake OpenDesign
daemon (plain HTTP on loopback), so the suite never touches a real server.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "open_design.py"
spec = importlib.util.spec_from_file_location("open_design", CLI)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

GOOD_TOKEN = "test-token-abc"
LONG_TEXT = "K" * 5000


class FakeDaemon(BaseHTTPRequestHandler):
    enforce_auth = True
    slow = False
    projects: dict[str, dict] = {}
    files: dict[str, dict[str, bytes]] = {}

    def log_message(self, *args):  # silence
        pass

    def _authorized(self) -> bool:
        if not self.enforce_auth:
            return True
        return self.headers.get("Authorization") == f"Bearer {GOOD_TOKEN}"

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def _raw(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    mapped_proxy = False
    def _strip_prefix(self):
        if self.path.startswith("/agent-api/"):
            stripped = self.path[len("/agent-api"):]
            # mapped proxy: /agent-api/<x> is the daemon's /api/<x>; root proxy keeps /api
            self.path = ("/api" + stripped) if self.mapped_proxy else stripped

    def do_GET(self):  # noqa: N802
        self._strip_prefix()
        if self.slow:
            time.sleep(3)
        if self.path == "/api/version":
            return self._json(200, {"version": {"version": "0.20.3", "capabilities": {"slideRenderer": False}}})
        if "/preview/" in self.path:  # scoped preview URLs open without the API token, like the real daemon
            return self._raw(200, b"<html>preview</html>", "text/html")
        if not self._authorized():
            return self._json(401, {"error": {"message": "unauthorized"}})
        if self.path == "/api/projects":
            return self._json(200, {"projects": list(self.projects.values())})
        parts = self.path.split("?")[0].strip("/").split("/")
        if len(parts) == 3 and parts[1] == "projects":
            pid = parts[2]
            if pid not in self.projects:
                return self._json(404, {"error": {"message": "project not found"}})
            return self._json(200, {"project": self.projects[pid]})
        if len(parts) == 4 and parts[3] == "files":
            return self._json(200, {"files": [
                {"name": n, "size": len(c), "kind": "html", "artifactManifest": {"exports": ["html", "pdf", "zip"]},
                 "description": LONG_TEXT} for n, c in self.files.get(parts[2], {}).items()]})
        if len(parts) == 5 and parts[3] == "files":
            content = self.files.get(parts[2], {}).get(parts[4])
            if content is None:
                return self._json(404, {"error": {"message": "file not found"}})
            return self._raw(200, content, "text/html")
        if len(parts) == 4 and parts[3].startswith("preview-url"):
            from urllib.parse import parse_qs, urlparse
            name = parse_qs(urlparse(self.path).query).get("file", [""])[0]
            if name not in self.files.get(parts[2], {}):
                return self._json(404, {"error": {"message": "ENOENT index.html"}})
            return self._json(200, {"url": f"/api/projects/{parts[2]}/preview/scope123/{name}", "csp": "sandbox allow-scripts"})
        if len(parts) == 6 and parts[3] == "preview":
            return self._raw(200, b"<html>preview</html>", "text/html")
        if len(parts) == 4 and parts[3] == "archive":
            return self._raw(200, b"PK\x03\x04fakezip", "application/zip")
        if len(parts) == 5 and parts[3] == "export" and parts[4] == "manifest":
            return self._json(200, {"schema": "open-design.project-export-manifest.v1", "projectId": parts[2]})
        return self._json(404, {"error": {"message": "no route"}})

    def do_POST(self):  # noqa: N802
        self._strip_prefix()
        if not self._authorized():
            return self._json(401, {"error": {"message": "unauthorized"}})
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        parts = self.path.strip("/").split("/")
        if self.path == "/api/projects":
            data = json.loads(body)
            if not data.get("id"):
                return self._json(400, {"error": {"code": "BAD_REQUEST", "message": "invalid project id"}})
            project = {"id": data["id"], "name": data["name"], "metadata": data.get("metadata", {}), "createdAt": 1, "updatedAt": 1}
            self.projects[data["id"]] = project
            self.files[data["id"]] = {}
            return self._json(200, {"project": project})
        if len(parts) == 4 and parts[3] == "upload":
            import re as _re
            match = _re.search(rb'filename="([^"]+)"\r\nContent-Type: [^\r]+\r\n\r\n(.*)\r\n--', body, _re.S)
            name, content = match.group(1).decode(), match.group(2)
            store = self.files.setdefault(parts[2], {})
            store[name] = content if not name.startswith("corrupt") else content + b"XX"
            return self._json(200, {"files": [{"name": name, "size": len(content)}]})
        if len(parts) == 5 and parts[3] == "export" and parts[4] == "html":
            name = json.loads(body).get("fileName")
            content = self.files.get(parts[2], {}).get(name)
            if content is None:
                return self._json(404, {"error": {"message": "not found"}})
            return self._raw(200, content, "text/html")
        if self.path == "/api/import/claude-design":
            return self._json(200, {"project": {"id": "imported-1", "name": "Imported", "metadata": {"kind": "deck"}}})
        return self._json(404, {"error": {"message": "no route"}})

    def do_DELETE(self):  # noqa: N802
        self._strip_prefix()
        if not self._authorized():
            return self._json(401, {"error": {"message": "unauthorized"}})
        pid = self.path.strip("/").split("/")[2]
        self.projects.pop(pid, None)
        return self._json(200, {"ok": True})


class HarnessCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeDaemon)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeDaemon.enforce_auth = True
        FakeDaemon.mapped_proxy = False
        FakeDaemon.slow = False
        FakeDaemon.projects = {}
        FakeDaemon.files = {}
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state"
        self.run_cli("config.set", "--state-root", str(self.state), "--base-url", self.base)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, token: str | None = GOOD_TOKEN, expect: int = 0):
        env = {**os.environ}
        env.pop(module.TOKEN_ENV, None)
        if token is not None:
            env[module.TOKEN_ENV] = token
        completed = subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True, env=env)
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, expect, payload)
        return payload

    def create_project(self, name="Smoke Deck"):
        out = self.run_cli("projects.create", "--state-root", str(self.state), "--name", name)
        return out["data"]["project"]["id"]

    def write_local(self, name, content: bytes):
        path = Path(self.tmp.name) / name
        path.write_bytes(content)
        return str(path)


class ContractTests(HarnessCase):
    def test_status_and_manifest_agree(self):
        out = self.run_cli("status", token=None)
        self.assertEqual(out["data"]["version"], module.VERSION)
        manifest = json.loads((ROOT / "harness.json").read_text())
        self.assertEqual(manifest["version"], module.VERSION)
        self.assertEqual(set(manifest["commands"]), set(module.COMMANDS))
        for name, command in manifest["commands"].items():
            self.assertEqual(command["baseArgv"], [name])
        self.assertEqual(manifest["commands"]["projects.delete"]["safetyClasses"], ["destructive", "externalSideEffect"])

    def test_config_is_owner_only_and_never_holds_the_token(self):
        info = os.stat(self.state / "config.json")
        self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.state).st_mode), 0o700)
        self.assertNotIn(GOOD_TOKEN, (self.state / "config.json").read_text())
        out = self.run_cli("config.status", "--state-root", str(self.state))
        self.assertEqual(out["data"]["config"]["baseUrl"], self.base)
        self.assertTrue(out["data"]["tokenPresent"])

    def test_mapped_proxy_layout_is_autodetected_and_works_end_to_end(self):
        # nginx maps /agent-api/* directly onto the daemon's /api/* (the od.wondermove.local layout)
        FakeDaemon.mapped_proxy = True
        out = self.run_cli("config.set", "--state-root", str(self.state), "--base-url", self.base + "/agent-api", "--web-base-url", self.base)
        self.assertEqual(out["data"]["config"]["apiStyle"], "mapped")
        self.assertTrue(any("auto-detected" in w for w in out["data"]["warnings"]))
        out = self.run_cli("health", "--state-root", str(self.state))
        self.assertEqual(out["data"]["apiStyle"], "mapped")
        self.assertEqual(out["data"]["serverVersion"], "0.20.3")
        pid = self.create_project()
        local = self.write_local("deck.html", b"<html>x</html>")
        self.run_cli("files.put", "--state-root", str(self.state), "--project-id", pid, "--path", local)
        link = self.run_cli("preview.link", "--state-root", str(self.state), "--project-id", pid, "--file", "deck.html")
        self.assertTrue(link["data"]["url"].startswith(self.base + "/api/projects/"))
        self.assertTrue(link["data"]["apiUrl"].startswith(self.base + "/agent-api/api/"))
        self.assertTrue(link["data"]["opensWithoutToken"])
        paths = [r["path"] for r in link["data"]["evidence"]["requests"]]
        self.assertTrue(any(p.startswith("/projects/") for p in paths), paths)   # /api collapsed: sent as <base>/projects/... not <base>/api/projects/...

    def test_api_style_explicit_override_skips_probe(self):
        out = self.run_cli("config.set", "--state-root", str(self.state), "--base-url", self.base + "/agent-api", "--api-style", "mapped")
        self.assertEqual(out["data"]["config"]["apiStyle"], "mapped")
        out = self.run_cli("config.set", "--state-root", str(self.state), "--base-url", self.base, "--api-style", "sideways", expect=module.EXIT["invalid"])
        self.assertEqual(out["error"]["code"], "INVALID_API_STYLE")

    def test_agent_api_prefix_and_separate_web_url(self):
        out = self.run_cli("config.set", "--state-root", str(self.state), "--base-url", self.base + "/agent-api/", "--web-base-url", self.base)
        self.assertEqual(out["data"]["config"]["baseUrl"], self.base + "/agent-api")
        self.assertEqual(out["data"]["config"]["webBaseUrl"], self.base)
        out = self.run_cli("health", "--state-root", str(self.state))
        self.assertEqual(out["data"]["serverVersion"], "0.20.3")
        pid = self.create_project()
        local = self.write_local("deck.html", b"<html>x</html>")
        self.run_cli("files.put", "--state-root", str(self.state), "--project-id", pid, "--path", local)
        link = self.run_cli("preview.link", "--state-root", str(self.state), "--project-id", pid, "--file", "deck.html")
        self.assertTrue(link["data"]["url"].startswith(self.base + "/api/projects/"))       # human URL: web origin, no prefix
        self.assertTrue(link["data"]["apiUrl"].startswith(self.base + "/agent-api/api/"))   # agent URL keeps the prefix
        self.assertTrue(link["data"]["opensWithoutToken"])

    def test_web_base_url_defaults_to_origin_of_prefixed_base(self):
        out = self.run_cli("config.set", "--state-root", str(self.state), "--base-url", self.base + "/agent-api")
        self.assertEqual(out["data"]["config"]["webBaseUrl"], self.base)
        out = self.run_cli("config.set", "--state-root", str(self.state), "--base-url", self.base + "/agent-api", "--web-base-url", self.base + "/web", expect=module.EXIT["invalid"])
        self.assertEqual(out["error"]["code"], "INVALID_BASE_URL")

    def test_base_url_and_state_validation_fail_closed(self):
        out = self.run_cli("config.set", "--state-root", str(self.state), "--base-url", "https://u:p@host/x?q=1", expect=module.EXIT["invalid"])
        self.run_cli("config.set", "--state-root", str(self.state), "--base-url", "https://host/a//b", expect=module.EXIT["invalid"])
        self.assertEqual(out["error"]["code"], "INVALID_BASE_URL")
        self.state.chmod(0o755)
        out = self.run_cli("projects.list", "--state-root", str(self.state), expect=module.EXIT["precondition"])
        self.assertEqual(out["error"]["code"], "UNSAFE_STATE")
        self.state.chmod(0o700)
        out = self.run_cli("projects.list", "--state-root", str(Path(self.tmp.name) / "missing" / "x"), expect=module.EXIT["precondition"])

    def test_secret_never_in_argv_or_output(self):
        out = self.run_cli("projects.list", "--state-root", str(self.state), "--name", GOOD_TOKEN, expect=module.EXIT["invalid"])
        self.assertEqual(out["error"]["code"], "SECRET_IN_ARGV")
        pid = self.create_project()
        listing = self.run_cli("projects.list", "--state-root", str(self.state))
        self.assertNotIn(GOOD_TOKEN, json.dumps(listing))
        self.assertTrue(listing["data"]["evidence"]["tokenSentFromEnv"])

    def test_auth_rejection_maps_to_exit_4(self):
        out = self.run_cli("projects.list", "--state-root", str(self.state), token="wrong", expect=module.EXIT["auth"])
        self.assertEqual(out["error"]["code"], "AUTH_REJECTED")

    def test_health_reports_enforcement_both_ways(self):
        out = self.run_cli("health", "--state-root", str(self.state))
        self.assertTrue(out["data"]["authEnforced"])
        self.assertEqual(out["data"]["serverVersion"], "0.20.3")
        self.assertEqual(out["data"]["findings"], [])
        FakeDaemon.enforce_auth = False
        out = self.run_cli("health", "--state-root", str(self.state))
        self.assertFalse(out["data"]["authEnforced"])
        self.assertIn("AUTH_NOT_ENFORCED", [f["code"] for f in out["data"]["findings"]])
        out = self.run_cli("health", "--state-root", str(self.state), token=None)
        self.assertIn("TOKEN_ABSENT", [f["code"] for f in out["data"]["findings"]])

    def test_timeout_maps_to_exit_7(self):
        FakeDaemon.slow = True
        out = self.run_cli("health", "--state-root", str(self.state), "--timeout-ms", "300", expect=module.EXIT["timeout"])
        self.assertEqual(out["error"]["code"], "TIMEOUT")


class LifecycleTests(HarnessCase):
    def test_create_upload_roundtrip_preview_export_delete(self):
        pid = self.create_project("한국어 덱 이름")
        local = self.write_local("deck.html", ("<html>" + LONG_TEXT + "</html>").encode())
        out = self.run_cli("files.put", "--state-root", str(self.state), "--project-id", pid, "--path", local)
        self.assertTrue(out["data"]["roundTripVerified"])
        self.assertEqual(out["effects"], [f"uploaded deck.html (5013 bytes) to project {pid}"])

        listing = self.run_cli("files.list", "--state-root", str(self.state), "--project-id", pid)
        self.assertEqual(listing["data"]["files"][0]["exports"], ["html", "pdf", "zip"])

        got = self.run_cli("files.get", "--state-root", str(self.state), "--project-id", pid, "--name", "deck.html")
        self.assertEqual(got["data"]["content"], "<html>" + LONG_TEXT + "</html>")
        self.assertEqual(len(got["data"]["content"]), 5013)  # long data is never truncated

        link = self.run_cli("preview.link", "--state-root", str(self.state), "--project-id", pid, "--file", "deck.html")
        self.assertTrue(link["data"]["url"].startswith(self.base + "/api/projects/"))
        self.assertTrue(link["data"]["opensWithoutToken"])

        exported = Path(self.tmp.name) / "out.html"
        out = self.run_cli("export.html", "--state-root", str(self.state), "--project-id", pid, "--file-name", "deck.html", "--out-path", str(exported))
        self.assertEqual(exported.read_bytes(), ("<html>" + LONG_TEXT + "</html>").encode())

        archive = Path(self.tmp.name) / "out.zip"
        self.run_cli("export.archive", "--state-root", str(self.state), "--project-id", pid, "--out-path", str(archive))
        self.assertTrue(archive.read_bytes().startswith(b"PK"))

        manifest = self.run_cli("export.manifest", "--state-root", str(self.state), "--project-id", pid)
        self.assertEqual(manifest["data"]["manifest"]["schema"], "open-design.project-export-manifest.v1")

        out = self.run_cli("projects.delete", "--state-root", str(self.state), "--project-id", pid, expect=module.EXIT["precondition"])
        self.assertEqual(out["error"]["code"], "APPROVAL_REQUIRED")
        out = self.run_cli("projects.delete", "--state-root", str(self.state), "--project-id", pid, "--exact-name", "wrong", "--approve", expect=module.EXIT["precondition"])
        self.assertEqual(out["error"]["code"], "NAME_MISMATCH")
        out = self.run_cli("projects.delete", "--state-root", str(self.state), "--project-id", pid, "--exact-name", "한국어 덱 이름", "--approve")
        self.assertTrue(out["data"]["deleted"])

    def test_upload_verifies_byte_identical_readback(self):
        pid = self.create_project()
        local = self.write_local("corrupt.html", b"<html>x</html>")
        out = self.run_cli("files.put", "--state-root", str(self.state), "--project-id", pid, "--path", local, expect=module.EXIT["failed"])
        self.assertEqual(out["error"]["code"], "VERIFY_FAILED")

    def test_filename_and_path_validation(self):
        pid = self.create_project()
        out = self.run_cli("files.get", "--state-root", str(self.state), "--project-id", pid, "--name", "../etc/passwd", expect=module.EXIT["invalid"])
        self.assertEqual(out["error"]["code"], "INVALID_FILENAME")
        out = self.run_cli("files.put", "--state-root", str(self.state), "--project-id", pid, "--path", "relative.html", expect=module.EXIT["invalid"])
        self.assertEqual(out["error"]["code"], "INVALID_PATH")
        out = self.run_cli("import.claude-design", "--state-root", str(self.state), "--path", self.write_local("not-zip.zip", b"nope"), expect=module.EXIT["invalid"])
        self.assertEqual(out["error"]["code"], "INVALID_PATH")

    def test_import_claude_design_zip(self):
        local = self.write_local("Deck Export.zip", b"PK\x03\x04zipdata")
        out = self.run_cli("import.claude-design", "--state-root", str(self.state), "--path", local)
        self.assertEqual(out["data"]["project"]["id"], "imported-1")
        self.assertEqual(out["effects"], ["imported Deck Export.zip as an OpenDesign project"])

    def test_missing_project_maps_to_precondition(self):
        out = self.run_cli("projects.get", "--state-root", str(self.state), "--project-id", "0" * 32, expect=module.EXIT["precondition"])
        self.assertEqual(out["error"]["code"], "PROVIDER_ERROR")
        self.assertEqual(out["error"]["details"]["status"], 404)


if __name__ == "__main__":
    unittest.main()
