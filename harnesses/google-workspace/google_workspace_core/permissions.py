"""Metadata-only diagnostics and snapshot-bound protected-root repair."""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path

from .bindings import BindingError, binding_root


DIRECTORIES = (("root", Path("."), False),
               ("credentialsDirectory", Path("credentials"), True),
               ("backupsDirectory", Path("backups"), True))
FILES = (("registry", Path("bindings.v1.json"), True),
         ("lock", Path("bindings.v1.lock"), True))

CREDENTIAL_NAME = re.compile(r"^[a-f0-9]{32}\.json$")
CREDENTIAL_TOMBSTONE = re.compile(r"^\.[a-f0-9]{32}\.json\.delete-[a-f0-9]{16}$")
BACKUP_NAME = re.compile(r"^bindings\.v1\.\d{20}-[a-f0-9]{24}\.json$")
REGISTRY_TEMP = re.compile(r"^\.bindings\.v1\.[a-f0-9]{24}\.tmp$")


def _owned(info):
    return not hasattr(os, "geteuid") or info.st_uid == os.geteuid()


def _process_group(info):
    return not hasattr(os, "getegid") or info.st_gid == os.getegid()


def _process_owner(snapshot):
    return snapshot["uid"] == (os.geteuid() if hasattr(os, "geteuid") else snapshot["uid"])


def _trusted_identity(snapshot):
    return _process_owner(snapshot) and (not hasattr(os, "getegid") or snapshot["gid"] == os.getegid())


def _exact_forge_location(paths):
    paths = tuple(paths)
    root = Path("/root/.local/state/openclaw/google-workspace")
    root_chain = tuple(root.parents)[::-1][1:] + (root,)
    workspace_boundary = (len(paths) == 2 and paths[0] == Path("/workspace")
                          and paths[1].parent == paths[0])
    return paths == root_chain or workspace_boundary


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


