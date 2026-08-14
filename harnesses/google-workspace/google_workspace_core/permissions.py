"""Metadata-only diagnostics and snapshot-bound protected-root repair."""
from __future__ import annotations

import os
import stat
import json
from pathlib import Path

from .bindings import BindingError, MAX_REGISTRY, binding_root, validate_registry


DIRECTORIES = (("root", Path(".")), ("credentialsDirectory", Path("credentials")),
               ("backupsDirectory", Path("backups")))
FILES = (("registry", Path("bindings.v1.json"), True),
         ("lock", Path("bindings.v1.lock"), True))


def _owned(info):
    return not hasattr(os, "geteuid") or info.st_uid == os.geteuid()


def _mode(info):
    return stat.S_IMODE(info.st_mode)


def _kind(info):
    if stat.S_ISLNK(info.st_mode):
        return "symlink"
    if stat.S_ISDIR(info.st_mode):
        return "directory"
    if stat.S_ISREG(info.st_mode):
        return "file"
    return "unsupported"


def _snapshot(info):
    return {"device": info.st_dev, "inode": info.st_ino, "uid": info.st_uid,
            "type": _kind(info), "linkCount": info.st_nlink, "mode": oct(_mode(info))}


def _same_snapshot(info, snapshot):
    return _snapshot(info) == snapshot


def _root_and_parents(root):
    """Validate lexical/resolved containment and snapshot the trusted chain.

    The protected root itself is the private boundary that repair establishes.
    An exact owned ``workspace`` 02777 ancestor is the sole non-sticky shared
    Forge exception and is never returned as a repair target.
    """
    root = Path(root)
    if not root.is_absolute() or Path(os.path.abspath(root)) != root:
        raise BindingError("BINDING_PATH_UNSAFE", "binding root must be an absolute normalized path")
    chain = []
    current = Path(root.anchor)
    for part in root.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except OSError:
            raise BindingError("BINDING_PATH_UNSAFE", "protected path is unavailable") from None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise BindingError("BINDING_PATH_UNSAFE", "protected path contains an unsafe parent")
        if current != root and info.st_mode & 0o022:
            forge = current.name == "workspace" and _mode(info) == 0o2777
            sticky = bool(info.st_mode & stat.S_ISVTX)
            trusted = info.st_uid in ({os.geteuid(), 0} if hasattr(os, "geteuid") else {info.st_uid})
            if not trusted or not (sticky or forge):
                raise BindingError("BINDING_PATH_UNSAFE", "protected parent is writable by another user")
        chain.append((current, _snapshot(info)))
    root_info = chain[-1][1]
    if root_info["type"] != "directory" or not _owned(root.lstat()):
        raise BindingError("BINDING_PERMISSION_DENIED", "protected root has an unsafe type or owner")
    try:
        if root.resolve(strict=True) != root:
            raise BindingError("BINDING_PATH_UNSAFE", "protected root resolves outside its lexical location")
    except OSError:
        raise BindingError("BINDING_PATH_UNSAFE", "protected root cannot be resolved safely") from None
    return chain


def _verify_chain(chain):
    for path, snapshot in chain:
        try:
            info = path.lstat()
        except OSError:
            raise BindingError("BINDING_PATH_UNSAFE", "protected parent changed after preview") from None
        if not _same_snapshot(info, snapshot):
            raise BindingError("BINDING_PATH_UNSAFE", "protected parent changed after preview")


