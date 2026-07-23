"""Agent-local Atlassian OAuth 2.0 (3LO) onboarding.

Atlassian requires one distributable confidential 3LO app, an exact registered
callback URL, state, and a client secret. The app config must register the fixed
loopback redirect used here. Atlassian does not document PKCE for this flow, so
this module does not invent a code_challenge parameter.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import stat
import threading
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"
RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
ME_URL = "https://api.atlassian.com/me"
CALLBACK_PATH = "/oauth/atlassian/callback"
ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class OAuthFailure(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable


def _private_path(root, relative, *, existing):
    if not root or not relative or Path(relative).is_absolute():
        raise OAuthFailure("oauth_path_invalid", "transfer root and a relative path are required")
    r = Path(root).expanduser().resolve()
    if not r.is_dir() or (os.name != "nt" and (r.stat().st_uid != os.getuid() or stat.S_IMODE(r.stat().st_mode) & 0o077)):
        raise OAuthFailure("oauth_permissions", "transfer root must be an owner-controlled private directory")
    p0 = r / relative
    for q in (r, *r.parents, p0, *p0.parents):
        if q.exists() and q.is_symlink():
            raise OAuthFailure("oauth_path_invalid", "symlink path components are forbidden")
    p = p0.resolve()
    if p != r and r not in p.parents:
        raise OAuthFailure("oauth_path_invalid", "OAuth path escapes transfer root")
    if existing and (not p.is_file() or p.is_symlink()):
        raise OAuthFailure("oauth_path_invalid", "OAuth input must be a regular file")
    if p.exists() and not p.is_file():
        raise OAuthFailure("oauth_path_invalid", "OAuth path must be a regular file")
    if p.exists() and os.name != "nt" and stat.S_IMODE(p.stat().st_mode) != 0o600:
        raise OAuthFailure("oauth_permissions", "OAuth files must be mode 0600")
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        current = p.parent
        while True:
            if current.stat().st_uid != os.getuid() or stat.S_IMODE(current.stat().st_mode) & 0o077:
                raise OAuthFailure("oauth_permissions", "OAuth parent directories must be owner-controlled and private")
            if current == r: break
            current = current.parent
    return p


def _loopback_redirect(value):
    try:
        u = urllib.parse.urlsplit(value)
        ip = ipaddress.ip_address(u.hostname or "")
    except Exception:
        raise OAuthFailure("oauth_redirect_invalid", "registered redirect must use a literal loopback IP") from None
    if (u.scheme != "http" or not ip.is_loopback or u.username or u.password or
            u.query or u.fragment or not u.port or u.path != CALLBACK_PATH):
        raise OAuthFailure("oauth_redirect_invalid", "registered redirect must be fixed loopback HTTP with the approved callback path")
    if ip.version != 4 or ip.compressed != "127.0.0.1":
        raise OAuthFailure("oauth_redirect_invalid", "registered redirect must use 127.0.0.1")
    return f"http://127.0.0.1:{u.port}{CALLBACK_PATH}", u.port


def _devtools_endpoint(value):
    try:
        u = urllib.parse.urlsplit(value)
        ip = ipaddress.ip_address(u.hostname or "")
    except Exception:
        raise OAuthFailure("browser_endpoint_invalid", "managed browser endpoint must use a loopback IP") from None
    if u.scheme != "http" or not ip.is_loopback or u.username or u.password or u.query or u.fragment or u.path not in ("", "/") or not u.port:
        raise OAuthFailure("browser_endpoint_invalid", "managed browser endpoint must be loopback-only HTTP with an explicit port")
    return f"http://127.0.0.1:{u.port}"


def _client(path):
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        c = doc["oauth2"]
    except Exception:
        raise OAuthFailure("oauth_client_invalid", "OAuth client file is malformed") from None
    required = ("client_id", "client_secret", "redirect_uri", "scopes")
    if not all(k in c for k in required) or not all(isinstance(c[k], str) and c[k] for k in required[:3]):
        raise OAuthFailure("oauth_client_invalid", "OAuth client file is malformed")
    if not isinstance(c["scopes"], list) or not c["scopes"] or not all(isinstance(x, str) and x and " " not in x for x in c["scopes"]):
        raise OAuthFailure("oauth_client_invalid", "OAuth scopes must be a non-empty string array")
    scopes = list(dict.fromkeys(c["scopes"]))
    if not {"offline_access", "read:me"}.issubset(scopes):
        raise OAuthFailure("oauth_scope_invalid", "OAuth app scopes must include offline_access and read:me")
    redirect, port = _loopback_redirect(c["redirect_uri"])
    return {"client_id": c["client_id"], "client_secret": c["client_secret"], "redirect_uri": redirect, "scopes": scopes}, port


def _fsync_dir(path):
    if os.name == "nt": return
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try: os.fsync(fd)
    finally: os.close(fd)


@contextmanager
def _bundle_lock(path, timeout=5):
    lock = path.parent / ("." + path.name + ".refresh.lock")
    deadline = time.monotonic() + timeout
    fd = None
    while fd is None:
        try: fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if time.monotonic() >= deadline: raise OAuthFailure("oauth_lock_timeout", "credential refresh lock timed out", True)
            time.sleep(.01)
    try: yield
    finally:
        os.close(fd); lock.unlink(missing_ok=True); _fsync_dir(path.parent)


def _atomic_json(path, value, *, overwrite):
    data = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    tmp = path.parent / ("." + path.name + "." + secrets.token_hex(8) + ".part")
    fd = None
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            fd = None
            f.write(data); f.flush(); os.fsync(f.fileno())
        if overwrite:
            os.replace(tmp, path)
        else:
            try:
                os.link(tmp, path); tmp.unlink()
            except FileExistsError:
                raise OAuthFailure("oauth_output_exists", "OAuth output exists; pass overwrite explicitly") from None
        os.chmod(path, 0o600); _fsync_dir(path.parent)
    finally:
        if fd is not None:
            os.close(fd)
        tmp.unlink(missing_ok=True)


def _receiver(port, state, timeout, server_factory=HTTPServer):
    result, done = {}, threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def reply(self, status, text):
            body = text.encode()
            self.send_response(status); self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            u = urllib.parse.urlsplit(self.path)
            host = self.headers.get("Host", "").split(":", 1)[0]
            if u.path != CALLBACK_PATH or u.fragment or host != "127.0.0.1": self.reply(404, "Not found"); return
            q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
            if done.is_set(): self.reply(409, "Callback already received"); return
            if not hmac.compare_digest(q.get("state", [""])[0], state):
                result["error"] = "oauth_state_mismatch"; done.set(); self.reply(400, "Invalid OAuth response"); return
            if q.get("error"):
                result["error"] = "oauth_denied"; done.set(); self.reply(400, "Authorization denied"); return
            code = q.get("code", [""])[0]
            if not code:
                result["error"] = "oauth_code_missing"; done.set(); self.reply(400, "Invalid OAuth response"); return
            result["code"] = code; done.set(); self.reply(200, "Authorization complete. You may close this tab.")
        def do_POST(self): self.reply(405, "Method not allowed")

    try:
        server = server_factory(("127.0.0.1", port), Handler)
    except Exception:
        raise OAuthFailure("oauth_callback_unavailable", "could not bind the registered loopback callback") from None
    server.timeout = .2
    def wait():
        deadline = time.monotonic() + timeout
        while not done.is_set() and time.monotonic() < deadline: server.handle_request()
        server.server_close(); done.set()
    threading.Thread(target=wait, daemon=True).start()
    return result, done


def _open_devtools(endpoint, url, timeout=5):
    endpoint = _devtools_endpoint(endpoint)
    req = urllib.request.Request(endpoint + "/json/new?" + urllib.parse.quote(url, safe=""), method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=min(timeout, 5)) as r: doc = json.load(r)
    except Exception:
        return False
    return isinstance(doc, dict) and bool(doc.get("id"))


def _json_request(method, url, *, token=None, body=None, timeout=30, opener=urllib.request.urlopen):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Accept": "application/json", "User-Agent": "clawpod-atlassian-oauth/0.2"}
    if body is not None: headers["Content-Type"] = "application/json"
    if token: headers["Authorization"] = "Bearer " + token
    try:
        with opener(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=timeout) as r:
            raw = r.read(); return json.loads(raw) if raw else {}
    except Exception:
        raise OAuthFailure("oauth_provider_rejected", "Atlassian OAuth endpoint rejected the request", True) from None


def _select_resource(resources, resource_url):
    wanted = resource_url.rstrip("/")
    found = [r for r in resources if isinstance(r, dict) and str(r.get("url", "")).rstrip("/") == wanted]
    if len(found) != 1 or not isinstance(found[0].get("id"), str):
        raise OAuthFailure("oauth_resource_unavailable", "requested Atlassian site was not granted")
    return found[0]


def _load_site_document(path, alias, overwrite):
    current = {"sites": {}}
    if path.exists():
        try: current = json.loads(path.read_text(encoding="utf-8"))
        except Exception: raise OAuthFailure("site_config_invalid", "site alias file is invalid JSON") from None
    if not isinstance(current, dict) or not isinstance(current.setdefault("sites", {}), dict):
        raise OAuthFailure("site_config_invalid", "site alias file is invalid JSON")
    if alias in current["sites"] and not overwrite:
        raise OAuthFailure("site_alias_exists", "site alias exists; pass overwrite explicitly")
    return current


def _site_document(current, alias, resource, credential_path):
    sites = current["sites"]
    cloud = resource["id"]
    sites[alias] = {
        "jiraBaseUrl": f"https://api.atlassian.com/ex/jira/{cloud}",
        "confluenceBaseUrl": f"https://api.atlassian.com/ex/confluence/{cloud}",
        "auth": {"type": "oauth", "tokenRef": "file:" + str(credential_path)},
        "resourceUrl": resource.get("url"), "resourceName": resource.get("name"), "cloudId": cloud,
    }
    return current


def _smoke(access_token, cloud_id, services, timeout, opener):
    specs = {
        "jira": f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/myself",
        "confluence": f"https://api.atlassian.com/ex/confluence/{cloud_id}/wiki/api/v2/spaces?limit=1",
    }
    out = {}
    for service in services:
        if service not in specs: raise OAuthFailure("oauth_smoke_invalid", "unknown smoke service")
        try:
            doc = _json_request("GET", specs[service], token=access_token, timeout=min(timeout, 15), opener=opener)
            out[service] = {"ok": isinstance(doc, dict)}
        except OAuthFailure:
            out[service] = {"ok": False, "error": "REQUEST_FAILED"}
    return out


def login(*, transfer_root, client_path, output_path, sites_output_path, site_alias, resource_url,
          managed_browser_devtools_url, timeout=300, overwrite=False, smoke_tests=("jira", "confluence"),
          opener=urllib.request.urlopen, open_devtools=_open_devtools, server_factory=HTTPServer):
    if not ALIAS.fullmatch(site_alias or ""): raise OAuthFailure("site_alias_invalid", "invalid site alias")
    if not 5 <= timeout <= 600: raise OAuthFailure("oauth_timeout_invalid", "OAuth timeout must be 5..600 seconds")
    ru = urllib.parse.urlsplit(resource_url or "")
    if ru.scheme != "https" or not ru.netloc or ru.username or ru.query or ru.fragment:
        raise OAuthFailure("oauth_resource_invalid", "resourceUrl must be an HTTPS Atlassian site origin")
    cp = _private_path(transfer_root, client_path, existing=True)
    op = _private_path(transfer_root, output_path, existing=False)
    sp = _private_path(transfer_root, sites_output_path, existing=False)
    paths = (cp, op, sp)
    if len(set(paths)) != len(paths) or any(a in b.parents or b in a.parents for i, a in enumerate(paths) for b in paths[i+1:]):
        raise OAuthFailure("oauth_path_invalid", "OAuth client, credential, and site paths must be distinct")
    if not overwrite and (op.exists() or sp.exists()):
        raise OAuthFailure("oauth_output_exists", "OAuth output exists; pass overwrite explicitly")
    site_template = _load_site_document(sp, site_alias, overwrite)
    client, port = _client(cp)
    endpoint = _devtools_endpoint(managed_browser_devtools_url)
    state = secrets.token_urlsafe(32)
    result, done = _receiver(port, state, timeout, server_factory)
    query = {"audience": "api.atlassian.com", "client_id": client["client_id"], "scope": " ".join(client["scopes"]),
             "redirect_uri": client["redirect_uri"], "state": state, "response_type": "code", "prompt": "consent"}
    authorize = AUTHORIZE_URL + "?" + urllib.parse.urlencode(query, quote_via=urllib.parse.quote)
    if not open_devtools(endpoint, authorize, min(timeout, 5)):
        done.set()
        raise OAuthFailure("browser_open_failed", "could not open the agent-managed browser")
    if not done.wait(timeout + .5): raise OAuthFailure("oauth_timeout", "authorization timed out", True)
    if result.get("error"): raise OAuthFailure(result["error"], "authorization failed")
    code = result.pop("code", None)
    if not code: raise OAuthFailure("oauth_timeout", "authorization timed out", True)
    token = _json_request("POST", TOKEN_URL, body={"grant_type": "authorization_code", "client_id": client["client_id"],
        "client_secret": client["client_secret"], "code": code, "redirect_uri": client["redirect_uri"]}, timeout=min(timeout, 30), opener=opener)
    if not isinstance(token, dict) or not all(isinstance(token.get(k), str) and token[k] for k in ("access_token", "refresh_token")):
        raise OAuthFailure("oauth_token_invalid", "token response omitted reusable credentials")
    granted = set(str(token.get("scope", "")).split())
    if set(client["scopes"]) - granted: raise OAuthFailure("oauth_scope_missing", "token response omitted requested scopes")
    resources = _json_request("GET", RESOURCES_URL, token=token["access_token"], timeout=min(timeout, 30), opener=opener)
    if not isinstance(resources, list): raise OAuthFailure("oauth_resources_invalid", "accessible resources response was invalid")
    resource = _select_resource(resources, resource_url)
    ident = _json_request("GET", ME_URL, token=token["access_token"], timeout=min(timeout, 30), opener=opener)
    account_id = ident.get("account_id") if isinstance(ident, dict) else None
    if not isinstance(account_id, str) or not account_id: raise OAuthFailure("oauth_identity_invalid", "identity response was invalid")
    bundle = {"schemaVersion": 1, "type": "atlassian-oauth-3lo", "client_id": client["client_id"],
        "client_secret": client["client_secret"], "redirect_uri": client["redirect_uri"], "access_token": token["access_token"],
        "refresh_token": token["refresh_token"], "expires_at": int(time.time()) + int(token.get("expires_in", 3600)),
        "scopes": sorted(granted), "account_id_hash": hashlib.sha256(account_id.encode()).hexdigest(), "site_alias": site_alias,
        "cloud_id": resource["id"], "resource_url": resource.get("url")}
    site_doc = _site_document(site_template, site_alias, resource, op)
    old_op = op.read_bytes() if op.exists() else None
    old_sp = sp.read_bytes() if sp.exists() else None
    try:
        _atomic_json(op, bundle, overwrite=overwrite)
        _atomic_json(sp, site_doc, overwrite=overwrite)
    except Exception:
        for path, previous in ((op, old_op), (sp, old_sp)):
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                tmp = path.parent / ("." + path.name + ".rollback." + secrets.token_hex(8))
                fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as f: f.write(previous); f.flush(); os.fsync(f.fileno())
                os.replace(tmp, path); os.chmod(path, 0o600)
        raise OAuthFailure("oauth_storage_failed", "OAuth credential and site configuration were not committed") from None
    smoke = _smoke(token["access_token"], resource["id"], tuple(dict.fromkeys(smoke_tests)), timeout, opener)
    return {"siteAlias": site_alias, "accountIdHash": bundle["account_id_hash"], "resourceName": resource.get("name"),
            "resourceUrl": resource.get("url"), "scopes": sorted(granted), "expiresAt": bundle["expires_at"],
            "smokeTests": smoke, "desktopLocal": True, "browserMode": "managed-devtools"}


def _bundle(transfer_root, output_path):
    p = _private_path(transfer_root, output_path, existing=True)
    try: b = json.loads(p.read_text(encoding="utf-8"))
    except Exception: raise OAuthFailure("oauth_bundle_invalid", "credential bundle is invalid") from None
    if b.get("type") != "atlassian-oauth-3lo": raise OAuthFailure("oauth_bundle_invalid", "credential bundle is invalid")
    return p, b


def status(*, transfer_root, output_path):
    _, b = _bundle(transfer_root, output_path)
    return {"siteAlias": b.get("site_alias"), "accountIdHash": b.get("account_id_hash"), "resourceUrl": b.get("resource_url"),
            "scopes": b.get("scopes", []), "expiresAt": b.get("expires_at"), "expired": int(time.time()) >= int(b.get("expires_at", 0))}


def refresh(*, transfer_root, output_path, timeout=30, opener=urllib.request.urlopen):
    p = _private_path(transfer_root, output_path, existing=True)
    with _bundle_lock(p):
        _, b = _bundle(transfer_root, output_path)
        token = _json_request("POST", TOKEN_URL, body={"grant_type": "refresh_token", "client_id": b.get("client_id"),
            "client_secret": b.get("client_secret"), "refresh_token": b.get("refresh_token")}, timeout=min(timeout, 30), opener=opener)
        if not isinstance(token, dict) or not isinstance(token.get("access_token"), str) or not isinstance(token.get("refresh_token"), str):
            raise OAuthFailure("oauth_refresh_invalid", "refresh response omitted rotated credentials")
        b["access_token"] = token["access_token"]; b["refresh_token"] = token["refresh_token"]
        b["expires_at"] = int(time.time()) + int(token.get("expires_in", 3600))
        if token.get("scope"): b["scopes"] = sorted(set(str(token["scope"]).split()))
        _atomic_json(p, b, overwrite=True)
        return {"siteAlias": b.get("site_alias"), "scopes": b.get("scopes", []), "expiresAt": b["expires_at"], "rotated": True}