def _root_and_parents(root, *, allow_absent=False):
    """Validate lexical/resolved containment and snapshot the trusted chain.

    The existing /root exception is its complete named Forge chain.  The
    separate /workspace exception is only the 02777 ancestor plus its immediate
    process-owned private protected root.  Both pin one uniform chain GID.
    """
    root = Path(root)
    if not root.is_absolute() or Path(os.path.abspath(root)) != root:
        raise BindingError("BINDING_PATH_UNSAFE", "binding root must be an absolute normalized path")
    chain = []
    current = Path(root.anchor)
    parts = root.parts[1:] if not allow_absent else root.parts[1:-1]
    for part in parts:
        current /= part
        try:
            info = current.lstat()
        except OSError:
            raise BindingError("BINDING_PATH_UNSAFE", "protected path is unavailable") from None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise BindingError("BINDING_PATH_UNSAFE", "protected path contains an unsafe parent")
        snapshot = _snapshot(info)
        if snapshot["uid"] != info.st_uid or snapshot["gid"] != info.st_gid:
            raise BindingError("BINDING_PATH_UNSAFE", "protected path identity snapshot is inconsistent")
        chain.append((current, snapshot))
    root_names = ("root", ".local", "state", "openclaw", "google-workspace")
    root_modes = (0o2777, 0o2775, 0o2775, 0o2775, 0o2770)
    forge_start = len(chain) - len(root_names)
    forge_paths = [path for path, _snapshot_value in chain[forge_start:]] if forge_start >= 0 else []
    forge_gid = chain[forge_start][1]["gid"] if forge_start >= 0 else None
    legacy_gid = os.getegid() if hasattr(os, "getegid") else forge_gid
    exact_root = forge_start >= 0 and _exact_forge_location(forge_paths) and all(
        path.name == name and _process_owner(snapshot)
        and (snapshot["gid"] == forge_gid
             or (name == "google-workspace" and snapshot["gid"] == legacy_gid
                 and int(snapshot["mode"], 8) == 0o2770))
        and (int(snapshot["mode"], 8) == mode if name != "google-workspace"
             else int(snapshot["mode"], 8) in (0o2770, 0o700))
        for (path, snapshot), name, mode in zip(chain[forge_start:], root_names, root_modes)
    )
    workspace_start = len(chain) - 2
    workspace_paths = [path for path, _snapshot_value in chain[workspace_start:]] \
        if workspace_start >= 0 else []
    workspace_gid = chain[workspace_start][1]["gid"] if workspace_start >= 0 else None
    exact_workspace = workspace_start >= 0 and _exact_forge_location(workspace_paths) \
      and all(_process_owner(snapshot) for _path, snapshot in chain[workspace_start:]) \
      and (chain[workspace_start + 1][1]["gid"] == workspace_gid
           or (chain[workspace_start + 1][1]["gid"] == legacy_gid
               and int(chain[workspace_start + 1][1]["mode"], 8) == 0o2770)) \
      and int(chain[workspace_start][1]["mode"], 8) == 0o2777 \
      and int(chain[workspace_start + 1][1]["mode"], 8) in (0o2770, 0o700)
    exact_forge = exact_root or exact_workspace
    if exact_workspace:
        forge_start = workspace_start
        forge_gid = workspace_gid
    for number, (_path, snapshot) in enumerate(chain[:-1]):
        if int(snapshot["mode"], 8) & 0o022:
            in_forge_suffix = exact_forge and number >= forge_start
            exact_sticky = int(snapshot["mode"], 8) == 0o1777 and _trusted_identity(snapshot)
            if not in_forge_suffix and not exact_sticky:
                raise BindingError("BINDING_PATH_UNSAFE", "protected parent is writable by another user")
    if allow_absent:
        if not chain:
            raise BindingError("BINDING_PATH_UNSAFE", "protected root has no verified parent")
        parent = chain[-1][1]
        if parent["type"] != "directory" or not _process_owner(parent):
            raise BindingError("BINDING_PERMISSION_DENIED", "protected root parent has an unsafe identity")
        return chain
    root_info = chain[-1][1]
    expected_gid = forge_gid if exact_forge else chain[-2][1]["gid"]
    if not _process_owner(chain[-2][1]):
        raise BindingError("BINDING_PERMISSION_DENIED", "protected root parent has an unsafe identity")
    if root_info["type"] != "directory" or not _process_owner(root_info):
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
    return chain, root_info["uid"], expected_gid


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
    try:
        root.lstat()
    except FileNotFoundError:
        chain = _root_and_parents(root, allow_absent=True)
        check = {"checkId": "rootPresent", "artifactId": "artifact-0001", "passed": True,
                 "repairAvailable": False, "present": False, "applicable": False}
        return chain, [check], [], [("artifact-0001", root)], [], \
            chain[-1][1]["uid"], chain[-1][1]["gid"]
    chain, expected_uid, expected_gid = _root_and_parents(root)
    artifacts = []
    for category, relative, optional in DIRECTORIES:
        artifacts.append((category, relative, True, optional))
    for category, relative, optional in FILES:
        artifacts.append((category, relative, False, optional))
    for directory, category, pattern in ((Path("credentials"), "credentialFile", CREDENTIAL_NAME),
                                         (Path("backups"), "backupFile", BACKUP_NAME)):
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
            if pattern.fullmatch(entry.name):
                artifacts.append((category, directory / entry.name, False, False))
            elif directory == Path("credentials") and CREDENTIAL_TOMBSTONE.fullmatch(entry.name):
                artifacts.append(("credentialStagingFile", directory / entry.name, False, False))
            else:
                artifacts.append(("unsafeContent", directory / entry.name, False, False))
    try:
        root_entries = sorted(os.scandir(root), key=lambda item: item.name)
    except OSError:
        raise BindingError("BINDING_PATH_UNSAFE", "protected root could not be enumerated") from None
    fixed = {"credentials", "backups", "bindings.v1.json", "bindings.v1.lock"}
    for entry in root_entries:
        if entry.name not in fixed:
            category = "registryStagingFile" if REGISTRY_TEMP.fullmatch(entry.name) else "unsafeContent"
            artifacts.append((category, Path(entry.name), False, False))

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
        owner = _owned(info) and info.st_uid == expected_uid
        group = info.st_gid == expected_gid
        one_link = directory or os.name == "nt" or info.st_nlink == 1
        current_mode = _mode(info)
        recognized = category != "unsafeContent"
        passed = recognized and right_type and owner and group and one_link and (os.name == "nt" or current_mode == expected)
        repairable = os.name != "nt" and recognized and right_type and owner and one_link
        check = {"checkId": category + "Permissions", "artifactId": artifact_id,
                 "passed": passed, "repairAvailable": repairable,
                 "present": True, "applicable": True,
                 "currentMode": oct(current_mode), "intendedMode": oct(expected), "type": kind,
                 "currentGid": info.st_gid, "intendedGid": expected_gid}
        checks.append(check)
        if not passed:
            if repairable:
                targets.append((artifact_id, path, info, expected))
            else:
                blocked.append(check["checkId"])
    _verify_chain(chain)
    _verify_targets(targets)
    _verify_absent(absent)
    return chain, checks, targets, absent, sorted(set(blocked)), expected_uid, expected_gid