def _discover(root):
    root = Path(root)
    chain = _root_and_parents(root)
    artifacts = []
    for category, relative in DIRECTORIES:
        artifacts.append((category, relative, True, False))
    for category, relative, optional in FILES:
        artifacts.append((category, relative, False, optional))
    for directory, category in ((Path("credentials"), "credentialFile"),
                                (Path("backups"), "backupFile")):
        parent = root / directory
        directory_fd = None
        try:
            before = parent.lstat()
            if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
                entries = []
            else:
                flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
                flags |= getattr(os, "O_DIRECTORY", 0)
                directory_fd = os.open(parent, flags)
                if not _same_snapshot(os.fstat(directory_fd), _snapshot(before)):
                    raise BindingError("BINDING_PATH_UNSAFE", "protected directory changed during discovery")
                entries = sorted(os.scandir(directory_fd), key=lambda item: item.name)
        except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
            entries = []
        finally:
            if directory_fd is not None:
                os.close(directory_fd)
        for entry in entries:
            artifacts.append((category, directory / entry.name, False, False))

    checks = []
    targets = []
    blocked = []
    for number, (category, relative, directory, optional) in enumerate(artifacts, 1):
        artifact_id = f"artifact-{number:04d}"
        path = root if relative == Path(".") else root / relative
        # Relative names originate only from fixed direct scandir entries.
        if path != root and path.parent != root and path.parent not in (root / "credentials", root / "backups"):
            raise BindingError("BINDING_PATH_UNSAFE", "artifact escaped protected-root containment")
        try:
            info = path.lstat()
        except FileNotFoundError:
            check = {"checkId": category + "Present", "artifactId": artifact_id,
                     "passed": bool(optional), "repairAvailable": False}
            checks.append(check)
            if not optional:
                blocked.append(check["checkId"])
            continue
        expected = 0o700 if directory else 0o600
        kind = _kind(info)
        right_type = kind == ("directory" if directory else "file")
        owner = _owned(info)
        one_link = directory or os.name == "nt" or info.st_nlink == 1
        current_mode = _mode(info)
        passed = right_type and owner and one_link and (os.name == "nt" or current_mode == expected)
        repairable = os.name != "nt" and right_type and owner and one_link
        check = {"checkId": category + "Permissions", "artifactId": artifact_id,
                 "passed": passed, "repairAvailable": repairable,
                 "currentMode": oct(current_mode), "intendedMode": oct(expected), "type": kind}
        checks.append(check)
        if not passed:
            if repairable:
                targets.append((artifact_id, path, info, expected))
            else:
                blocked.append(check["checkId"])
    return chain, checks, targets, sorted(set(blocked))


def _reject_external_references(root):
    """Inspect registry metadata only; credential references are never opened."""
    path = Path(root) / "bindings.v1.json"
    try:
        before = path.lstat()
    except FileNotFoundError:
        return
    if _kind(before) != "file" or not _owned(before) or before.st_nlink != 1 or before.st_size > MAX_REGISTRY:
        raise BindingError("BINDING_PERMISSION_DENIED", "binding registry is unsafe for repair planning")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        raise BindingError("BINDING_PATH_UNSAFE", "binding registry could not be inspected safely") from None
    try:
        if not _same_snapshot(os.fstat(fd), _snapshot(before)):
            raise BindingError("BINDING_PATH_UNSAFE", "binding registry changed during repair planning")
        raw = b""
        while len(raw) <= MAX_REGISTRY:
            chunk = os.read(fd, min(65536, MAX_REGISTRY + 1 - len(raw)))
            if not chunk:
                break
            raw += chunk
        if len(raw) > MAX_REGISTRY:
            raise BindingError("BINDING_REGISTRY_CORRUPT", "binding registry exceeds its size limit")
        try:
            doc = validate_registry(json.loads(raw.decode("utf-8")))
        except BindingError:
            raise
        except (UnicodeError, ValueError, RecursionError):
            raise BindingError("BINDING_REGISTRY_CORRUPT", "binding registry is malformed") from None
        if any(item.get("externalReference") for item in doc["bindings"].values()):
            raise BindingError("BINDING_PATH_UNSAFE", "external credential references cannot be permission-repaired")
        if not _same_snapshot(os.fstat(fd), _snapshot(before)):
            raise BindingError("BINDING_PATH_UNSAFE", "binding registry changed during repair planning")
    finally:
        os.close(fd)


def check_permissions(root=None):
    root = Path(root) if root is not None else binding_root()
    try:
        chain, checks, _targets, blocked = _discover(root)
        parent = {"checkId": "parentTrust", "passed": not blocked,
                  "repairAvailable": False, "artifactId": "artifact-parent",
                  "currentMode": None, "intendedMode": None, "type": "parent-chain"}
        return [parent, *checks]
    except BindingError as error:
        return [{"checkId": "parentTrust", "passed": False, "repairAvailable": False,
                 "artifactId": "artifact-parent", "currentMode": None,
                 "intendedMode": None, "type": "parent-chain", "reasonCode": error.code}]


