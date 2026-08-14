"""Metadata-only diagnostics and snapshot-bound protected-root repair."""
from __future__ import annotations

import os
import stat
from pathlib import Path

from .bindings import BindingError, binding_root


DIRECTORIES = (("root", Path("."), False),
               ("credentialsDirectory", Path("credentials"), True),
               ("backupsDirectory", Path("backups"), True))
FILES = (("registry", Path("bindings.v1.json"), True),
         ("lock", Path("bindings.v1.lock"), True))


def _owned(info):
    return not hasattr(os, "geteuid") or info.st_uid == os.geteuid()


def _process_group(info):
    return not hasattr(os, "getegid") or info.st_gid == os.getegid()


def _process_owner(snapshot):
    return snapshot["uid"] == (os.geteuid() if hasattr(os, "geteuid") else snapshot["uid"])


def _trusted_identity(snapshot):
    return _process_owner(snapshot) and (not hasattr(os, "getegid") or snapshot["gid"] == os.getegid())


def _exact_forge_location(paths):
    expected = tuple(Path("/root/.local/state/openclaw/google-workspace").parents)[::-1][1:]
    return tuple(paths) == expected + (Path("/root/.local/state/openclaw/google-workspace"),)


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
    return {"device": info.st_dev, "inode": info.st_ino, "uid": info.st_uid, "gid": info.st_gid,
            "type": _kind(info), "linkCount": info.st_nlink, "mode": oct(_mode(info))}


def _same_snapshot(info, snapshot):
    return _snapshot(info) == snapshot