def check_permissions(root=None):
    root = Path(root) if root is not None else binding_root()
    try:
        chain, checks, _targets, _absent, _blocked, _uid, _gid = _discover(root)
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
    chain, _checks, targets, absent, blocked, expected_uid, expected_gid = _discover(root)
    if blocked:
        raise BindingError("BINDING_PERMISSION_DENIED",
                           "permission repair cannot safely address every defect",
                           {"checkIds": blocked})
    changes = [{"artifactId": artifact_id, "beforeMode": oct(_mode(info)),
                "afterMode": oct(expected), "beforeUid": info.st_uid,
                "afterUid": expected_uid, "beforeGid": info.st_gid, "afterGid": expected_gid,
                "type": _kind(info),
                "snapshot": _snapshot(info)}
               for artifact_id, _path, info, expected in targets]
    return {"operation": "permissions.repair",
            "rootIdentity": {"device": chain[-1][1]["device"], "inode": chain[-1][1]["inode"]},
            "expectedIdentity": {"uid": expected_uid, "gid": expected_gid},
            "parentSnapshots": [{"artifactId": f"parent-{number:04d}", "snapshot": snapshot}
                                for number, (_path, snapshot) in enumerate(chain, 1)],
            "absentArtifacts": [{"artifactId": artifact_id, "snapshot": {"type": "absent"}}
                                for artifact_id, _path in absent],
            "changes": changes, "intendedDirectoryMode": "0o700", "intendedFileMode": "0o600"}


def repair_permissions(root=None, expected_plan=None):
    root = Path(root) if root is not None else binding_root()
    chain, _checks, targets, absent, blocked, expected_uid, expected_gid = _discover(root)
    if blocked:
        raise BindingError("BINDING_PERMISSION_DENIED", "permission repair refused an unsafe artifact",
                           {"checkIds": blocked})
    current_plan = {"operation": "permissions.repair",
                    "rootIdentity": {"device": chain[-1][1]["device"], "inode": chain[-1][1]["inode"]},
                    "expectedIdentity": {"uid": expected_uid, "gid": expected_gid},
                    "parentSnapshots": [{"artifactId": f"parent-{number:04d}", "snapshot": snapshot}
                                        for number, (_path, snapshot) in enumerate(chain, 1)],
                    "absentArtifacts": [{"artifactId": artifact_id, "snapshot": {"type": "absent"}}
                                        for artifact_id, _path in absent],
                    "changes": [{"artifactId": aid, "beforeMode": oct(_mode(info)),
                                 "afterMode": oct(mode), "beforeUid": info.st_uid,
                                 "afterUid": expected_uid, "beforeGid": info.st_gid,
                                 "afterGid": expected_gid, "type": _kind(info), "snapshot": _snapshot(info)}
                                for aid, _path, info, mode in targets],
                    "intendedDirectoryMode": "0o700", "intendedFileMode": "0o600"}
    if expected_plan is not None and current_plan != expected_plan:
        raise BindingError("BINDING_PATH_UNSAFE", "permission repair preview is stale")
    if not targets:
        return [], current_plan
    if (os.name == "nt" or not hasattr(os, "fchmod") or not hasattr(os, "fchown")
            or not hasattr(os, "O_NOFOLLOW")):
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
                os.fchown(fd, expected_uid, expected_gid)
                changed.append((fd, before["uid"], before["gid"], int(before["mode"], 8)))
                os.fchmod(fd, expected)
            for _artifact_id, path, fd, expected, before in opened:
                after = os.fstat(fd)
                invariant = dict(before, uid=expected_uid, gid=expected_gid, mode=oct(expected))
                try:
                    current = path.lstat()
                except OSError:
                    raise BindingError("BINDING_PATH_UNSAFE", "repair target changed during permission repair") from None
                if not _same_snapshot(after, invariant) or not _same_snapshot(current, invariant):
                    raise BindingError("BINDING_PATH_UNSAFE", "repair target changed during permission repair")
            _verify_absent(absent)
            _verify_chain([(path, dict(snapshot, uid=expected_uid, gid=expected_gid,
                                       mode=oct(0o700)) if path == root else snapshot)
                           for path, snapshot in chain])
        except Exception:
            # Best-effort transactional rollback on the already-open exact inodes.
            for fd, original_uid, original_gid, original_mode in reversed(changed):
                try:
                    os.fchown(fd, original_uid, original_gid)
                    os.fchmod(fd, original_mode)
                except OSError:
                    pass
            raise
    finally:
        for _artifact_id, _path, fd, _expected, _before in opened:
            os.close(fd)
    repaired = sorted({"directory" if change[3] == 0o700 else "file" for change in targets})
    return repaired, current_plan