def plan_repair(root=None):
    root = Path(root) if root is not None else binding_root()
    chain, _checks, targets, blocked = _discover(root)
    if blocked:
        raise BindingError("BINDING_PERMISSION_DENIED",
                           "permission repair cannot safely address every defect",
                           {"checkIds": blocked})
    _reject_external_references(root)
    changes = [{"artifactId": artifact_id, "beforeMode": oct(_mode(info)),
                "afterMode": oct(expected), "type": _kind(info),
                "snapshot": _snapshot(info)}
               for artifact_id, _path, info, expected in targets]
    return {"operation": "permissions.repair",
            "rootIdentity": {"device": chain[-1][1]["device"], "inode": chain[-1][1]["inode"]},
            "parentSnapshots": [{"artifactId": f"parent-{number:04d}", "snapshot": snapshot}
                                for number, (_path, snapshot) in enumerate(chain, 1)],
            "changes": changes, "intendedDirectoryMode": "0o700", "intendedFileMode": "0o600"}


def repair_permissions(root=None, expected_plan=None):
    root = Path(root) if root is not None else binding_root()
    chain, _checks, targets, blocked = _discover(root)
    if blocked:
        raise BindingError("BINDING_PERMISSION_DENIED", "permission repair refused an unsafe artifact",
                           {"checkIds": blocked})
    _reject_external_references(root)
    current_plan = {"operation": "permissions.repair",
                    "rootIdentity": {"device": chain[-1][1]["device"], "inode": chain[-1][1]["inode"]},
                    "parentSnapshots": [{"artifactId": f"parent-{number:04d}", "snapshot": snapshot}
                                        for number, (_path, snapshot) in enumerate(chain, 1)],
                    "changes": [{"artifactId": aid, "beforeMode": oct(_mode(info)),
                                 "afterMode": oct(mode), "type": _kind(info), "snapshot": _snapshot(info)}
                                for aid, _path, info, mode in targets],
                    "intendedDirectoryMode": "0o700", "intendedFileMode": "0o600"}
    if expected_plan is not None and current_plan != expected_plan:
        raise BindingError("BINDING_PATH_UNSAFE", "permission repair preview is stale")
    if not targets:
        return [], current_plan
    if os.name == "nt" or not hasattr(os, "fchmod") or not hasattr(os, "O_NOFOLLOW"):
        raise BindingError("BINDING_PERMISSION_DENIED", "safe no-follow permission repair is unavailable")

    opened = []
    try:
        # Open and validate every exact inode before the first mutation.
        for artifact_id, path, before, expected in targets:
            flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
            if stat.S_ISDIR(before.st_mode):
                flags |= getattr(os, "O_DIRECTORY", 0)
            try:
                fd = os.open(path, flags)
            except OSError:
                raise BindingError("BINDING_PATH_UNSAFE", "repair target could not be reopened safely") from None
            opened.append((artifact_id, fd, expected, _snapshot(before)))
            if not _same_snapshot(os.fstat(fd), _snapshot(before)):
                raise BindingError("BINDING_PATH_UNSAFE", "repair target changed after preview")
        _verify_chain(chain)
        changed = []
        try:
            for _artifact_id, fd, expected, before in opened:
                os.fchmod(fd, expected)
                changed.append((fd, int(before["mode"], 8)))
            for _artifact_id, fd, expected, before in opened:
                after = os.fstat(fd)
                invariant = dict(before, mode=oct(expected))
                if not _same_snapshot(after, invariant):
                    raise BindingError("BINDING_PATH_UNSAFE", "repair target changed during permission repair")
            _verify_chain([(path, dict(snapshot, mode=(oct(0o700) if path == root else snapshot["mode"])))
                           for path, snapshot in chain])
        except Exception:
            # Best-effort transactional rollback on the already-open exact inodes.
            for fd, original_mode in reversed(changed):
                try:
                    os.fchmod(fd, original_mode)
                except OSError:
                    pass
            raise
    finally:
        for _artifact_id, fd, _expected, _before in opened:
            os.close(fd)
    repaired = sorted({"directory" if change[3] == 0o700 else "file" for change in targets})
    return repaired, current_plan
