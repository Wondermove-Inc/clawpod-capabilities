#!/usr/bin/env python3
"""open-design Harness.

Typed client for a self-hosted OpenDesign daemon: onboarding-time configuration
(Base URL + TLS trust), health/auth verification, project and file lifecycle,
scoped preview links, and HTML/ZIP export. The API token travels ONLY through
the OPEN_DESIGN_API_TOKEN environment variable injected per run by the Gateway
secret lane — never through argv, state, or output.

Verified against OpenDesign v0.20.3 (2026-08-31); see docs/open-design-contract.md.
Response data is never truncated; only diagnostic messages are bounded.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import mimetypes
import os
import re
import ssl
import stat
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
SCHEMA_VERSION = 1
VERIFIED_SERVER_SERIES = "0.20"
TOKEN_ENV = "OPEN_DESIGN_API_TOKEN"
MAX_DIAGNOSTIC = 512
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
DEFAULT_TIMEOUT_MS = 20_000
MAX_TIMEOUT_MS = 120_000
EXIT = {"ok": 0, "invalid": 2, "unavailable": 3, "auth": 4, "precondition": 5, "failed": 6, "timeout": 7}
FILENAME_RE = re.compile(r"^[^/\\]{1,255}$")
PROJECT_KINDS = {"deck", "prototype", "document", "dashboard", "image", "other"}


class Fail(Exception):
    def __init__(self, code: str, message: str, kind: str = "invalid", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message[:MAX_DIAGNOSTIC]
        self.kind = kind
        self.details = details or {}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def state_root(value: str, create: bool = False) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise Fail("INVALID_STATE_ROOT", "stateRoot must be an absolute path")
    if create:
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
    try:
        info = os.lstat(path)
    except OSError:
        raise Fail("STATE_UNAVAILABLE", "stateRoot is unavailable", "precondition")
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise Fail("UNSAFE_STATE", "stateRoot must be an owner-only (0700) directory", "precondition")
    return path


def load_config(root: Path) -> dict[str, Any]:
    path = root / "config.json"
    try:
        info = os.lstat(path)
    except OSError:
        raise Fail("NOT_ONBOARDED", "no OpenDesign configuration; run config.set with the Base URL first", "precondition")
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
        raise Fail("UNSAFE_STATE", "config.json must be a regular 0600 file", "precondition")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Fail("MALFORMED_STATE", "config.json is unreadable; re-run config.set", "precondition")
    if not isinstance(config, dict) or config.get("schemaVersion") != SCHEMA_VERSION or not isinstance(config.get("baseUrl"), str):
        raise Fail("MALFORMED_STATE", "config.json has an unexpected shape; re-run config.set", "precondition")
    for key, value in config.items():
        if isinstance(value, str) and re.search(r"(?i)bearer\s|odagt_|token|secret|password", key + "=" + value) and key not in {"baseUrl", "caCertPath", "verifiedServerVersion", "updatedAt"}:
            raise Fail("UNSAFE_STATE", "config.json contains secret-like content; secrets belong only in the Gateway secret lane", "precondition")
    return config


def validate_base_url(value: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(value.strip().rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in ("", "/") or parsed.query or parsed.fragment or "@" in parsed.netloc:
        raise Fail("INVALID_BASE_URL", "baseUrl must be http(s)://host[:port] with no path, query, or credentials")
    return f"{parsed.scheme}://{parsed.netloc}"


class Client:
    def __init__(self, args: argparse.Namespace, config: dict[str, Any]):
        self.base = config["baseUrl"]
        self.timeout = min(int(args.timeout_ms or DEFAULT_TIMEOUT_MS), MAX_TIMEOUT_MS) / 1000.0
        self.requests: list[dict[str, Any]] = []
        self.token = os.environ.get(TOKEN_ENV, "").strip()
        ca = config.get("caCertPath")
        if config.get("insecureTls"):
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        elif ca:
            try:
                context = ssl.create_default_context(cafile=ca)
            except (OSError, ssl.SSLError):
                raise Fail("INVALID_CA", "caCertPath could not be loaded", "precondition")
        else:
            context = ssl.create_default_context()
        self.context = context

    def call(self, method: str, path: str, *, body: bytes | None = None, content_type: str | None = None,
             expect_json: bool = True, ok: tuple[int, ...] = (200,), token_override: str | None = None,
             max_bytes: int = MAX_DOWNLOAD_BYTES) -> tuple[int, Any, dict[str, str]]:
        url = self.base + path
        headers = {"Accept": "application/json" if expect_json else "*/*", "User-Agent": f"clawpod-open-design/{VERSION}"}
        token = self.token if token_override is None else token_override
        if token:
            headers["Authorization"] = "Bearer " + token
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        started = time.monotonic()
        status, payload, response_headers = 0, b"", {}
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=self.context) as response:
                status = response.status
                payload = response.read(max_bytes + 1)
                response_headers = {k.lower(): v for k, v in response.headers.items()}
        except urllib.error.HTTPError as error:
            status = error.code
            payload = error.read(65_536)
            response_headers = {k.lower(): v for k, v in error.headers.items()}
        except TimeoutError:
            self._record(method, path, None, started, 0)
            raise Fail("TIMEOUT", f"{method} {path} exceeded {int(self.timeout * 1000)} ms", "timeout")
        except (urllib.error.URLError, ssl.SSLError, OSError) as error:
            self._record(method, path, None, started, 0)
            reason = getattr(error, "reason", error)
            if isinstance(reason, ssl.SSLCertVerificationError):
                raise Fail("TLS_VERIFY_FAILED", "server certificate is not trusted; set caCertPath in config.set (or, only after explicit approval, insecureTlsRiskAccepted)", "unavailable")
            raise Fail("UNREACHABLE", f"{self.base} is unreachable: {type(reason).__name__}", "unavailable")
        self._record(method, path, status, started, len(payload))
        if len(payload) > max_bytes:
            raise Fail("RESPONSE_TOO_LARGE", f"{method} {path} exceeded the {max_bytes}-byte response bound", "failed")
        if status in (401, 403):
            raise Fail("AUTH_REJECTED", f"the server rejected the credential for {method} {path}; verify {TOKEN_ENV} matches the daemon's OD_API_TOKEN", "auth")
        if status not in ok:
            detail = ""
            try:
                parsed = json.loads(payload.decode("utf-8"))
                detail = str(parsed.get("error", {}).get("message") or parsed.get("error") or "")
            except (ValueError, AttributeError):
                pass
            kind = "precondition" if status == 404 else "failed"
            raise Fail("PROVIDER_ERROR", f"{method} {path} returned HTTP {status}" + (f": {detail}" if detail else ""), kind, {"status": status})
        if not expect_json:
            return status, payload, response_headers
        try:
            return status, json.loads(payload.decode("utf-8")) if payload else {}, response_headers
        except ValueError:
            raise Fail("MALFORMED_RESPONSE", f"{method} {path} did not return JSON", "failed")

    def _record(self, method: str, path: str, status: int | None, started: float, size: int) -> None:
        self.requests.append({"method": method, "path": path, "status": status, "durationMs": int((time.monotonic() - started) * 1000), "bytes": size})


def multipart(field: str, filename: str, content: bytes, content_type: str) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\n"
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def check_filename(value: str) -> str:
    if not isinstance(value, str) or not FILENAME_RE.match(value) or value in (".", "..") or value.startswith("."):
        raise Fail("INVALID_FILENAME", "file names must be plain basenames (no path separators, no leading dot)")
    return value


def read_local(path_value: str) -> tuple[str, bytes, str]:
    path = Path(path_value)
    if not path.is_absolute() or not path.is_file():
        raise Fail("INVALID_PATH", f"{path_value} must be an absolute path to an existing file")
    content = path.read_bytes()
    if len(content) > MAX_UPLOAD_BYTES:
        raise Fail("UPLOAD_TOO_LARGE", f"{path.name} exceeds the {MAX_UPLOAD_BYTES}-byte upload bound")
    return check_filename(path.name), content, mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def write_out(path_value: str, content: bytes) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_absolute():
        raise Fail("INVALID_PATH", "outPath must be absolute")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"path": str(path), "bytes": len(content)}


def project_summary(p: dict[str, Any]) -> dict[str, Any]:
    return {"id": p.get("id"), "name": p.get("name"), "kind": (p.get("metadata") or {}).get("kind"),
            "status": (p.get("status") or {}).get("value"), "createdAt": p.get("createdAt"), "updatedAt": p.get("updatedAt")}


# ---------------------------------------------------------------------------
# commands


def cmd_status(args, _root, _config, _client) -> dict[str, Any]:
    return {"name": "open-design", "version": VERSION, "verifiedServerSeries": VERIFIED_SERVER_SERIES,
            "tokenEnv": TOKEN_ENV, "storesSecrets": False, "storesResponses": False}


def cmd_config_set(args, root, _config, _client) -> dict[str, Any]:
    base_url = validate_base_url(args.base_url or "")
    ca = args.ca_cert_path
    if ca:
        ca_path = Path(ca)
        if not ca_path.is_absolute() or not ca_path.is_file():
            raise Fail("INVALID_CA", "caCertPath must be an absolute path to an existing PEM file")
    if os.environ.get(TOKEN_ENV, "") and os.environ[TOKEN_ENV] in json.dumps(vars(args), default=str):
        raise Fail("SECRET_IN_ARGV", "the API token must never appear in arguments; it is read only from the Gateway-injected environment")
    config = {"schemaVersion": SCHEMA_VERSION, "baseUrl": base_url, "caCertPath": ca, "insecureTls": bool(args.insecure_tls_risk_accepted), "updatedAt": now_iso()}
    path = root / "config.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(config, stream, sort_keys=True)
    warnings = []
    if base_url.startswith("http://") and not re.match(r"^http://(127\.|localhost)", base_url):
        warnings.append("baseUrl is plain HTTP on a non-loopback host; the token would travel unencrypted")
    if config["insecureTls"]:
        warnings.append("TLS verification is disabled by explicit risk acceptance; prefer caCertPath")
    return {"config": {k: config[k] for k in ("baseUrl", "caCertPath", "insecureTls", "updatedAt")}, "warnings": warnings,
            "nextAction": "Run health to verify the server, then one bounded read (projects.list) before claiming readiness."}


def cmd_config_status(args, root, config, _client) -> dict[str, Any]:
    return {"config": {k: config.get(k) for k in ("baseUrl", "caCertPath", "insecureTls", "updatedAt")}, "tokenPresent": bool(os.environ.get(TOKEN_ENV, "").strip())}


def cmd_health(args, root, config, client) -> dict[str, Any]:
    _, version, _ = client.call("GET", "/api/version")
    server_version = str((version.get("version") or {}).get("version") or "")
    capabilities = (version.get("version") or {}).get("capabilities") or {}
    # Auth-enforcement probe: a deliberately wrong credential must be rejected when
    # the daemon enforces OD_API_TOKEN. A 200 here means auth is NOT enforced.
    enforced = None
    try:
        status, _, _ = client.call("GET", "/api/projects", token_override="definitely-wrong-token", ok=(200,))
        enforced = False
    except Fail as error:
        if error.code == "AUTH_REJECTED":
            enforced = True
        else:
            raise
    _, projects, _ = client.call("GET", "/api/projects")
    findings = []
    if enforced is False:
        findings.append({"severity": "warning", "code": "AUTH_NOT_ENFORCED", "message": "the daemon accepted a wrong token; OD_API_TOKEN is not set (or auth is disabled) on the server"})
    if not os.environ.get(TOKEN_ENV, "").strip():
        findings.append({"severity": "warning", "code": "TOKEN_ABSENT", "message": f"{TOKEN_ENV} is not injected in this run"})
    if server_version and not server_version.startswith(VERIFIED_SERVER_SERIES + "."):
        findings.append({"severity": "warning", "code": "UNVERIFIED_SERVER_VERSION", "message": f"server {server_version} differs from the verified {VERIFIED_SERVER_SERIES}.x series; re-check the contract on breakage"})
    return {"serverVersion": server_version, "capabilities": capabilities, "authEnforced": enforced,
            "tokenPresent": bool(os.environ.get(TOKEN_ENV, "").strip()), "projectCount": len(projects.get("projects", [])), "findings": findings}


def cmd_projects_list(args, root, config, client) -> dict[str, Any]:
    _, data, _ = client.call("GET", "/api/projects")
    projects = [project_summary(p) for p in data.get("projects", [])]
    return {"projectCount": len(projects), "projects": projects}


def cmd_projects_get(args, root, config, client) -> dict[str, Any]:
    project_id = require_uuid(args.project_id)
    _, data, _ = client.call("GET", f"/api/projects/{project_id}")
    return {"project": data.get("project", data)}


def cmd_projects_create(args, root, config, client) -> dict[str, Any]:
    name = (args.name or "").strip()
    if not 1 <= len(name) <= 200:
        raise Fail("INVALID_NAME", "--name must be 1-200 characters")
    kind = args.kind or "deck"
    if kind not in PROJECT_KINDS:
        raise Fail("INVALID_KIND", f"--kind must be one of {sorted(PROJECT_KINDS)}")
    project_id = str(uuid.uuid4())
    body = json.dumps({"id": project_id, "name": name, "metadata": {"kind": kind, "nameSource": "agent"}, "skipDiscoveryBrief": True}).encode()
    _, data, _ = client.call("POST", "/api/projects", body=body, content_type="application/json")
    project = data.get("project", data)
    return {"project": project_summary(project), "effects": [f"created OpenDesign project {project.get('id')} ({name})"]}


def cmd_projects_delete(args, root, config, client) -> dict[str, Any]:
    project_id = require_uuid(args.project_id)
    if not args.approve:
        raise Fail("APPROVAL_REQUIRED", "deletion requires --exact-name and --approve after explicit approval", "precondition")
    _, data, _ = client.call("GET", f"/api/projects/{project_id}")
    name = (data.get("project") or {}).get("name")
    if not args.exact_name or args.exact_name != name:
        raise Fail("NAME_MISMATCH", "--exact-name must equal the project's displayed name exactly", "precondition", {"displayedName": name})
    client.call("DELETE", f"/api/projects/{project_id}")
    try:
        client.call("GET", f"/api/projects/{project_id}")
        raise Fail("VERIFY_FAILED", "the project still exists after deletion", "failed")
    except Fail as error:
        if error.code != "PROVIDER_ERROR" or error.details.get("status") != 404:
            raise
    return {"projectId": project_id, "deleted": True, "effects": [f"deleted OpenDesign project {project_id} ({name})"]}


def cmd_files_list(args, root, config, client) -> dict[str, Any]:
    project_id = require_uuid(args.project_id)
    _, data, _ = client.call("GET", f"/api/projects/{project_id}/files")
    files = [{"name": f.get("name"), "size": f.get("size"), "kind": f.get("kind"),
              "exports": (f.get("artifactManifest") or {}).get("exports"), "mtime": f.get("mtime")} for f in data.get("files", [])]
    return {"fileCount": len(files), "files": files}


def cmd_files_put(args, root, config, client) -> dict[str, Any]:
    project_id = require_uuid(args.project_id)
    paths = args.path or []
    if not paths or len(paths) > 12:
        raise Fail("INVALID_PATH", "pass 1-12 --path files (the server accepts at most 12 per upload)")
    uploaded, effects = [], []
    for path_value in paths:
        filename, content, content_type = read_local(path_value)
        body, mp_type = multipart("files", filename, content, content_type)
        _, data, _ = client.call("POST", f"/api/projects/{project_id}/upload", body=body, content_type=mp_type)
        for entry in data.get("files", []):
            uploaded.append({"name": entry.get("name"), "size": entry.get("size")})
        # Read back and require byte-identical content before claiming success.
        _, echoed, _ = client.call("GET", f"/api/projects/{project_id}/files/{filename}", expect_json=False)
        if echoed != content:
            raise Fail("VERIFY_FAILED", f"{filename} did not round-trip byte-identically", "failed")
        effects.append(f"uploaded {filename} ({len(content)} bytes) to project {project_id}")
    return {"uploaded": uploaded, "roundTripVerified": True, "effects": effects}


def cmd_files_get(args, root, config, client) -> dict[str, Any]:
    project_id = require_uuid(args.project_id)
    name = check_filename(args.name or "")
    _, content, headers = client.call("GET", f"/api/projects/{project_id}/files/{name}", expect_json=False)
    result = {"name": name, "bytes": len(content), "contentType": headers.get("content-type")}
    if args.out_path:
        result["saved"] = write_out(args.out_path, content)
    else:
        result["content"] = content.decode("utf-8", errors="replace")
    return result


def cmd_preview_link(args, root, config, client) -> dict[str, Any]:
    project_id = require_uuid(args.project_id)
    name = check_filename(args.file or "")
    _, data, _ = client.call("GET", f"/api/projects/{project_id}/preview-url?file={name}")
    relative = data.get("url")
    if not isinstance(relative, str) or not relative.startswith("/"):
        raise Fail("MALFORMED_RESPONSE", "preview-url did not return a relative URL", "failed")
    url = config["baseUrl"] + relative
    status, _, _ = client.call("GET", relative, expect_json=False, token_override="")
    return {"file": name, "url": url, "opensWithoutToken": status == 200, "csp": data.get("csp"),
            "note": "the preview URL embeds a scope token; anyone who can reach the server network can open it"}


def cmd_export_html(args, root, config, client) -> dict[str, Any]:
    project_id = require_uuid(args.project_id)
    name = check_filename(args.file_name or "")
    body = json.dumps({"fileName": name}).encode()
    _, content, headers = client.call("POST", f"/api/projects/{project_id}/export/html", body=body, content_type="application/json", expect_json=False)
    result = {"fileName": name, "bytes": len(content), "contentType": headers.get("content-type")}
    if args.out_path:
        result["saved"] = write_out(args.out_path, content)
    return result


def cmd_export_archive(args, root, config, client) -> dict[str, Any]:
    project_id = require_uuid(args.project_id)
    if not args.out_path:
        raise Fail("INVALID_PATH", "--out-path is required for the ZIP archive")
    _, content, headers = client.call("GET", f"/api/projects/{project_id}/archive", expect_json=False)
    if not content.startswith(b"PK"):
        raise Fail("MALFORMED_RESPONSE", "archive did not return a ZIP payload", "failed")
    return {"contentType": headers.get("content-type"), "saved": write_out(args.out_path, content)}


def cmd_export_manifest(args, root, config, client) -> dict[str, Any]:
    project_id = require_uuid(args.project_id)
    _, data, _ = client.call("GET", f"/api/projects/{project_id}/export/manifest")
    return {"manifest": data}


def cmd_import_claude_design(args, root, config, client) -> dict[str, Any]:
    paths = args.path or []
    if len(paths) != 1:
        raise Fail("INVALID_PATH", "import.claude-design takes exactly one --path to a Claude Design export .zip")
    filename, content, _ = read_local(paths[0])
    if not filename.lower().endswith(".zip") or not content.startswith(b"PK"):
        raise Fail("INVALID_PATH", "import.claude-design requires a Claude Design export .zip")
    body, mp_type = multipart("file", filename, content, "application/zip")
    _, data, _ = client.call("POST", "/api/import/claude-design", body=body, content_type=mp_type)
    project = data.get("project", data)
    return {"project": project_summary(project) if isinstance(project, dict) else project,
            "effects": [f"imported {filename} as an OpenDesign project"]}


def require_uuid(value: str | None) -> str:
    if not value or not re.fullmatch(r"[0-9a-fA-F-]{8,64}", value):
        raise Fail("INVALID_PROJECT_ID", "--project-id must be the project's id")
    return value


COMMANDS = {
    "status": (cmd_status, False, False),
    "config.set": (cmd_config_set, True, False),
    "config.status": (cmd_config_status, True, True),
    "health": (cmd_health, True, True),
    "projects.list": (cmd_projects_list, True, True),
    "projects.get": (cmd_projects_get, True, True),
    "projects.create": (cmd_projects_create, True, True),
    "projects.delete": (cmd_projects_delete, True, True),
    "files.list": (cmd_files_list, True, True),
    "files.put": (cmd_files_put, True, True),
    "files.get": (cmd_files_get, True, True),
    "preview.link": (cmd_preview_link, True, True),
    "export.html": (cmd_export_html, True, True),
    "export.archive": (cmd_export_archive, True, True),
    "export.manifest": (cmd_export_manifest, True, True),
    "import.claude-design": (cmd_import_claude_design, True, True),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="open-design", description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--state-root")
    parser.add_argument("--base-url")
    parser.add_argument("--ca-cert-path")
    parser.add_argument("--insecure-tls-risk-accepted", action="store_true")
    parser.add_argument("--timeout-ms", type=int)
    parser.add_argument("--project-id")
    parser.add_argument("--name")
    parser.add_argument("--kind")
    parser.add_argument("--exact-name")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--path", action="append")
    parser.add_argument("--file")
    parser.add_argument("--file-name")
    parser.add_argument("--out-path")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        print(json.dumps({"ok": False, "schemaVersion": SCHEMA_VERSION, "command": None,
                          "error": {"code": "INVALID_ARGUMENTS", "message": "arguments could not be parsed"}, "effects": []}))
        return EXIT["invalid"]
    handler, needs_state, needs_config = COMMANDS[args.command]
    client = None
    try:
        for value in (argv if argv is not None else sys.argv[1:]):
            token = os.environ.get(TOKEN_ENV, "").strip()
            if token and token in str(value):
                raise Fail("SECRET_IN_ARGV", f"the API token must never appear in arguments; it is read only from {TOKEN_ENV}")
        root = config = None
        if needs_state:
            if not args.state_root:
                raise Fail("INVALID_STATE_ROOT", "--state-root is required")
            root = state_root(args.state_root, create=args.command == "config.set")
        if needs_config:
            config = load_config(root)
            client = Client(args, config)
        data = handler(args, root, config, client)
        effects = data.pop("effects", [])
        data["evidence"] = {"collectedAt": now_iso(), "harnessVersion": VERSION, "requests": client.requests if client else [], "tokenSentFromEnv": bool(client and client.token)}
        print(json.dumps({"ok": True, "schemaVersion": SCHEMA_VERSION, "command": args.command, "data": data, "effects": effects}, ensure_ascii=False, separators=(",", ":")))
        return EXIT["ok"]
    except Fail as error:
        response = {"ok": False, "schemaVersion": SCHEMA_VERSION, "command": args.command,
                    "error": {"code": error.code, "message": error.message, "kind": error.kind, "details": error.details}, "effects": []}
        if client is not None:
            response["data"] = {"evidence": {"collectedAt": now_iso(), "harnessVersion": VERSION, "requests": client.requests, "tokenSentFromEnv": bool(client.token)}}
        print(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
        return EXIT.get(error.kind, EXIT["failed"])


if __name__ == "__main__":
    raise SystemExit(main())
