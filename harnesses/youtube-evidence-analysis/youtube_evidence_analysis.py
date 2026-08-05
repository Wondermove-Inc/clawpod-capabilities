#!/usr/bin/env python3
"""Deterministic, stdlib-only helpers for evidence-led YouTube analysis."""
from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import json
import os
import re
import socket
import stat
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from html.parser import HTMLParser
from pathlib import Path

VERSION = "0.1.1"
MAX_INPUT = 2_000_000
MAX_OUTPUT = 4_000_000
MAX_TRANSCRIPT = 1_500_000
MAX_SEGMENTS = 20_000
MAX_LINKS = 200
MAX_CLAIMS = 500
MAX_EVIDENCE = 100
MAX_DEPTH = 12
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
TIME = re.compile(r"^(?:(\d{1,3}):)?([0-5]?\d):([0-5]\d)(?:[.,](\d{1,3}))?$")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be", "www.youtu.be", "youtube-nocookie.com", "www.youtube-nocookie.com"}


class HarnessError(Exception):
    def __init__(self, code, message, retryable=False, data=None):
        self.code, self.message, self.retryable, self.data = code, message, retryable, data
        super().__init__(message)


def stable(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value):
    return hashlib.sha256(value).hexdigest()


def validate_shape(value, depth=0):
    if depth > MAX_DEPTH:
        raise HarnessError("INPUT_LIMIT", "JSON nesting exceeds limit")
    if isinstance(value, str) and len(value) > MAX_TRANSCRIPT:
        raise HarnessError("INPUT_LIMIT", "string exceeds limit")
    if isinstance(value, list):
        if len(value) > MAX_SEGMENTS:
            raise HarnessError("INPUT_LIMIT", "array exceeds limit")
        for item in value:
            validate_shape(item, depth + 1)
    elif isinstance(value, dict):
        if len(value) > 1000:
            raise HarnessError("INPUT_LIMIT", "object exceeds limit")
        for key, item in value.items():
            validate_shape(key, depth + 1)
            validate_shape(item, depth + 1)


def owner_root(value, output=False):
    if not value:
        raise HarnessError("INVALID_PATH", "explicit existing root required")
    path = Path(value)
    if path.is_symlink():
        raise HarnessError("INVALID_PATH", "symlink root forbidden")
    try:
        path = path.resolve(strict=True)
    except FileNotFoundError:
        raise HarnessError("INVALID_PATH", "root must already exist")
    if not path.is_dir():
        raise HarnessError("INVALID_PATH", "root must be a directory")
    metadata = path.stat()
    if metadata.st_uid != os.getuid():
        raise HarnessError("INVALID_PATH", "root must be owned by the current user")
    mode = stat.S_IMODE(metadata.st_mode)
    if output and (mode & 0o077):
        raise HarnessError("INVALID_PATH", "output root must be owner-only (0700 access bits or stricter)")
    return path


def child(root, name, must_exist=False, output=False):
    base = owner_root(root, output)
    if not isinstance(name, str) or not name or len(name) > 500 or "\0" in name:
        raise HarnessError("INVALID_PATH", "bounded relative child path required")
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts:
        raise HarnessError("INVALID_PATH", "absolute paths and traversal are forbidden")
    current = base
    for part in rel.parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise HarnessError("INVALID_PATH", "symlink path component forbidden")
    target = base / rel
    if must_exist and not target.is_file():
        raise HarnessError("INVALID_PATH", "input file missing")
    return target


def read_bytes(path, limit=MAX_INPUT):
    if path.stat().st_size > limit:
        raise HarnessError("INPUT_LIMIT", "input exceeds byte limit")
    data = path.read_bytes()
    if len(data) > limit:
        raise HarnessError("INPUT_LIMIT", "input exceeds byte limit")
    return data


def load_json(root, name):
    try:
        value = json.loads(read_bytes(child(root, name, True)).decode("utf-8"))
    except UnicodeDecodeError:
        raise HarnessError("MALFORMED_INPUT", "input must be UTF-8")
    except json.JSONDecodeError:
        raise HarnessError("MALFORMED_INPUT", "input must be valid JSON")
    validate_shape(value)
    return value


