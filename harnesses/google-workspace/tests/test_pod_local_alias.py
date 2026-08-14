import json
import os
import stat
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from google_workspace_core.auth import CredentialProvider
from google_workspace_core.bindings import (
    BindingError, binding_root, import_binding, list_bindings, normalize_alias,
    remove_binding, rename_binding, resolve_binding, restore_registry_backup,
)
from google_workspace_core.high_level_reads import normalize
from google_workspace_core.migration import apply_migration, preview_candidates
from google_workspace_core.permissions import check_permissions, repair_permissions
from google_workspace_core.security import redact


def bundle(path, alias="legacy", subject="subject-one"):
    path.write_text(json.dumps({"accounts": {alias: {
        "access_token": "CANARY_ACCESS", "refresh_token": "CANARY_REFRESH",
        "client_id": "client", "client_secret": "CANARY_CLIENT_SECRET",
        "expires_at": 4102444800, "email": "person@example.invalid",
        "subject_hash": subject, "scopes": ["scope"],
    }}}), encoding="utf-8")
    path.chmod(0o600)
    return path


@pytest.mark.parametrize("value", ["A", "with space", "a/b", "a\\b", ".", "..", "é", "a" * 64, "a\n"])
def test_alias_rejections(value):
    with pytest.raises(BindingError):
        normalize_alias(value)


def test_root_precedence_and_replaceable_rejection(tmp_path):
    assert binding_root({"GOOGLE_WORKSPACE_BINDING_ROOT": str(tmp_path)}) == tmp_path
    with pytest.raises(BindingError, match="absolute"):
        binding_root({"GOOGLE_WORKSPACE_BINDING_ROOT": "relative"})
    with pytest.raises(BindingError, match="replaceable"):
        binding_root({"GOOGLE_WORKSPACE_BINDING_ROOT": str(PACKAGE)})


def test_copy_rename_resolve_remove_and_backup_restore(tmp_path):
    root = tmp_path / "state"
    source = bundle(tmp_path / "legacy.json")
    first = import_binding("work", source, source_alias="legacy", root=root)
    assert first["revision"] == 1
    selected, path, bundle_alias, item, revision = resolve_binding("work", root)
    assert (selected, bundle_alias, revision) == ("work", "work", 1)
    assert path.parent == root / "credentials" and path.name != "work.json"
    assert "CANARY" not in json.dumps(first)
    renamed = rename_binding("work", "team", root)
    assert renamed["revision"] == 2 and resolve_binding("team", root)[0] == "team"
    backups = sorted((root / "backups").iterdir())
    assert backups
    removed = remove_binding("team", root=root)
    assert removed["revision"] == 3 and list_bindings(root)[0] == []
    restored = restore_registry_backup(backups[-1].name, root)
    assert restored["revision"] == 4 and resolve_binding("work", root)[0] == "work"


def test_explicit_path_precedence_and_binding_default(tmp_path, monkeypatch):
    root = tmp_path / "state"
    explicit = bundle(tmp_path / "explicit.json", "explicit", "subject-explicit")
    import_binding("work", bundle(tmp_path / "legacy.json"), source_alias="legacy", root=root)
    monkeypatch.setenv("GOOGLE_WORKSPACE_BINDING_ROOT", str(root))
    direct = CredentialProvider(str(explicit)); assert direct.load("explicit")["subject_hash"] == "subject-explicit"
    implicit = CredentialProvider(); assert implicit.load("work")["subject_hash"] == "subject-one"
    assert implicit.resolved_alias == "work"


def test_schema_corruption_permissions_migration_and_redaction(tmp_path):
    root = tmp_path / "state"; source = bundle(tmp_path / "legacy.json")
    candidates = preview_candidates([str(source)])
    assert candidates[0]["healthy"] and str(source) not in json.dumps(candidates)
    results, revision, _plan = apply_migration([str(source)], [{"candidateId": "0", "alias": "work", "sourceAlias": "legacy"}], root)
    assert results[0]["alias"] == "work"
    assert revision == 2
    credential = next((root / "credentials").iterdir()); credential.chmod(0o644)
    assert not all(item["passed"] for item in check_permissions(root))
    repaired, _plan = repair_permissions(root)
    assert "file" in repaired and stat.S_IMODE(credential.stat().st_mode) == 0o600
    canary = {"nested": [{"credentialRef": str(source), "providerResponse": "CANARY"}], "message": "Bearer CANARY"}
    output = json.dumps(redact(canary))
    assert "CANARY" not in output and str(source) not in output


def test_high_level_reads_are_bounded_normalizers():
    items, token = normalize("gmail.read", {"messages": [{"id": "m", "snippet": "s", "payload": "secret"}], "nextPageToken": "n"})
    assert items[0]["id"] == "m" and items[0]["snippet"] == "s" and "payload" not in items[0] and token == "n"
    items, _ = normalize("calendar.read", {"items": [{"id": "e", "attendees": [{}, {}]}]})
    assert items[0]["attendeeCount"] == 2
    items, _ = normalize("drive.read", {"files": [{"id": "f", "owners": [{"emailAddress": "private"}]}]})
    assert items[0]["ownerCount"] == 1 and "private" not in json.dumps(items)
