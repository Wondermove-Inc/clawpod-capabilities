"""Red contract tests for permission-first bootstrap.

These tests use synthetic canary bytes only. They never inspect a real credential.
"""
import json
import os
import stat
import sys
from pathlib import Path

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
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace.chmod(0o2777)
    root = workspace / "protected"
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