def atomic_json(root, name, value, overwrite=False):
    path = child(root, name, output=True)
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if len(data) > MAX_OUTPUT:
        raise HarnessError("OUTPUT_LIMIT", "output exceeds byte limit")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise HarnessError("INVALID_PATH", "symlink output parent forbidden")
    if path.exists() and not overwrite:
        existing = read_bytes(path, MAX_OUTPUT)
        if existing == data:
            return str(name), False
        raise HarnessError("OUTPUT_EXISTS", "different output exists; pass --overwrite")
    fd, temp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        try: os.unlink(temp)
        except FileNotFoundError: pass
    return str(name), True


def normalize_video(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise HarnessError("INVALID_VIDEO", "bounded video ID or URL required")
    value = value.strip()
    if VIDEO_ID.fullmatch(value):
        vid = value
    else:
        try: parsed = urllib.parse.urlsplit(value)
        except ValueError: raise HarnessError("INVALID_VIDEO", "malformed YouTube URL")
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in ("http", "https") or host not in YOUTUBE_HOSTS or parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            raise HarnessError("INVALID_VIDEO", "credential-free canonical YouTube HTTP(S) URL required")
        parts = [urllib.parse.unquote(x) for x in parsed.path.split("/") if x]
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        if host.endswith("youtu.be"):
            vid = parts[0] if len(parts) == 1 else ""
        elif parts[:1] in (["watch"],):
            vals = query.get("v", []); vid = vals[0] if len(vals) == 1 else ""
        elif parts and parts[0] in ("shorts", "embed", "live"):
            vid = parts[1] if len(parts) == 2 else ""
        else:
            vid = ""
        if not VIDEO_ID.fullmatch(vid):
            raise HarnessError("INVALID_VIDEO", "URL does not contain one unambiguous 11-character video ID")
    return {"videoId": vid, "canonicalUrl": f"https://www.youtube.com/watch?v={vid}", "embedUrl": f"https://www.youtube.com/embed/{vid}"}


def public_url(url):
    try: parsed = urllib.parse.urlsplit(url)
    except ValueError: raise HarnessError("UNSAFE_URL", "malformed URL")
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise HarnessError("UNSAFE_URL", "credential-free HTTP(S) URL required")
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    try: port = parsed.port
    except ValueError: raise HarnessError("UNSAFE_URL", "invalid port")
    if port not in (None, 80, 443):
        raise HarnessError("UNSAFE_URL", "unsafe port")
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
        if not literal.is_global: raise HarnessError("UNSAFE_URL", "non-public address forbidden")
    except ValueError: pass
    if host == "localhost" or host.endswith(".localhost"):
        raise HarnessError("UNSAFE_URL", "localhost forbidden")
    try: infos = socket.getaddrinfo(host, port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc: raise HarnessError("DNS_ERROR", str(exc), True)
    if any(not ipaddress.ip_address(info[4][0].split("%")[0]).is_global for info in infos):
        raise HarnessError("UNSAFE_URL", "DNS resolved a non-public address")
    netloc = host + ((":" + str(port)) if port else "")
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path or "/", parsed.query, ""))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HarnessError("REDIRECT_FORBIDDEN", "oEmbed redirects are not followed")