def _root_and_parents(root):
    """Validate lexical/resolved containment and snapshot the trusted chain.

    The sole non-sticky shared exception is the complete observed Forge suffix:
    root 02777, .local/state/openclaw 02775, and google-workspace 02770.
    Every member must be process UID/GID owned. No prefix or partial suffix is
    trusted. Exact process-owned 01777 remains the generic sticky-parent case.
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
        chain.append((current, _snapshot(info)))
    suffix_names = ("root", ".local", "state", "openclaw", "google-workspace")
    suffix_modes = (0o2777, 0o2775, 0o2775, 0o2775)
    forge_start = len(chain) - len(suffix_names)
    forge_paths = [path for path, _snapshot_value in chain[forge_start:]] if forge_start >= 0 else []
    forge_gid = chain[forge_start][1]["gid"] if forge_start >= 0 else None
    exact_forge = forge_start >= 0 and _exact_forge_location(forge_paths) and all(
        path.name == name and _process_owner(snapshot) and snapshot["gid"] == forge_gid
        and (int(snapshot["mode"], 8) == mode if name != "google-workspace"
             else int(snapshot["mode"], 8) in (0o2770, 0o700))
        for (path, snapshot), name, mode in zip(chain[forge_start:], suffix_names, (*suffix_modes, 0o2770))
    )
    for number, (_path, snapshot) in enumerate(chain[:-1]):
        if int(snapshot["mode"], 8) & 0o022:
            in_forge_suffix = exact_forge and number >= forge_start
            exact_sticky = int(snapshot["mode"], 8) == 0o1777 and _trusted_identity(snapshot)
            if not in_forge_suffix and not exact_sticky:
                raise BindingError("BINDING_PATH_UNSAFE", "protected parent is writable by another user")
    root_info = chain[-1][1]
    root_group_ok = root_info["gid"] == forge_gid if exact_forge else _process_group(root.lstat())
    if root_info["type"] != "directory" or not _owned(root.lstat()) or not root_group_ok:
        raise BindingError("BINDING_PERMISSION_DENIED", "protected root has an unsafe type or owner")
    shared_ancestors = [snapshot for path, snapshot in chain[:-1]
                        if int(snapshot["mode"], 8) & 0o022]
    if shared_ancestors:
        descendants = chain[chain.index(next(item for item in chain[:-1]
                                            if int(item[1]["mode"], 8) & 0o022)) + 1:]
        private_boundary = any(snapshot["uid"] == root_info["uid"]
                               and not int(snapshot["mode"], 8) & 0o022
                               for _path, snapshot in descendants)
        pending_boundary = exact_forge
        if not private_boundary and not pending_boundary:
            raise BindingError("BINDING_PATH_UNSAFE", "shared parent lacks an exact protected containment boundary")
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


def _verify_targets(targets):
    for _artifact_id, path, before, _expected in targets:
        try:
            current = path.lstat()
        except OSError:
            raise BindingError("BINDING_PATH_UNSAFE", "repair target changed during validation") from None
        if not _same_snapshot(current, _snapshot(before)):
            raise BindingError("BINDING_PATH_UNSAFE", "repair target changed during validation")


def _verify_absent(absent):
    for _artifact_id, path in absent:
        try:
            path.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise BindingError("BINDING_PATH_UNSAFE", "absent artifact changed during validation") from None
        raise BindingError("BINDING_PATH_UNSAFE", "absent artifact appeared during validation")


def _discover(root):
    root = Path(root)
    chain = _root_and_parents(root)
    artifacts = []
    for category, relative, optional in DIRECTORIES:
        artifacts.append((category, relative, True, optional))
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
    absent = []
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
                     "passed": bool(optional), "repairAvailable": False,
                     "present": False, "applicable": not optional}
            checks.append(check)
            if optional:
                absent.append((artifact_id, path))
            if not optional:
                blocked.append(check["checkId"])
            continue
        expected = 0o700 if directory else 0o600
        kind = _kind(info)
        right_type = kind == ("directory" if directory else "file")
        expected_gid = chain[-1][1]["gid"]
        owner = _owned(info) and info.st_gid == expected_gid
        one_link = directory or os.name == "nt" or info.st_nlink == 1
        current_mode = _mode(info)
        passed = right_type and owner and one_link and (os.name == "nt" or current_mode == expected)
        repairable = os.name != "nt" and right_type and owner and one_link
        check = {"checkId": category + "Permissions", "artifactId": artifact_id,
                 "passed": passed, "repairAvailable": repairable,
                 "present": True, "applicable": True,
                 "currentMode": oct(current_mode), "intendedMode": oct(expected), "type": kind}
        checks.append(check)
        if not passed:
            if repairable:
                targets.append((artifact_id, path, info, expected))
            else:
                blocked.append(check["checkId"])
    _verify_chain(chain)
    _verify_targets(targets)
    _verify_absent(absent)
    return chain, checks, targets, absent, sorted(set(blocked))


def check_permissions(root=None):
    root = Path(root) if root is not None else binding_root()
    try:
        chain, checks, _targets, _absent, _blocked = _discover(root)
        parent = {"checkId": "parentTrust", "passed": True,
                  "repairAvailable": False, "artifactId": "artifact-parent",
                  "currentMode": None, "intendedMode": None, "type": "parent-chain"}
        return [parent, *checks]
    except BindingError as error:
        return [{"checkId": "parentTrust", "passed": False, "repairAvailable": False,
                 "artifactId": "artifact-parent", "currentMode": None,
                 "intendedMode": None, "type": "parent-chain", "reasonCode": error.code}]


def plan_repair(root=None):
    root = Path(root) if root is not None else binding_root()
    chain, _checks, targets, absent, blocked = _discover(root)
    if blocked:
        raise BindingError("BINDING_PERMISSION_DENIED",
                           "permission repair cannot safely address every defect",
                           {"checkIds": blocked})
    changes = [{"artifactId": artifact_id, "beforeMode": oct(_mode(info)),
                "afterMode": oct(expected), "type": _kind(info),
                "snapshot": _snapshot(info)}
               for artifact_id, _path, info, expected in targets]
    return {"operation": "permissions.repair",
            "rootIdentity": {"device": chain[-1][1]["device"], "inode": chain[-1][1]["inode"]},
            "parentSnapshots": [{"artifactId": f"parent-{number:04d}", "snapshot": snapshot}
                                for number, (_path, snapshot) in enumerate(chain, 1)],
            "absentArtifacts": [{"artifactId": artifact_id, "snapshot": {"type": "absent"}}
                                for artifact_id, _path in absent],
            "changes": changes, "intendedDirectoryMode": "0o700", "intendedFileMode": "0o600"}


def repair_permissions(root=None, expected_plan=None):
    root = Path(root) if root is not None else binding_root()
    chain, _checks, targets, absent, blocked = _discover(root)
    if blocked:
        raise BindingError("BINDING_PERMISSION_DENIED", "permission repair refused an unsafe artifact",
                           {"checkIds": blocked})
    current_plan = {"operation": "permissions.repair",
                    "rootIdentity": {"device": chain[-1][1]["device"], "inode": chain[-1][1]["inode"]},
                    "parentSnapshots": [{"artifactId": f"parent-{number:04d}", "snapshot": snapshot}
                                        for number, (_path, snapshot) in enumerate(chain, 1)],
                    "absentArtifacts": [{"artifactId": artifact_id, "snapshot": {"type": "absent"}}
                                        for artifact_id, _path in absent],
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
            opened.append((artifact_id, path, fd, expected, _snapshot(before)))
            if not _same_snapshot(os.fstat(fd), _snapshot(before)):
                raise BindingError("BINDING_PATH_UNSAFE", "repair target changed after preview")
        _verify_chain(chain)
        _verify_absent(absent)
        for _artifact_id, path, fd, _expected, before in opened:
            try:
                current = path.lstat()
            except OSError:
                raise BindingError("BINDING_PATH_UNSAFE", "repair target changed after preview") from None
            if not _same_snapshot(current, before) or not _same_snapshot(os.fstat(fd), before):
                raise BindingError("BINDING_PATH_UNSAFE", "repair target changed after preview")
        changed = []
        try:
            for _artifact_id, _path, fd, expected, before in opened:
                os.fchmod(fd, expected)
                changed.append((fd, int(before["mode"], 8)))
            for _artifact_id, path, fd, expected, before in opened:
                after = os.fstat(fd)
                invariant = dict(before, mode=oct(expected))
                try:
                    current = path.lstat()
                except OSError:
                    raise BindingError("BINDING_PATH_UNSAFE", "repair target changed during permission repair") from None
                if not _same_snapshot(after, invariant) or not _same_snapshot(current, invariant):
                    raise BindingError("BINDING_PATH_UNSAFE", "repair target changed during permission repair")
            _verify_absent(absent)
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
        for _artifact_id, _path, fd, _expected, _before in opened:
            os.close(fd)
    repaired = sorted({"directory" if change[3] == 0o700 else "file" for change in targets})
    return repaired, current_plan
