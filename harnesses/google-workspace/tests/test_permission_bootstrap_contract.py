"""Red contract tests for permission-first bootstrap.

These tests use synthetic canary bytes only. They never inspect a real credential.
"""
import json
import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from google_workspace_core.bindings import import_binding
from google_workspace_core.core import run
from google_workspace_core.permissions import plan_repair, repair_permissions


def _bundle(path):
    path.write_text(json.dumps({"accounts": {"legacy": {
        "access_token": "CANARY_ACCESS", "refresh_token": "CANARY_REFRESH",
        "client_id": "client", "client_secret": "CANARY_SECRET",
        "expires_at": 4102444800, "subject_hash": "subject-one",
    }}}), encoding="utf-8")
    path.chmod(0o600)
    return path


def _forge_legacy_shape(tmp_path):
    process_root = tmp_path / "root"
    process_root.mkdir()
    process_root.chmod(0o2777)
    root = process_root / "protected"
    import_binding("work", _bundle(tmp_path / "source.json"), source_alias="legacy", root=root)
    credential = next((root / "credentials").iterdir())
    # Reproduce metadata only: the implementation must not need these bytes.
    credential.write_bytes(b"not-json CANARY_CREDENTIAL_BYTES")
    root.chmod(0o2770)
    (root / "credentials").chmod(0o2770)
    credential.chmod(0o660)
    return root, credential


def _contains_path(value, path):
    return str(path) in json.dumps(value, sort_keys=True)


def test_status_reports_permission_bootstrap_before_credential_parse(tmp_path, monkeypatch):
    root, credential = _forge_legacy_shape(tmp_path)
    monkeypatch.setenv("GOOGLE_WORKSPACE_BINDING_ROOT", str(root))

    out, code = run("auth.bindings.status", {})

    assert code == 0, out
    assert out["data"]["healthy"] is False
    checks = out["data"]["permissionChecks"]
    assert any(c["currentMode"] == "0o2770" and c["intendedMode"] == "0o700" for c in checks)
    assert any(c["currentMode"] == "0o660" and c["intendedMode"] == "0o600" for c in checks)
    assert not _contains_path(out, root)
    assert not _contains_path(out, credential)
    assert "CANARY" not in json.dumps(out)


def test_repair_preview_binds_exact_opaque_targets_and_snapshots(tmp_path):
    root, credential = _forge_legacy_shape(tmp_path)

    plan = plan_repair(root)

    assert plan["operation"] == "permissions.repair"
    assert len(plan["changes"]) >= 3
    assert {change["afterMode"] for change in plan["changes"]} == {"0o700", "0o600"}
    assert all(change["artifactId"].startswith("artifact-") for change in plan["changes"])
    assert all(set(change["snapshot"]) >= {"device", "inode", "uid", "type", "linkCount", "mode"} for change in plan["changes"])
    assert not _contains_path(plan, root)
    assert not _contains_path(plan, credential)


def test_mode_only_repair_is_idempotent_and_preserves_credential_bytes(tmp_path):
    root, credential = _forge_legacy_shape(tmp_path)
    before = credential.read_bytes()

    repaired, _ = repair_permissions(root)
    second_plan = plan_repair(root)
    repaired_again, _ = repair_permissions(root)

    assert repaired
    assert stat.S_IMODE(root.lstat().st_mode) == 0o700
    assert stat.S_IMODE(credential.lstat().st_mode) == 0o600
    assert credential.read_bytes() == before
    assert second_plan["changes"] == []
    assert repaired_again == []