def fetch_oembed(video, timeout, max_bytes):
    norm = normalize_video(video)
    if not 1 <= timeout <= 20 or not 1 <= max_bytes <= 500_000:
        raise HarnessError("INPUT_LIMIT", "timeout or byte limit outside allowed bounds")
    query = urllib.parse.urlencode({"url": norm["canonicalUrl"], "format": "json"})
    url = "https://www.youtube.com/oembed?" + query
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "youtube-evidence-analysis/" + VERSION})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            if response.headers.get("Content-Encoding"):
                raise HarnessError("UNSUPPORTED_ENCODING", "compressed oEmbed response rejected")
            if int(response.headers.get("Content-Length", "0") or 0) > max_bytes:
                raise HarnessError("SIZE_LIMIT", "oEmbed response exceeds limit")
            raw = response.read(max_bytes + 1)
    except HarnessError: raise
    except urllib.error.HTTPError as exc: raise HarnessError("OEMBED_HTTP_ERROR", f"oEmbed returned HTTP {exc.code}", exc.code >= 500)
    except (urllib.error.URLError, TimeoutError, OSError) as exc: raise HarnessError("OEMBED_FETCH_ERROR", type(exc).__name__, True)
    if len(raw) > max_bytes: raise HarnessError("SIZE_LIMIT", "oEmbed response exceeds limit")
    try: obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError): raise HarnessError("MALFORMED_RESPONSE", "oEmbed response was not UTF-8 JSON")
    allowed = ("title", "author_name", "author_url", "provider_name", "provider_url", "thumbnail_url", "thumbnail_width", "thumbnail_height", "width", "height", "type", "version")
    metadata = {key: obj[key] for key in allowed if key in obj and isinstance(obj[key], (str, int)) and not isinstance(obj[key], bool)}
    return {**norm, "oembedEndpoint": "https://www.youtube.com/oembed", "metadata": metadata, "rawSha256": sha(raw), "bytes": len(raw)}


