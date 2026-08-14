import json
import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from google_workspace_core.bindings import BindingError, import_binding, list_bindings


def _bundle(path, subject="subject-one"):
    path.write_text(json.dumps({"accounts": {"legacy": {
        "access_token": "fixture-access", "refresh_token": "fixture-refresh",
        "client_id": "fixture-client", "client_secret": "fixture-secret",
        "expires_at": 4102444800, "subject_hash": subject,
    }}}), encoding="utf-8")
    path.chmod(0o600)
    return path


@pytest.mark.skipif(not hasattr(os, "fchown") or os.geteuid() != 0,
                    reason="requires root-owned synthetic protected GID")
def test_import_inherits_protected_gid_not_process_default_gid(tmp_path, monkeypatch):
    """Model /workspace(02777,gid=1000)/<private root> with EGID != 1000."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    try:
        os.chown(workspace, -1, 1000)
    except OSError as exc:
        pytest.skip(f"filesystem user namespace cannot represent gid 1000: {exc.errno}")
    workspace.chmod(0o2777)
    root = workspace / "private-root"
    source = _bundle(tmp_path / "legacy.json")
    monkeypatch.setattr("google_workspace_core.bindings._exact_forge_location",
                        lambda paths: [p.name for p in paths] == ["workspace", "private-root"])

    result = import_binding("work", source, source_alias="legacy", root=root)

    assert result["revision"] == 1
    artifacts = [root, root / "credentials", root / "backups",
                 root / "bindings.v1.lock", root / "bindings.v1.json",
                 *list((root / "credentials").iterdir())]
    assert os.getegid() != 1000
    assert {path.lstat().st_gid for path in artifacts} == {1000}
    assert stat.S_IMODE(root.lstat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.lstat().st_mode) == 0o700 for path in artifacts[1:3])
    assert all(stat.S_IMODE(path.lstat().st_mode) == 0o600 for path in artifacts[3:])
    assert list_bindings(root)[1] == 1
    assert source.exists()  # importing never deletes the legacy source


def test_fchown_failure_removes_uncommitted_credential_and_preserves_source(tmp_path):
    root = tmp_path / "state"
    source = _bundle(tmp_path / "legacy.json")
    # Bootstrap first so the injected failure is specifically credential creation.
    from google_workspace_core.bindings import ensure_root
    ensure_root(root)
    real_fchown = os.fchown

    def fail_credential(fd, uid, gid):
        info = os.fstat(fd)
        if stat.S_ISREG(info.st_mode):
            raise OSError("synthetic chown failure")
        return real_fchown(fd, uid, gid)

    with patch("os.fchown", side_effect=fail_credential), pytest.raises(BindingError, match="metadata|written"):
        import_binding("work", source, source_alias="legacy", root=root)
    assert source.exists()
    assert list((root / "credentials").iterdir()) == []
    assert not (root / "bindings.v1.json").exists()


def test_registry_replace_failure_has_no_revision_backup_or_credential_drift(tmp_path):
    root = tmp_path / "state"
    first_source = _bundle(tmp_path / "first.json")
    import_binding("first", first_source, source_alias="legacy", root=root)
    registry_before = (root / "bindings.v1.json").read_bytes()
    backups_before = {p.name: p.read_bytes() for p in (root / "backups").iterdir()}
    credentials_before = {p.name: p.read_bytes() for p in (root / "credentials").iterdir()}
    second_source = _bundle(tmp_path / "second.json", "subject-two")

    with patch("os.replace", side_effect=OSError("synthetic replace failure")), \
         pytest.raises(BindingError, match="transaction"):
        import_binding("second", second_source, source_alias="legacy", root=root)

    assert (root / "bindings.v1.json").read_bytes() == registry_before
    assert {p.name: p.read_bytes() for p in (root / "backups").iterdir()} == backups_before
    assert {p.name: p.read_bytes() for p in (root / "credentials").iterdir()} == credentials_before
    assert list_bindings(root)[1] == 1
    assert second_source.exists()
    assert import_binding("second", second_source, source_alias="legacy", root=root)["revision"] == 2


def test_write_failure_cleans_partial_file_without_bootstrapping_registry(tmp_path):
    root = tmp_path / "state"
    source = _bundle(tmp_path / "legacy.json")
    real_write = os.write
    failed = False

    def fail_once(fd, data):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("synthetic write failure")
        return real_write(fd, data)

    with patch("os.write", side_effect=fail_once), pytest.raises(BindingError, match="written"):
        import_binding("work", source, source_alias="legacy", root=root)
    assert list((root / "credentials").iterdir()) == []
    assert list((root / "backups").iterdir()) == []
    assert not (root / "bindings.v1.json").exists()
    assert source.exists()


def test_post_replace_fsync_failure_rolls_back_revision_backup_and_credential(tmp_path):
    root = tmp_path / "state"
    import_binding("first", _bundle(tmp_path / "first.json"), source_alias="legacy", root=root)
    registry_before = (root / "bindings.v1.json").read_bytes()
    backups_before = {p.name: p.read_bytes() for p in (root / "backups").iterdir()}
    credentials_before = {p.name: p.read_bytes() for p in (root / "credentials").iterdir()}
    second = _bundle(tmp_path / "second.json", "subject-two")
    from google_workspace_core import bindings
    real_fsync_directory = bindings._fsync_directory
    failed = False

    def fail_commit_once(path):
        nonlocal failed
        if Path(path) == root and not failed:
            failed = True
            raise OSError("synthetic commit fsync failure")
        return real_fsync_directory(path)

    with patch("google_workspace_core.bindings._fsync_directory", side_effect=fail_commit_once), \
         pytest.raises(BindingError, match="transaction") as raised:
        import_binding("second", second, source_alias="legacy", root=root)
    assert not raised.value.committed
    assert (root / "bindings.v1.json").read_bytes() == registry_before
    assert {p.name: p.read_bytes() for p in (root / "backups").iterdir()} == backups_before
    assert {p.name: p.read_bytes() for p in (root / "credentials").iterdir()} == credentials_before
    assert list_bindings(root)[1] == 1
    assert second.exists()
    assert import_binding("second", second, source_alias="legacy", root=root)["revision"] == 2