def test_metadata_only_status_and_repair_never_open_credential_bytes(tmp_path, monkeypatch):
    root, credential = _forge_legacy_shape(tmp_path)
    monkeypatch.setenv("GOOGLE_WORKSPACE_BINDING_ROOT", str(root))
    real_open = os.open
    real_read = os.read
    credential_fds = set()

    def guarded_open(path, flags, *args, **kwargs):
        fd = real_open(path, flags, *args, **kwargs)
        if Path(path) == credential:
            credential_fds.add(fd)
        return fd

    def guarded_read(fd, size):
        if fd in credential_fds:
            raise AssertionError("credential bytes were read")
        return real_read(fd, size)

    with patch("os.read", side_effect=guarded_read), \
         patch("os.open", side_effect=guarded_open):
        out, code = run("auth.bindings.status", {})
        repaired, _ = repair_permissions(root)
    assert code == 0 and repaired
    assert "CANARY" not in json.dumps(out)


def test_stale_snapshot_rejected_before_first_chmod(tmp_path):
    root, credential = _forge_legacy_shape(tmp_path)
    plan = plan_repair(root)
    credential.chmod(0o640)
    with patch("os.fchmod") as chmod:
        with pytest.raises(Exception, match="stale"):
            repair_permissions(root, expected_plan=plan)
    chmod.assert_not_called()


def test_parent_race_rejected_before_first_chmod(tmp_path):
    root, _credential = _forge_legacy_shape(tmp_path)
    plan = plan_repair(root)
    (tmp_path / "root").chmod(0o1777)
    with patch("os.fchmod") as chmod:
        with pytest.raises(Exception, match="stale"):
            repair_permissions(root, expected_plan=plan)
    chmod.assert_not_called()


@pytest.mark.parametrize("bad_mode", [0o0777, 0o1770, 0o2770, 0o3777])
def test_other_writable_parent_requires_exact_forge_or_sticky_mode(tmp_path, bad_mode):
    root, _credential = _forge_legacy_shape(tmp_path)
    (tmp_path / "root").chmod(bad_mode)
    with patch("os.fchmod") as chmod, pytest.raises(Exception):
        repair_permissions(root)
    chmod.assert_not_called()


def test_forge_parent_must_be_process_owned(tmp_path):
    root, _credential = _forge_legacy_shape(tmp_path)
    parent_inode = (tmp_path / "root").lstat().st_ino
    real_owned = __import__("google_workspace_core.permissions", fromlist=["_owned"])._owned

    def synthetic_owner(info):
        return False if info.st_ino == parent_inode else real_owned(info)

    with patch("google_workspace_core.permissions._owned", side_effect=synthetic_owner), \
         patch("os.fchmod") as chmod, pytest.raises(Exception):
        repair_permissions(root)
    chmod.assert_not_called()


def test_root_rename_swap_after_preview_fails_before_chmod(tmp_path):
    root, _credential = _forge_legacy_shape(tmp_path)
    plan = plan_repair(root)
    moved = root.with_name("protected-moved")
    root.rename(moved)
    root.mkdir(mode=0o700)
    with patch("os.fchmod") as chmod, pytest.raises(Exception, match="stale|unsafe"):
        repair_permissions(root, expected_plan=plan)
    chmod.assert_not_called()


def test_target_swap_after_open_fails_before_first_chmod(tmp_path):
    root, credential = _forge_legacy_shape(tmp_path)
    plan = plan_repair(root)
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"replacement")
    replacement.chmod(0o660)
    real_open = os.open
    swapped = False

    def swapping_open(path, flags, *args, **kwargs):
        nonlocal swapped
        fd = real_open(path, flags, *args, **kwargs)
        if Path(path) == credential and not swapped:
            swapped = True
            credential.unlink()
            replacement.rename(credential)
        return fd

    with patch("os.open", side_effect=swapping_open), patch("os.fchmod") as chmod, \
         pytest.raises(Exception, match="changed"):
        repair_permissions(root, expected_plan=plan)
    chmod.assert_not_called()


def test_owner_mismatch_blocks_entire_plan(tmp_path):
    root, credential = _forge_legacy_shape(tmp_path)
    credential_inode = credential.lstat().st_ino
    real_owned = __import__("google_workspace_core.permissions", fromlist=["_owned"])._owned

    def synthetic_owner(info):
        return False if info.st_ino == credential_inode else real_owned(info)

    with patch("google_workspace_core.permissions._owned", side_effect=synthetic_owner), \
         patch("os.fchmod") as chmod:
        with pytest.raises(Exception):
            repair_permissions(root)
    chmod.assert_not_called()