def parse_seconds(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 359999.999:
        return round(float(value), 3)
    if isinstance(value, str):
        match = TIME.fullmatch(value.strip())
        if match:
            hours, minutes, seconds, millis = match.groups()
            return round(int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int((millis or "0").ljust(3, "0")) / 1000, 3)
    raise HarnessError("INVALID_TIMESTAMP", "timestamp must be bounded seconds or H:MM:SS.mmm")


def stamp(seconds):
    whole = int(seconds); hours, rem = divmod(whole, 3600); minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def clean_text(value):
    if not isinstance(value, str): raise HarnessError("MALFORMED_TRANSCRIPT", "segment text must be a string")
    value = html.unescape(value).replace("\r\n", "\n").replace("\r", "\n").replace("\0", "")
    value = re.sub(r"[ \t\f\v]+", " ", value).strip()
    return value[:10_000]


def transcript_import(root, name, video, language, source_kind):
    raw = read_bytes(child(root, name, True), MAX_TRANSCRIPT)
    norm = normalize_video(video)
    if not re.fullmatch(r"[A-Za-z0-9-]{2,35}", language or ""):
        raise HarnessError("MALFORMED_INPUT", "BCP-47-like language tag required")
    if source_kind not in ("creator-captions", "auto-captions", "browser-transcript-panel", "user-provided", "accessibility-transcript"):
        raise HarnessError("MALFORMED_INPUT", "explicit transcript source kind required")
    try: value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HarnessError("MALFORMED_TRANSCRIPT", "transcript input must be UTF-8 JSON")
    items = value.get("segments") if isinstance(value, dict) else value
    if not isinstance(items, list) or not items or len(items) > MAX_SEGMENTS:
        raise HarnessError("MALFORMED_TRANSCRIPT", "segments must be a nonempty bounded array")
    segments = []
    for index, item in enumerate(items):
        if not isinstance(item, dict): raise HarnessError("MALFORMED_TRANSCRIPT", f"segment {index} must be an object")
        start = parse_seconds(item.get("start")); end_value = item.get("end")
        if end_value is None and item.get("duration") is not None: end_value = start + parse_seconds(item["duration"])
        end = parse_seconds(end_value)
        text = clean_text(item.get("text"))
        if not text or end <= start or (segments and start < segments[-1]["startSeconds"]):
            raise HarnessError("MALFORMED_TRANSCRIPT", f"segment {index} is empty, reversed, or out of order")
        segments.append({"index": index, "startSeconds": start, "endSeconds": end, "timestamp": stamp(start), "text": text})
    core = {"schemaVersion": 1, **norm, "language": language, "sourceKind": source_kind, "segmentCount": len(segments), "segments": segments, "inputSha256": sha(raw), "untrustedData": True}
    core["transcriptSha256"] = sha(stable(core).encode())
    return core


class Links(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True); self.values = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href: self.values.append(href)


def description_links(root, name):
    raw = read_bytes(child(root, name, True), MAX_INPUT)
    try: text = raw.decode("utf-8")
    except UnicodeDecodeError: raise HarnessError("MALFORMED_INPUT", "description must be UTF-8")
    parser = Links(); parser.feed(text)
    candidates = parser.values + re.findall(r"https?://[^\s<>\]\[(){}\"']+", html.unescape(text))
    found, seen, rejected = [], set(), 0
    for raw_url in candidates[:MAX_LINKS * 4]:
        value = raw_url.rstrip(".,;:!?")
        try: url = public_url(value)
        except HarnessError: rejected += 1; continue
        if url not in seen: seen.add(url); found.append({"url": url, "host": urllib.parse.urlsplit(url).hostname})
        if len(found) >= MAX_LINKS: break
    status = "complete" if len(candidates) <= MAX_LINKS * 4 else "partial"
    return {"status": status, "links": found, "linkCount": len(found), "rejectedCount": rejected, "inputSha256": sha(raw), "untrustedData": True}


def validate_bundle(root, name):
    bundle = load_json(root, name); issues = []; warnings = []
    if not isinstance(bundle, dict): raise HarnessError("MALFORMED_INPUT", "bundle must be an object")
    claims = bundle.get("claims", [])
    if not isinstance(claims, list) or len(claims) > MAX_CLAIMS: raise HarnessError("MALFORMED_INPUT", "claims must be a bounded array")
    ids = set()
    for index, claim in enumerate(claims):
        label = claim.get("id") if isinstance(claim, dict) else None
        if not isinstance(claim, dict): issues.append({"code": "INVALID_CLAIM", "index": index}); continue
        if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", label) or label in ids: issues.append({"code": "INVALID_CLAIM_ID", "index": index})
        else: ids.add(label)
        kind = claim.get("kind")
        if kind not in ("fact", "opinion", "marketing", "sponsorship"): issues.append({"code": "INVALID_CLAIM_KIND", "claimId": label})
        if not isinstance(claim.get("text"), str) or not claim["text"].strip() or len(claim["text"]) > 10_000: issues.append({"code": "INVALID_CLAIM_TEXT", "claimId": label})
        status = claim.get("status")
        if status not in ("supported", "unsupported", "partial", "ambiguous", "contradicted"): issues.append({"code": "INVALID_STATUS", "claimId": label})
        if status in ("partial", "ambiguous", "contradicted"): warnings.append({"code": "NON_FINAL_CLAIM", "claimId": label, "status": status})
        evidence = claim.get("evidence", [])
        if not isinstance(evidence, list) or len(evidence) > MAX_EVIDENCE: issues.append({"code": "INVALID_EVIDENCE", "claimId": label}); continue
        valid = 0
        for item in evidence:
            if not isinstance(item, dict): issues.append({"code": "INVALID_EVIDENCE", "claimId": label}); continue
            try: start = parse_seconds(item.get("start")); end = parse_seconds(item.get("end"))
            except HarnessError: issues.append({"code": "INVALID_TIMESTAMP", "claimId": label}); continue
            quote = item.get("quote"); url = item.get("url")
            try: norm = normalize_video(url)
            except HarnessError: issues.append({"code": "INVALID_VIDEO_URL", "claimId": label}); continue
            if end <= start or not isinstance(quote, str) or not quote.strip() or len(quote) > 10_000: issues.append({"code": "INVALID_EVIDENCE", "claimId": label}); continue
            timestamp_url = norm["canonicalUrl"] + "&t=" + str(int(start)) + "s"
            if item.get("timestampUrl") != timestamp_url: issues.append({"code": "TIMESTAMP_URL_MISMATCH", "claimId": label}); continue
            valid += 1
        if kind == "fact" and status == "supported" and valid == 0: issues.append({"code": "TIMESTAMPED_EVIDENCE_REQUIRED", "claimId": label})
        if kind in ("opinion", "marketing", "sponsorship") and claim.get("materialFact") is True: warnings.append({"code": "MATERIAL_CLAIM_REQUIRES_VERIFIED_RESEARCH", "claimId": label})
    supplied = bundle.get("bundleSha256")
    core = {k: v for k, v in bundle.items() if k != "bundleSha256"}
    expected = sha(stable(core).encode())
    if supplied is not None and supplied != expected: issues.append({"code": "BUNDLE_HASH_MISMATCH"})
    return {"valid": not issues, "status": "invalid" if issues else ("partial" if warnings else "complete"), "issues": issues, "warnings": warnings, "claimCount": len(claims), "bundleSha256": expected}


def fallback(video):
    return {"status": "unavailable", "reason": "caption acquisition is intentionally unsupported", "video": normalize_video(video), "fallback": {"type": "browser-transcript-panel", "steps": ["Open the canonical video page in a browser", "Open the description/more menu and choose Show transcript", "Select the requested language when available", "Copy timestamped transcript text to a bounded UTF-8 JSON file", "Import it with transcript.import using sourceKind browser-transcript-panel"], "requiredCapture": {"segments": [{"start": "M:SS", "end": "M:SS", "text": "verbatim caption text"}]}, "failurePolicy": "If the transcript panel or subtitles are unavailable, report unavailable and request an accessibility transcript; do not scrape page internals."}}


def command(args):
    if args.command == "status":
        return {"status": "ready", "version": VERSION, "network": "oEmbed only", "captionAcquisition": "fail-closed", "writes": "owner-only explicit roots"}
    if args.command == "preflight":
        return {"status": "ready", "checks": {"pythonStdlib": True, "credentialsRequired": False, "arbitraryCommands": False, "captionScraping": False}, "limits": {"timeoutSeconds": 20, "inputBytes": MAX_INPUT, "outputBytes": MAX_OUTPUT, "segments": MAX_SEGMENTS}}
    if args.command == "video.normalize": return normalize_video(args.video)
    if args.command == "metadata.oembed": return fetch_oembed(args.video, args.timeout, args.max_bytes)
    if args.command == "caption.fallback": return fallback(args.video)
    if args.command == "transcript.import": data = transcript_import(args.input_root, args.input, args.video, args.language, args.source_kind)
    elif args.command == "description.links": data = description_links(args.input_root, args.input)
    elif args.command == "bundle.validate": return validate_bundle(args.input_root, args.input)
    else:
        if args.command not in ("transcript.import", "description.links"): raise HarnessError("UNKNOWN_COMMAND", "unknown command")
    effects = []
    if args.output or args.output_root:
        if not args.output or not args.output_root: raise HarnessError("MALFORMED_INPUT", "output requires both output root and relative name")
        path, written = atomic_json(args.output_root, args.output, data, args.overwrite)
        effects.append({"type": "write" if written else "unchanged", "path": path})
    return {"result": data, "effects": effects}


def envelope(name, data=None, error=None):
    effects = data.pop("effects", []) if isinstance(data, dict) and "effects" in data else []
    result = {"ok": error is None, "schemaVersion": 1, "command": name, "requestId": str(uuid.uuid4()), "data": data, "effects": effects, "provenance": {"tool": "youtube-evidence-analysis", "version": VERSION}}
    if error: result["error"] = {"code": error.code, "message": error.message, "retryable": error.retryable}
    return result


def parser():
    value = argparse.ArgumentParser()
    value.add_argument("command", choices=("status", "preflight", "video.normalize", "metadata.oembed", "caption.fallback", "transcript.import", "description.links", "bundle.validate"))
    value.add_argument("--video"); value.add_argument("--input-root"); value.add_argument("--input"); value.add_argument("--output-root"); value.add_argument("--output")
    value.add_argument("--language", default="en"); value.add_argument("--source-kind", default="user-provided")
    value.add_argument("--timeout", type=int, default=10); value.add_argument("--max-bytes", type=int, default=500_000); value.add_argument("--overwrite", action="store_true")
    return value


if __name__ == "__main__":
    parsed = parser().parse_args()
    try: print(json.dumps(envelope(parsed.command, command(parsed)), ensure_ascii=False, sort_keys=True)); raise SystemExit(0)
    except HarnessError as exc:
        print(json.dumps(envelope(parsed.command, exc.data, exc), ensure_ascii=False, sort_keys=True)); raise SystemExit(4 if exc.retryable else 2)
    except Exception:
        exc = HarnessError("INTERNAL_ERROR", "unexpected internal error; details suppressed")
        print(json.dumps(envelope(getattr(parsed, "command", "unknown"), error=exc), ensure_ascii=False, sort_keys=True)); raise SystemExit(5)
