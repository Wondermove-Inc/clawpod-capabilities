"""Sanitized permission diagnostics and conservative protected-root repair."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from .bindings import BindingError, binding_root, validate_registry


def _owned(info):
    return not hasattr(os, "geteuid") or info.st_uid == os.geteuid()


def _artifact_check(category, path, directory, *, optional=False, external=False):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"checkId": category + "Present", "passed": bool(optional), "repairAvailable": False}
    expected = 0o700 if directory else 0o600
    proper_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    owned = _owned(info)
    private = os.name == "nt" or stat.S_IMODE(info.st_mode) == expected
    one_link = directory or os.name == "nt" or info.st_nlink == 1
    safe = proper_type and not stat.S_ISLNK(info.st_mode) and owned and private and one_link
    return {
        "checkId": category + "Permissions", "passed": safe,
        "repairAvailable": bool(not external and proper_type and not stat.S_ISLNK(info.st_mode) and owned and one_link),
        "intendedMode": oct(expected),
    }


def check_permissions(root=None):
    root = Path(root) if root is not None else binding_root()
    checks = []
    parent_safe = True
    current = Path(root.anchor)
    for part in root.parts[1:-1]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX):
            parent_safe = False
            break
    checks.append({"checkId": "parentTrust", "passed": parent_safe, "repairAvailable": False})
    checks.extend([
        _artifact_check("root", root, True),
        _artifact_check("credentialsDirectory", root / "credentials", True),
        _artifact_check("backupsDirectory", root / "backups", True),
        _artifact_check("registry", root / "bindings.v1.json", False, optional=True),
        _artifact_check("lock", root / "bindings.v1.lock", False, optional=True),
    ])
    credentials = root / "credentials"
    try:
        entries = list(credentials.iterdir()) if credentials.is_dir() and not credentials.is_symlink() else []
    except OSError:
        entries = []
    for path in sorted(entries, key=lambda p: p.name):
        checks.append(_artifact_check("credentialFile", path, False))
    backups = root / "backups"
    try:
        backup_entries = list(backups.iterdir()) if backups.is_dir() and not backups.is_symlink() else []
    except OSError:
        backup_entries = []
    for path in sorted(backup_entries, key=lambda p: p.name):
        checks.append(_artifact_check("backupFile", path, False))
    registry = root / "bindings.v1.json"
    try:
        info = registry.lstat()
        if stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode) and info.st_size <= 1024 * 1024:
            doc = validate_registry(json.loads(registry.read_text(encoding="utf-8")))
            for item in doc["bindings"].values():
                if item.get("externalReference"):
                    checks.append({"checkId": "externalReferencePortable", "passed": False, "repairAvailable": False})
    except Exception:
        # Registry shape is reported by status; permission checks never echo parse errors.
        pass
    return checks


def plan_repair(root=None):
    checks = check_permissions(root)
    repairable = sorted({item["checkId"] for item in checks if not item["passed"] and item.get("repairAvailable")})
    blocked = sorted({item["checkId"] for item in checks if not item["passed"] and not item.get("repairAvailable")})
    if blocked:
        raise BindingError("BINDING_PERMISSION_DENIED", "permission repair cannot safely address every defect", {"checkIds": blocked})
    return {"operation": "permissions.repair", "artifactCategories": repairable, "intendedDirectoryMode": "0o700", "intendedFileMode": "0o600"}


def repair_permissions(root=None):
    root = Path(root) if root is not None else binding_root()
    plan = plan_repair(root)
    if not root.exists():
        raise BindingError("BINDING_PATH_UNSAFE", "binding root does not exist")
    candidates = [root, root / "credentials", root / "backups", root / "bindings.v1.json", root / "bindings.v1.lock"]
    credentials = root / "credentials"
    if credentials.is_dir() and not credentials.is_symlink():
        candidates.extend(credentials.iterdir())
    backups = root / "backups"
    if backups.is_dir() and not backups.is_symlink():
        candidates.extend(backups.iterdir())
    repaired = []
    for path in candidates:
        try:
            before = path.lstat()
        except FileNotFoundError:
            continue
        directory = stat.S_ISDIR(before.st_mode)
        regular = directory or stat.S_ISREG(before.st_mode)
        if stat.S_ISLNK(before.st_mode) or not regular or not _owned(before) or (not directory and os.name != "nt" and before.st_nlink != 1):
            raise BindingError("BINDING_PERMISSION_DENIED", "permission repair refused an unsafe or unowned artifact")
        current = path.lstat()
        if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
            raise BindingError("BINDING_PATH_UNSAFE", "artifact changed during permission repair")
        expected = 0o700 if directory else 0o600
        if os.name == "nt":  # pragma: no cover - fail closed until the ACL adapter is available
            raise BindingError("BINDING_PERMISSION_DENIED", "Windows ACL repair is unavailable on this runtime")
        os.chmod(path, expected, follow_symlinks=False)
        after = path.lstat()
        if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino) or stat.S_IMODE(after.st_mode) != expected:
            raise BindingError("BINDING_PATH_UNSAFE", "artifact changed during permission repair")
        repaired.append("directory" if directory else "file")
    return sorted(set(repaired)), plan