def test_backend_failure_rolls_back_all_modes(tmp_path, monkeypatch):
    root, credential = _forge_legacy_shape(tmp_path)
    before = {path: stat.S_IMODE(path.lstat().st_mode) for path in
              (root, root / "credentials", credential)}
    real_fchmod = os.fchmod
    forward_calls = 0

    def failing_fchmod(fd, mode):
        nonlocal forward_calls
        if mode in (0o700, 0o600):
            forward_calls += 1
            if forward_calls == 2:
                raise OSError("synthetic chmod failure")
        return real_fchmod(fd, mode)

    monkeypatch.setattr(os, "fchmod", failing_fchmod)
    with pytest.raises(OSError, match="synthetic"):
        repair_permissions(root)
    assert {path: stat.S_IMODE(path.lstat().st_mode) for path in before} == before


@pytest.mark.parametrize("bad_root", ["relative", "../escape"])
def test_malformed_or_non_absolute_root_fails_closed(bad_root):
    with pytest.raises(Exception):
        plan_repair(bad_root)


def test_directory_symlink_escape_is_not_traversed(tmp_path):
    root, _credential = _forge_legacy_shape(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (external / "CANARY_EXTERNAL").write_bytes(b"never inspect")
    credentials = root / "credentials"
    for item in credentials.iterdir():
        item.unlink()
    credentials.rmdir()
    credentials.symlink_to(external, target_is_directory=True)
    with patch("os.scandir", wraps=os.scandir) as scandir:
        with pytest.raises(Exception):
            plan_repair(root)
    assert all(Path(call.args[0]) != credentials for call in scandir.call_args_list
               if not isinstance(call.args[0], int))


def test_external_reference_and_malformed_registry_are_not_read(tmp_path):
    root, _credential = _forge_legacy_shape(tmp_path)
    registry = root / "bindings.v1.json"
    doc = json.loads(registry.read_text())
    item = doc["bindings"]["work"]
    item["externalReference"] = True
    item["credentialRef"] = str(tmp_path / "outside.json")
    registry.write_text(json.dumps(doc))
    registry.chmod(0o660)
    before = registry.read_bytes()
    assert plan_repair(root)["changes"]
    assert registry.read_bytes() == before
    registry.write_bytes(b"not-json")
    registry.chmod(0o660)
    before = registry.read_bytes()
    assert plan_repair(root)["changes"]
    assert registry.read_bytes() == before


def test_confirm_digest_is_bound_to_exact_snapshot(tmp_path, monkeypatch):
    root, credential = _forge_legacy_shape(tmp_path)
    state = tmp_path / "preview-state.json"
    monkeypatch.setenv("GOOGLE_WORKSPACE_BINDING_ROOT", str(root))
    monkeypatch.setenv("GOOGLE_WORKSPACE_STATE_FILE", str(state))
    preview, code = run("auth.bindings.permissions.repair", {"dryRun": True})
    assert code == 0
    credential.chmod(0o640)
    confirmed, code = run("auth.bindings.permissions.repair", {"confirm": preview["data"]["effectDigest"]})
    assert code == 4
    assert confirmed["error"]["code"] == "APPROVAL_REQUIRED"
    assert stat.S_IMODE(root.lstat().st_mode) == 0o2770


@pytest.mark.parametrize("unsafe", ["symlink", "hardlink", "fifo"])
def test_bootstrap_preview_fails_closed_for_unsafe_artifacts(tmp_path, unsafe):
    root, credential = _forge_legacy_shape(tmp_path)
    if unsafe == "symlink":
        credential.unlink()
        credential.symlink_to(tmp_path / "source.json")
    elif unsafe == "hardlink":
        os.link(credential, tmp_path / "second-link")
    else:
        credential.unlink()
        os.mkfifo(credential)

    with pytest.raises(Exception):
        plan_repair(root)
