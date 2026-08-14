"""Secure pod-local Google Workspace credential bindings.

Only identity metadata and credential references live in the registry.  Secret
files are opened without following links, all registry access is serialized,
and registry replacement is durable before a transaction is reported complete.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import time
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - the Windows adapter is exercised on Windows CI
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

ALIAS = re.compile(r"^[a-z][a-z0-9._-]{0,62}$")
OPAQUE_CREDENTIAL = re.compile(r"^[a-f0-9]{32}\.json$")
BACKUP_NAME = re.compile(r"^bindings\.v1\.[a-f0-9]{24}\.json$")
TOP_KEYS = {"schemaVersion", "revision", "updatedAt", "bindings", "migration"}
BINDING_KEYS = {
    "credentialRef", "subjectHash", "emailHint", "createdAt", "updatedAt",
    "source", "bundleFormat", "externalReference",
}
MIGRATION_KEYS = {"legacyScanCompletedAt"}
MAX_REGISTRY = 1024 * 1024
MAX_CREDENTIAL = 64 * 1024 * 1024
LOCK_TIMEOUT = 5.0
BACKUP_LIMIT = 5


class BindingError(Exception):
    def __init__(self, code: str, message: str, details=None, *, committed=False):
        super().__init__(message)
        self.code = code
        self.details = details or {}
        self.committed = committed


def _now(clock=None):
    value = (clock or (lambda: datetime.now(timezone.utc)))()
    return value.isoformat().replace("+00:00", "Z")


def normalize_alias(value: str) -> str:
    if not isinstance(value, str):
        raise BindingError("INVALID_ARGUMENT", "alias must be a string")
    normalized = unicodedata.normalize("NFC", value)
    if normalized != value or value.lower() != value or value in (".", "..") or not ALIAS.fullmatch(value):
        raise BindingError("INVALID_ARGUMENT", "alias must match ^[a-z][a-z0-9._-]{0,62}$")
    return value


def binding_root(env=None, platform=None, home=None) -> Path:
    env = os.environ if env is None else env
    platform = os.sys.platform if platform is None else platform
    configured = env.get("GOOGLE_WORKSPACE_BINDING_ROOT")
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            raise BindingError("BINDING_PATH_UNSAFE", "configured binding root must be absolute")
    elif platform == "win32":
        base = env.get("LOCALAPPDATA")
        if not base or not Path(base).is_absolute():
            raise BindingError("BINDING_PATH_UNSAFE", "LOCALAPPDATA must be an absolute trusted state location")
        candidate = Path(base) / "OpenClaw" / "google-workspace"
    elif platform == "darwin":
        candidate = Path(home or env.get("HOME") or Path.home()) / "Library" / "Application Support" / "OpenClaw" / "google-workspace"
    else:
        base = env.get("XDG_STATE_HOME")
        if base and not Path(base).is_absolute():
            raise BindingError("BINDING_PATH_UNSAFE", "XDG_STATE_HOME must be absolute")
        state = Path(base) if base else Path(home or env.get("HOME") or Path.home()) / ".local" / "state"
        candidate = state / "openclaw" / "google-workspace"
    candidate = Path(os.path.abspath(candidate))
    repo = Path(__file__).resolve().parents[3]
    forbidden = [repo / "skills", repo / "harnesses", repo / "registry"]
    if any(candidate == base or base in candidate.parents for base in forbidden):
        raise BindingError("BINDING_PATH_UNSAFE", "binding root cannot be inside replaceable package or registry storage")
    if any(part in {"staging", ".staging"} for part in candidate.parts):
        raise BindingError("BINDING_PATH_UNSAFE", "binding root cannot be inside staging storage")
    return candidate


def _owned(info):
    return not hasattr(os, "geteuid") or info.st_uid == os.geteuid()


def _private(info, directory=False):
    expected_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    expected_mode = 0o700 if directory else 0o600
    return expected_type and not stat.S_ISLNK(info.st_mode) and (os.name == "nt" or stat.S_IMODE(info.st_mode) == expected_mode)


def _check_info(info, *, directory=False, hardlink=True):
    if not _owned(info) or (hasattr(os, "getegid") and info.st_gid != os.getegid()):
        raise BindingError("BINDING_PERMISSION_DENIED", "protected artifact is not owned by the current process identity")
    if not _private(info, directory):
        raise BindingError("BINDING_PERMISSION_INSECURE", "protected artifact has an unsafe type or permissions")
    if hardlink and not directory and os.name != "nt" and info.st_nlink != 1:
        raise BindingError("BINDING_PATH_UNSAFE", "protected file must have exactly one hard link")


def _check_artifact(path: Path, directory=False, allow_missing=False, hardlink=True):
    try:
        info = path.lstat()
    except FileNotFoundError:
        if allow_missing:
            return None
        raise BindingError("BINDING_PATH_UNSAFE", "required protected artifact is missing") from None
    _check_info(info, directory=directory, hardlink=hardlink)
    return info


def _exact_forge_location(paths):
    expected = tuple(Path("/root/.local/state/openclaw/google-workspace").parents)[::-1][1:]
    return tuple(paths) == expected + (Path("/root/.local/state/openclaw/google-workspace"),)


def _parent_snapshot(path: Path):
    """Validate and snapshot ancestors without following links.

    The only non-sticky shared exception is Forge's complete process-owned
    root/.local/state/openclaw/google-workspace suffix with exact modes
    02777/02775/02775/02775/0700. Exact 01777 remains the generic sticky case.
    """
    if not path.is_absolute():
        raise BindingError("BINDING_PATH_UNSAFE", "protected file path must be absolute")
    current = Path(path.anchor)
    ancestors = []
    for part in path.parts[1:-1]:
        current /= part
        try:
            info = current.lstat()
        except OSError:
            raise BindingError("BINDING_PATH_UNSAFE", "protected file parent is unavailable") from None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise BindingError("BINDING_PATH_UNSAFE", "protected file parent is unsafe")
        ancestors.append((current, info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid))
    forge_names = ("root", ".local", "state", "openclaw", "google-workspace")
    forge_modes = (0o2777, 0o2775, 0o2775, 0o2775, 0o700)
    forge_start = next((start for start in range(len(ancestors) - len(forge_names) + 1)
                        if all(item[0].name == name and stat.S_IMODE(item[3]) == mode
                               and (not hasattr(os, "geteuid") or item[4] == os.geteuid())
                               and (not hasattr(os, "getegid") or item[5] == os.getegid())
                               for item, name, mode in
                               zip(ancestors[start:start + len(forge_names)], forge_names, forge_modes))
                        and _exact_forge_location([item[0] for item in
                                                  ancestors[start:start + len(forge_names)]])), -1)
    exact_forge = forge_start >= 0
    for number, (current, _device, _inode, mode, owner, group) in enumerate(ancestors):
        if mode & 0o022:
            forge_member = exact_forge and forge_start <= number < forge_start + len(forge_names)
            sticky = stat.S_IMODE(mode) == 0o1777
            process_owned = (not hasattr(os, "geteuid") or owner == os.geteuid())
            process_group = (not hasattr(os, "getegid") or group == os.getegid())
            if not ((forge_member or sticky) and process_owned and process_group):
                raise BindingError("BINDING_PATH_UNSAFE", "protected file parent is writable by another user")
            descendants = ancestors[number + 1:]
            if not any(_owned_path and not descendant_mode & 0o022
                       for _path, _dev, _ino, descendant_mode, descendant_owner, descendant_group in descendants
                       for _owned_path in [(not hasattr(os, "geteuid") or descendant_owner == os.geteuid())
                                           and (not hasattr(os, "getegid") or descendant_group == os.getegid())]):
                raise BindingError("BINDING_PATH_UNSAFE", "shared parent lacks an owned private containment boundary")
    return ancestors


def _check_parent_chain(path: Path):
    return _parent_snapshot(path)


def _verify_parent_snapshot(snapshot):
    for path, device, inode, mode, owner, group in snapshot:
        try:
            info = path.lstat()
        except OSError:
            raise BindingError("BINDING_PATH_UNSAFE", "protected file parent changed during access") from None
        if (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid) != (device, inode, mode, owner, group):
            raise BindingError("BINDING_PATH_UNSAFE", "protected file parent changed during access")


def _open_checked(path: Path, *, max_bytes: int, hardlink=True):
    parents = _check_parent_chain(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        raise BindingError("BINDING_PATH_UNSAFE", "protected file could not be opened safely") from None
    try:
        info = os.fstat(fd)
        _check_info(info, hardlink=hardlink)
        current = path.lstat()
        if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
            raise BindingError("BINDING_PATH_UNSAFE", "protected file changed while it was opened")
        if info.st_size > max_bytes:
            raise BindingError("BINDING_REGISTRY_CORRUPT" if max_bytes == MAX_REGISTRY else "AUTH_REQUIRED", "protected file exceeds its size limit")
        chunks = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > max_bytes:
            raise BindingError("BINDING_REGISTRY_CORRUPT" if max_bytes == MAX_REGISTRY else "AUTH_REQUIRED", "protected file exceeds its size limit")
        after = os.fstat(fd)
        if (info.st_dev, info.st_ino, info.st_size) != (after.st_dev, after.st_ino, after.st_size):
            raise BindingError("BINDING_PATH_UNSAFE", "protected file changed while it was read")
        _verify_parent_snapshot(parents)
        return raw, info
    finally:
        os.close(fd)


def ensure_root(root=None) -> Path:
    root = Path(root) if root is not None else binding_root()
    if not root.is_absolute():
        raise BindingError("BINDING_PATH_UNSAFE", "binding root must be absolute")
    try:
        root.lstat()
        root_existed = True
    except FileNotFoundError:
        root_existed = False
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        raise BindingError("BINDING_PERMISSION_DENIED", "binding root cannot be created securely") from None
    if not root_existed:
        created = root.lstat()
        if not _owned(created) or not stat.S_ISDIR(created.st_mode) or stat.S_ISLNK(created.st_mode):
            raise BindingError("BINDING_PATH_UNSAFE", "new binding root has an unsafe owner or type")
        # A setgid collaborative ancestor can propagate its bit despite the
        # requested mkdir mode. Remove inherited group semantics before use.
        os.chmod(root, 0o700, follow_symlinks=False)
    _check_artifact(root, directory=True)
    _check_parent_chain(root / ".containment-check")
    for name in ("credentials", "backups"):
        path = root / name
        try:
            path.mkdir(mode=0o700, exist_ok=True)
        except OSError:
            raise BindingError("BINDING_PERMISSION_DENIED", "protected directory cannot be created securely") from None
        _check_artifact(path, directory=True)
    return root


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise BindingError("BINDING_REGISTRY_CORRUPT", "registry contains a duplicate key")
        out[key] = value
    return out


def empty_registry(clock=None):
    return {"schemaVersion": 1, "revision": 0, "updatedAt": _now(clock), "bindings": {}, "migration": {"legacyScanCompletedAt": None}}


def validate_registry(doc):
    if not isinstance(doc, dict) or set(doc) != TOP_KEYS:
        raise BindingError("BINDING_REGISTRY_CORRUPT", "registry has unknown or missing top-level keys")
    if doc.get("schemaVersion") != 1:
        raise BindingError("BINDING_SCHEMA_UNSUPPORTED", "registry schema version is unsupported", {"schemaVersion": doc.get("schemaVersion")})
    if not isinstance(doc.get("revision"), int) or isinstance(doc.get("revision"), bool) or doc["revision"] < 0 or not isinstance(doc.get("bindings"), dict):
        raise BindingError("BINDING_REGISTRY_CORRUPT", "registry revision or bindings are invalid")
    if not isinstance(doc.get("updatedAt"), str) or not isinstance(doc.get("migration"), dict) or set(doc["migration"]) != MIGRATION_KEYS:
        raise BindingError("BINDING_REGISTRY_CORRUPT", "registry metadata is invalid")
    if doc["migration"]["legacyScanCompletedAt"] is not None and not isinstance(doc["migration"]["legacyScanCompletedAt"], str):
        raise BindingError("BINDING_REGISTRY_CORRUPT", "migration metadata is invalid")
    for alias, item in doc["bindings"].items():
        normalize_alias(alias)
        required = {"credentialRef", "subjectHash", "createdAt", "updatedAt", "source", "bundleFormat"}
        if not isinstance(item, dict) or set(item) - BINDING_KEYS or not required <= set(item):
            raise BindingError("BINDING_REGISTRY_CORRUPT", "binding has unknown or missing keys", {"alias": alias})
        if not isinstance(item["subjectHash"], str) or not item["subjectHash"].startswith("sha256:"):
            raise BindingError("BINDING_REGISTRY_CORRUPT", "binding identity metadata is invalid", {"alias": alias})
        if item.get("emailHint") is not None and not isinstance(item.get("emailHint"), str):
            raise BindingError("BINDING_REGISTRY_CORRUPT", "binding email hint is invalid", {"alias": alias})
        if not isinstance(item["credentialRef"], str) or not item["credentialRef"] or not isinstance(item.get("externalReference", False), bool):
            raise BindingError("BINDING_REGISTRY_CORRUPT", "binding reference is invalid", {"alias": alias})
        ref = Path(item["credentialRef"])
        if item.get("externalReference"):
            if not ref.is_absolute():
                raise BindingError("BINDING_PATH_UNSAFE", "external binding reference must be absolute", {"alias": alias})
        elif ref.is_absolute() or len(ref.parts) != 2 or ref.parts[0] != "credentials" or not OPAQUE_CREDENTIAL.fullmatch(ref.parts[1]):
            raise BindingError("BINDING_PATH_UNSAFE", "credential reference is not a contained opaque path", {"alias": alias})
    return doc


def _decode_document(raw, *, registry=False):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except BindingError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        code = "BINDING_REGISTRY_CORRUPT" if registry else "AUTH_REQUIRED"
        raise BindingError(code, "registry is malformed" if registry else "credential bundle is malformed or unreadable") from None


def _read_registry(root: Path):
    path = root / "bindings.v1.json"
    if _check_artifact(path, allow_missing=True) is None:
        return empty_registry(), None
    raw, _ = _open_checked(path, max_bytes=MAX_REGISTRY)
    return validate_registry(_decode_document(raw, registry=True)), raw


@contextmanager
def locked_registry(root=None, timeout=LOCK_TIMEOUT):
    root = ensure_root(root)
    root_info = root.lstat()
    lock = root / "bindings.v1.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(lock, flags, 0o600)
    except OSError:
        raise BindingError("BINDING_PATH_UNSAFE", "binding lock is unsafe or unavailable") from None
    acquired = False
    try:
        info = os.fstat(fd)
        _check_info(info)
        if fcntl is None:
            raise BindingError("BINDING_PERMISSION_DENIED", "platform locking semantics are unavailable")
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise BindingError("BINDING_LOCK_TIMEOUT", "binding registry lock timed out")
                time.sleep(0.02)
        current_lock = lock.lstat()
        current_root = root.lstat()
        if (info.st_dev, info.st_ino) != (current_lock.st_dev, current_lock.st_ino) or (root_info.st_dev, root_info.st_ino) != (current_root.st_dev, current_root.st_ino):
            raise BindingError("BINDING_PATH_UNSAFE", "protected storage changed while locking")
        doc, raw = _read_registry(root)
        yield root, doc, raw
    finally:
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(fd)


def _write_exclusive(directory: Path, prefix: str, suffix: str, data: bytes) -> Path:
    for _ in range(100):
        path = directory / (prefix + secrets.token_hex(12) + suffix)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            continue
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            _check_artifact(path)
            return path
        except Exception:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            raise
    raise BindingError("LOCAL_IO_ERROR", "could not allocate a protected temporary file")


def _fsync_directory(path: Path):
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _backup_registry(root: Path, raw: bytes | None):
    if raw is None:
        return
    backup = _write_exclusive(root / "backups", "bindings.v1.%020d-" % time.time_ns(), ".json", raw)
    _fsync_directory(root / "backups")
    backups = sorted((root / "backups").glob("bindings.v1.*.json"), key=lambda p: p.name)
    for stale in backups[:-BACKUP_LIMIT]:
        _check_artifact(stale)
        stale.unlink()
    if len(backups) > BACKUP_LIMIT:
        _fsync_directory(root / "backups")


def _write_registry(root: Path, before, after, raw_before=None, clock=None):
    candidate = json.loads(json.dumps(after))
    candidate["revision"] = before["revision"] + 1
    candidate["updatedAt"] = _now(clock)
    validate_registry(candidate)
    data = (json.dumps(candidate, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    temp = None
    replaced = False
    try:
        _backup_registry(root, raw_before)
        temp = _write_exclusive(root, ".bindings.v1.", ".tmp", data)
        os.replace(temp, root / "bindings.v1.json")
        temp = None
        replaced = True
        _fsync_directory(root)
    except BindingError:
        raise
    except OSError:
        raise BindingError("LOCAL_IO_ERROR", "registry transaction could not be completed durably", committed=replaced) from None
    finally:
        if temp is not None:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass
    return candidate


def _credential_path(root: Path, item, alias=None) -> Path:
    ref = Path(item["credentialRef"])
    if item.get("externalReference"):
        path = ref
    else:
        path = root / ref
        credentials = root / "credentials"
        parent = path.parent.resolve(strict=True)
        if parent != credentials.resolve(strict=True) or not OPAQUE_CREDENTIAL.fullmatch(path.name):
            raise BindingError("BINDING_PATH_UNSAFE", "credential reference escapes protected storage", {"alias": alias})
    _check_artifact(path)
    return path


def _accounts(path: Path):
    raw, _ = _open_checked(path, max_bytes=MAX_CREDENTIAL)
    doc = _decode_document(raw)
    accounts = doc.get("accounts", doc) if isinstance(doc, dict) else None
    if not isinstance(accounts, dict) or not accounts or not all(isinstance(k, str) and isinstance(v, dict) for k, v in accounts.items()):
        raise BindingError("AUTH_REQUIRED", "credential bundle has no valid accounts")
    return accounts


def _identity(account):
    if not isinstance(account, dict):
        raise BindingError("AUTH_REQUIRED", "credential account is malformed")
    subject = account.get("subject_hash") or account.get("subjectHash") or account.get("subject")
    if not isinstance(subject, str) or not subject:
        raise BindingError("AUTH_REQUIRED", "credential account has no stable identity")
    subject_hash = subject if subject.startswith("sha256:") else "sha256:" + hashlib.sha256(subject.encode()).hexdigest()
    email = account.get("email")
    hint = None
    if isinstance(email, str) and "@" in email:
        local, domain = email.rsplit("@", 1)
        hint = (local[:1] or "*") + "***@" + domain
    return subject_hash, hint


def _account_for_subject(accounts, subject_hash, alias):
    matches = [name for name, value in accounts.items() if _identity(value)[0] == subject_hash]
    if len(matches) != 1:
        raise BindingError("BINDING_IDENTITY_MISMATCH", "binding identity does not uniquely match its credential bundle", {"alias": alias})
    return matches[0], accounts[matches[0]]


def resolve_binding(alias=None, root=None):
    with locked_registry(root) as (root, doc, _):
        if alias is not None:
            alias = normalize_alias(alias)
            if alias not in doc["bindings"]:
                raise BindingError("BINDING_NOT_FOUND", "binding alias was not found", {"alias": alias})
        else:
            aliases = sorted(doc["bindings"])
            if not aliases:
                raise BindingError("AUTH_REQUIRED", "no pod-local binding is configured")
            if len(aliases) != 1:
                raise BindingError("ACCOUNT_REQUIRED", "an account alias is required", {"aliases": aliases})
            alias = aliases[0]
        item = doc["bindings"][alias]
        path = _credential_path(root, item, alias)
        bundle_alias, _account = _account_for_subject(_accounts(path), item["subjectHash"], alias)
        return alias, path, bundle_alias, dict(item), doc["revision"]


def list_bindings(root=None, validate_paths=False):
    with locked_registry(root) as (root, doc, _):
        items = []
        for alias, item in sorted(doc["bindings"].items()):
            healthy, check = True, "bindingHealthy"
            if validate_paths:
                try:
                    path = _credential_path(root, item, alias)
                    _account_for_subject(_accounts(path), item["subjectHash"], alias)
                except BindingError as exc:
                    healthy, check = False, exc.code
            items.append({
                "alias": alias, "subjectHash": item["subjectHash"], "emailHint": item.get("emailHint"),
                "source": item["source"], "portable": not item.get("externalReference", False),
                "healthy": healthy, "checkId": check,
            })
        return items, doc["revision"]


def _select_source(source, alias, source_alias=None):
    source = Path(source)
    if not source.is_absolute():
        raise BindingError("BINDING_PATH_UNSAFE", "credential input path must be absolute")
    _check_artifact(source)
    accounts = _accounts(source)
    selected = source_alias or alias
    if selected not in accounts:
        if source_alias is None and len(accounts) == 1:
            selected = next(iter(accounts))
        elif source_alias is None:
            raise BindingError("BINDING_AMBIGUOUS", "sourceAlias is required for a multi-account bundle")
        else:
            raise BindingError("BINDING_NOT_FOUND", "source alias was not found")
    subject, hint = _identity(accounts[selected])
    return source, selected, accounts[selected], subject, hint


def plan_import(alias, source, mode="copy", source_alias=None, overwrite=False, root=None):
    alias = normalize_alias(alias)
    if mode not in ("copy", "reference"):
        raise BindingError("INVALID_ARGUMENT", "mode must be copy or reference")
    source, selected, _, subject, hint = _select_source(source, alias, source_alias)
    if mode == "reference":
        resolved = source.resolve(strict=True)
        repo = Path(__file__).resolve().parents[3]
        replaceable = [repo / "skills", repo / "harnesses", repo / "registry"]
        if any(resolved == base or base in resolved.parents for base in replaceable):
            raise BindingError("BINDING_PATH_UNSAFE", "replaceable package files cannot be referenced")
    with locked_registry(root) as (_, doc, __):
        old = doc["bindings"].get(alias)
        if old and not overwrite:
            raise BindingError("BINDING_CONFLICT", "binding alias already exists", {"alias": alias})
        for existing, item in doc["bindings"].items():
            if existing != alias and item["subjectHash"] == subject:
                raise BindingError("BINDING_CONFLICT", "identity is already bound", {"alias": existing})
        return {
            "operation": "import", "alias": alias, "mode": mode, "sourceAlias": selected,
            "maskedIdentity": hint, "portable": mode == "copy", "replacesBinding": bool(old),
            "revision": doc["revision"],
        }


def import_binding(alias, source, mode="copy", source_alias=None, overwrite=False, root=None, expected_revision=None):
    alias = normalize_alias(alias)
    if mode not in ("copy", "reference"):
        raise BindingError("INVALID_ARGUMENT", "mode must be copy or reference")
    source, selected, account, subject, hint = _select_source(source, alias, source_alias)
    with locked_registry(root) as (root, doc, raw):
        if expected_revision is not None and doc["revision"] != expected_revision:
            raise BindingError("BINDING_CONFLICT", "binding registry changed after preview", {"revision": doc["revision"]})
        old = doc["bindings"].get(alias)
        if old and not overwrite:
            raise BindingError("BINDING_CONFLICT", "binding alias already exists", {"alias": alias})
        for existing, item in doc["bindings"].items():
            if existing != alias and item["subjectHash"] == subject:
                raise BindingError("BINDING_CONFLICT", "identity is already bound", {"alias": existing})
        staged = None
        if mode == "reference":
            resolved = source.resolve(strict=True)
            repo = Path(__file__).resolve().parents[3]
            if any(resolved == base or base in resolved.parents for base in (repo / "skills", repo / "harnesses", repo / "registry")):
                raise BindingError("BINDING_PATH_UNSAFE", "replaceable package files cannot be referenced")
            ref, external = str(resolved), True
        else:
            bundle = (json.dumps({"accounts": {alias: account}}, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
            # Eight fixed random hex characters plus the helper's 24 produces
            # the required 32-character opaque identifier without a rename.
            staged = _write_exclusive(root / "credentials", secrets.token_hex(4), ".json", bundle)
            _fsync_directory(root / "credentials")
            ref, external = "credentials/" + staged.name, False
        stamp = _now()
        item = {
            "credentialRef": ref, "subjectHash": subject,
            "createdAt": old["createdAt"] if old else stamp, "updatedAt": stamp,
            "source": "import", "bundleFormat": 1,
        }
        if hint:
            item["emailHint"] = hint
        if external:
            item["externalReference"] = True
        after = json.loads(json.dumps(doc))
        after["bindings"][alias] = item
        try:
            return _write_registry(root, doc, after, raw)
        except BindingError as exc:
            if staged is not None and not exc.committed:
                try:
                    staged.unlink()
                    _fsync_directory(root / "credentials")
                except OSError:
                    pass
            raise


def register_staged_binding(alias, staged_path, *, source="login", overwrite=False, root=None, expected_revision=None):
    alias = normalize_alias(alias)
    root = ensure_root(root)
    staged = Path(staged_path)
    credentials = root / "credentials"
    if staged.parent.resolve(strict=True) != credentials.resolve(strict=True) or not OPAQUE_CREDENTIAL.fullmatch(staged.name):
        raise BindingError("BINDING_PATH_UNSAFE", "staged credential is outside protected storage")
    accounts = _accounts(staged)
    if alias not in accounts:
        raise BindingError("BINDING_IDENTITY_MISMATCH", "staged credential does not contain the requested alias", {"alias": alias})
    subject, hint = _identity(accounts[alias])
    with locked_registry(root) as (root, doc, raw):
        if expected_revision is not None and doc["revision"] != expected_revision:
            raise BindingError("BINDING_CONFLICT", "binding registry changed after preview", {"revision": doc["revision"]})
        old = doc["bindings"].get(alias)
        if old and not overwrite:
            raise BindingError("BINDING_CONFLICT", "binding alias already exists", {"alias": alias})
        for existing, item in doc["bindings"].items():
            if existing != alias and item["subjectHash"] == subject:
                raise BindingError("BINDING_CONFLICT", "identity is already bound", {"alias": existing})
        stamp = _now()
        item = {
            "credentialRef": "credentials/" + staged.name, "subjectHash": subject,
            "createdAt": old["createdAt"] if old else stamp, "updatedAt": stamp,
            "source": source, "bundleFormat": 1,
        }
        if hint:
            item["emailHint"] = hint
        after = json.loads(json.dumps(doc))
        after["bindings"][alias] = item
        return _write_registry(root, doc, after, raw)


def plan_rename(old_alias, new_alias, root=None):
    old_alias, new_alias = normalize_alias(old_alias), normalize_alias(new_alias)
    with locked_registry(root) as (_, doc, __):
        if old_alias not in doc["bindings"]:
            raise BindingError("BINDING_NOT_FOUND", "binding alias was not found", {"alias": old_alias})
        if new_alias in doc["bindings"]:
            raise BindingError("BINDING_CONFLICT", "destination alias already exists", {"alias": new_alias})
        return {"operation": "rename", "alias": old_alias, "newAlias": new_alias, "identityUnchanged": True, "revision": doc["revision"]}


def rename_binding(old_alias, new_alias, root=None, expected_revision=None):
    old_alias, new_alias = normalize_alias(old_alias), normalize_alias(new_alias)
    with locked_registry(root) as (root, doc, raw):
        if expected_revision is not None and doc["revision"] != expected_revision:
            raise BindingError("BINDING_CONFLICT", "binding registry changed after preview", {"revision": doc["revision"]})
        if old_alias not in doc["bindings"]:
            raise BindingError("BINDING_NOT_FOUND", "binding alias was not found", {"alias": old_alias})
        if new_alias in doc["bindings"]:
            raise BindingError("BINDING_CONFLICT", "destination alias already exists", {"alias": new_alias})
        after = json.loads(json.dumps(doc))
        item = after["bindings"].pop(old_alias)
        item["updatedAt"] = _now()
        after["bindings"][new_alias] = item
        return _write_registry(root, doc, after, raw)


def plan_remove(alias, delete_credential=False, root=None):
    alias = normalize_alias(alias)
    with locked_registry(root) as (_, doc, __):
        if alias not in doc["bindings"]:
            raise BindingError("BINDING_NOT_FOUND", "binding alias was not found", {"alias": alias})
        item = doc["bindings"][alias]
        if delete_credential:
            if item.get("externalReference"):
                raise BindingError("BINDING_PATH_UNSAFE", "external credentials cannot be deleted")
            if any(name != alias and other["credentialRef"] == item["credentialRef"] for name, other in doc["bindings"].items()):
                raise BindingError("BINDING_CONFLICT", "credential is still referenced")
        return {
            "operation": "remove", "alias": alias, "deleteCredential": bool(delete_credential),
            "recoverability": "permanent" if delete_credential else "metadata-backup",
            "revision": doc["revision"],
        }


def remove_binding(alias, delete_credential=False, root=None, expected_revision=None):
    alias = normalize_alias(alias)
    with locked_registry(root) as (root, doc, raw):
        if expected_revision is not None and doc["revision"] != expected_revision:
            raise BindingError("BINDING_CONFLICT", "binding registry changed after preview", {"revision": doc["revision"]})
        if alias not in doc["bindings"]:
            raise BindingError("BINDING_NOT_FOUND", "binding alias was not found", {"alias": alias})
        item = doc["bindings"][alias]
        credential = tombstone = None
        if delete_credential:
            if item.get("externalReference"):
                raise BindingError("BINDING_PATH_UNSAFE", "external credentials cannot be deleted")
            if any(name != alias and other["credentialRef"] == item["credentialRef"] for name, other in doc["bindings"].items()):
                raise BindingError("BINDING_CONFLICT", "credential is still referenced")
            credential = _credential_path(root, item, alias)
            tombstone = credential.with_name("." + credential.name + ".delete-" + secrets.token_hex(8))
            os.replace(credential, tombstone)
            _fsync_directory(root / "credentials")
        after = json.loads(json.dumps(doc))
        after["bindings"].pop(alias)
        try:
            result = _write_registry(root, doc, after, raw)
        except BindingError as exc:
            if tombstone is not None and not exc.committed:
                try:
                    os.replace(tombstone, credential)
                    _fsync_directory(root / "credentials")
                except OSError:
                    raise BindingError("LOCAL_IO_ERROR", "credential deletion rollback failed safely closed") from None
            elif tombstone is not None and exc.committed:
                try:
                    tombstone.unlink()
                    _fsync_directory(root / "credentials")
                except OSError:
                    pass
            raise
        if tombstone is not None:
            try:
                tombstone.unlink()
                _fsync_directory(root / "credentials")
            except OSError:
                # Registry integrity is already committed; guarded orphan cleanup is separate.
                pass
        return result


def mark_migration_completed(root=None):
    with locked_registry(root) as (root, doc, raw):
        if doc["migration"]["legacyScanCompletedAt"] is not None:
            return doc
        after = json.loads(json.dumps(doc))
        after["migration"]["legacyScanCompletedAt"] = _now()
        return _write_registry(root, doc, after, raw)


def restore_registry_backup(name, root=None):
    """Restore validated metadata only; credential contents are never rolled back."""
    if not isinstance(name, str) or not BACKUP_NAME.fullmatch(name):
        raise BindingError("BINDING_PATH_UNSAFE", "backup identifier is invalid")
    with locked_registry(root) as (root, current, raw_current):
        raw, _ = _open_checked(root / "backups" / name, max_bytes=MAX_REGISTRY)
        backup = validate_registry(_decode_document(raw, registry=True))
        if backup["revision"] >= current["revision"]:
            raise BindingError("BINDING_CONFLICT", "backup revision is not older than the current registry")
        for alias, item in backup["bindings"].items():
            path = _credential_path(root, item, alias)
            _account_for_subject(_accounts(path), item["subjectHash"], alias)
        after = json.loads(json.dumps(backup))
        # _write_registry derives the monotonic revision from current.
        return _write_registry(root, current, after, raw_current)


def restore_registry_backup(backup_name, root=None):
    """Restore validated metadata only; credential bytes are never rolled back."""
    if not isinstance(backup_name, str) or not re.fullmatch(r"bindings\.v1\.\d{20}-[a-f0-9]{24}\.json", backup_name):
        raise BindingError("BINDING_PATH_UNSAFE", "backup name is invalid")
    with locked_registry(root) as (root, current, raw):
        backup = root / "backups" / backup_name
        data, _ = _open_checked(backup, max_bytes=MAX_REGISTRY)
        candidate = _decode_document(data)
        validate_registry(candidate)
        if candidate["revision"] >= current["revision"]:
            raise BindingError("BINDING_CONFLICT", "backup revision is not older than the active registry")
        for alias, item in candidate["bindings"].items():
            path = _credential_path(root, item, alias)
            _account_for_subject(_accounts(path), item["subjectHash"], alias)
        return _write_registry(root, current, candidate, raw)
