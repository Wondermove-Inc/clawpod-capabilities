import json

import pytest
from click.testing import CliRunner

from cli_anything.clawpod_cloud_webhooks import clawpod_cloud_webhooks_cli as module
from cli_anything.clawpod_cloud_webhooks.core.contracts import create_preview, delete_preview, preview, resource_merge
from cli_anything.clawpod_cloud_webhooks.utils.backend import BackendError


BASE = {
    "source": {"id": "s1", "name": "source", "description": None, "provider": "custom", "is_active": True, "playbook_id": None, "tenant_id": "t"},
    "playbook": {"id": "p1", "name": "playbook", "description": None, "content": "instructions", "is_active": True, "tenant_id": "t"},
    "rule": {"id": "r1", "name": "rule", "description": None, "source_id": "s1", "playbook_id": None, "conditions": [], "target_type": "room", "target_room_ids": ["room-1"], "priority": 100, "is_active": True, "tenant_id": "t"},
}


class ScriptedBackend:
    resources = {}
    calls = []
    fail = None
    tls_verification_mode = "strict"

    def __init__(self, *args, **kwargs):
        self.resources = ScriptedBackend.resources

    def request(self, method, path, body=None, idempotency=None, **kwargs):
        ScriptedBackend.calls.append((method, path, body, idempotency))
        if ScriptedBackend.fail:
            raise BackendError(ScriptedBackend.fail, "scripted failure", method == "GET", 503)
        collection = next((kind for kind in self.resources if f"webhook-{kind}s" in path), None)
        if not collection:
            return {"ok": True}
        clean = path.split("?", 1)[0]
        parts = clean.rstrip("/").split("/")
        root = f"webhook-{collection}s"
        root_index = parts.index(root)
        resource_id = parts[root_index + 1] if len(parts) > root_index + 1 else None
        action = parts[root_index + 2] if len(parts) > root_index + 2 else None
        bucket = self.resources[collection]
        if method == "GET" and resource_id:
            if resource_id not in bucket:
                raise BackendError("not_found", "scripted HTTP 404", True, 404)
            return dict(bucket[resource_id])
        if method == "GET":
            return [dict(value) for value in bucket.values()]
        if method == "POST" and action:
            bucket[resource_id]["previous_secret_expires_at"] = "tomorrow"
            return {"id": resource_id, "signing_secret": "must-redact"}
        if method == "POST":
            resource_id = {"source": "s2", "playbook": "p2", "rule": "r2"}[collection]
            bucket[resource_id] = {"id": resource_id, **body}
            return dict(bucket[resource_id])
        if method == "PUT":
            bucket[resource_id] = {"id": resource_id, **body}
            return {"updated": True}
        if method == "DELETE":
            bucket.pop(resource_id)
            return {"deleted": True}
        raise AssertionError((method, path))

    def session_status(self):
        return {"connected": True, "session_storage": "memory", "tls_verification_mode": "strict"}


@pytest.fixture(autouse=True)
def scripted(monkeypatch):
    ScriptedBackend.resources = {kind: {value["id"]: dict(value)} for kind, value in BASE.items()}
    ScriptedBackend.calls = []
    ScriptedBackend.fail = None
    monkeypatch.setattr(module, "Backend", ScriptedBackend)


def invoke(args):
    result = CliRunner().invoke(module.cli, ["--json", *args])
    return result, json.loads(result.output)


def mutation_args(digest, key):
    return ["--tenant-id", "t", "--idempotency-key", key, "--effect-digest", digest, "--approve"]


@pytest.mark.parametrize("kind", ["source", "playbook", "rule"])
def test_every_resource_create_get_list_update_delete_transport(kind):
    payload = {k: v for k, v in BASE[kind].items() if k != "id"}
    create_digest = create_preview(kind, payload, "t", f"{kind}-create")["effect_digest"]
    result, data = invoke([kind, "create", "--payload-json", json.dumps(payload), *mutation_args(create_digest, f"{kind}-create")])
    assert result.exit_code == 0, result.output
    created_id = data["readback"]["id"]
    for action in ([kind, "get", created_id, "--tenant-id", "t"], [kind, "list", "--tenant-id", "t"]):
        result, _ = invoke(action); assert result.exit_code == 0
    before = dict(ScriptedBackend.resources[kind][created_id])
    after = resource_merge(kind, before, {"description": "updated"})
    update_digest = preview(kind, created_id, before, after, "t", f"{kind}-update")["effect_digest"]
    result, data = invoke([kind, "update", created_id, "--changes-json", '{"description":"updated"}', *mutation_args(update_digest, f"{kind}-update")])
    assert result.exit_code == 0 and data["verified"]
    before = dict(ScriptedBackend.resources[kind][created_id])
    delete_digest = delete_preview(kind, created_id, before, "t", f"{kind}-delete")["effect_digest"]
    result, data = invoke([kind, "delete", created_id, *mutation_args(delete_digest, f"{kind}-delete")])
    assert result.exit_code == 0 and data["readback"]["absent"]
    assert {call[0] for call in ScriptedBackend.calls} >= {"GET", "POST", "PUT", "DELETE"}
    delete_index = next(i for i, call in enumerate(ScriptedBackend.calls) if call[0] == "DELETE")
    assert ScriptedBackend.calls[delete_index + 1][0:2] == ("GET", f"/api/proxy/webhook-{kind}s/{created_id}?tenant_id=t")


@pytest.mark.parametrize("kind", ["source", "playbook", "rule"])
@pytest.mark.parametrize("enabled", [False, True])
def test_enable_disable_uses_full_put_and_readback(kind, enabled):
    before = dict(ScriptedBackend.resources[kind][BASE[kind]["id"]]); after = resource_merge(kind, before, {"is_active": enabled})
    key = f"{kind}-{enabled}"; dg = preview(kind, before["id"], before, after, "t", key)["effect_digest"]
    result, data = invoke([f"{kind}-{'enable' if enabled else 'disable'}", before["id"], *mutation_args(dg, key)])
    assert result.exit_code == 0 and data["verified"] and data["readback"]["is_active"] is enabled


def test_rule_reorder_and_source_secret_actions():
    before = dict(ScriptedBackend.resources["rule"]["r1"]); after = resource_merge("rule", before, {"priority": 7})
    dg = preview("rule", "r1", before, after, "t", "reorder")["effect_digest"]
    result, data = invoke(["rule-reorder", "r1", "--priority", "7", *mutation_args(dg, "reorder")])
    assert result.exit_code == 0 and data["readback"]["priority"] == 7
    for command, route in (("source-rotate-secret", "rotate-secret"), ("source-regenerate", "regenerate")):
        before = dict(ScriptedBackend.resources["source"]["s1"]); after = {**before, "secret_action": command.removeprefix("source-")}
        dg = preview("source", "s1", before, after, "t", command)["effect_digest"]
        result, data = invoke([command, "s1", *mutation_args(dg, command)])
        assert result.exit_code == 0 and data["verified"] and "must-redact" not in result.output
        assert any(route in call[1] for call in ScriptedBackend.calls)


def test_event_actions_are_read_only_and_redacted():
    ScriptedBackend.resources["event"] = {"e1": {"id": "e1", "status": "delivered", "error_message": "", "headers": {"Authorization": "Bearer secret"}, "destination_evidence": {"id": "m"}}}
    # The generic fake recognizes the Event collection once it is part of its model.
    for args in (["event", "list", "--tenant-id", "t"], ["event", "get", "e1", "--tenant-id", "t"], ["event-inspect-redacted", "e1", "--tenant-id", "t"], ["event-verify", "e1", "--tenant-id", "t", "--require-destination-evidence"]):
        result, _ = invoke(args); assert result.exit_code == 0 and "Bearer secret" not in result.output
    assert all(call[0] == "GET" for call in ScriptedBackend.calls)


@pytest.mark.parametrize("failure", ["backend_error", "timeout", "auth_failed"])
def test_transport_failures_are_typed_and_never_mutate(failure):
    ScriptedBackend.fail = failure
    result, data = invoke(["source", "list", "--tenant-id", "t"])
    assert result.exit_code == 2 and data["error"]["code"] == failure
    assert all(call[0] == "GET" for call in ScriptedBackend.calls)


def test_digest_approval_and_payload_failures_stop_before_mutation():
    cases = [
        ["source", "create", "--payload-json", '{"name":"x","unknown":1}', *mutation_args("bad", "x")],
        ["source", "update", "s1", "--changes-json", '{"description":"x"}', *mutation_args("bad", "x")],
        ["rule", "create", "--payload-json", '{"name":"x","tenant_id":"t","conditions":[{"operator":"gt"}]}', *mutation_args("bad", "x")],
    ]
    for args in cases:
        ScriptedBackend.calls = []
        result, data = invoke(args)
        assert result.exit_code == 2 and not any(call[0] in {"POST", "PUT", "DELETE"} for call in ScriptedBackend.calls)
        assert data["error"]["code"] == "invalid_input"


def test_create_rejects_conflicting_payload_tenant_before_post():
    payload = {"name": "cross-tenant", "tenant_id": "other"}
    result, data = invoke(["playbook", "create", "--payload-json", json.dumps(payload), *mutation_args("irrelevant", "key")])
    assert result.exit_code == 2 and data["error"]["code"] == "invalid_input"
    assert not any(call[0] == "POST" for call in ScriptedBackend.calls)


def test_delete_non_404_readback_failure_is_not_treated_as_absence(monkeypatch):
    before = dict(ScriptedBackend.resources["source"]["s1"])
    dg = delete_preview("source", "s1", before, "t", "delete-key")["effect_digest"]
    original = ScriptedBackend.request
    def fail_verification(self, method, path, **kwargs):
        if method == "GET" and "/webhook-sources/s1?" in path and "s1" not in self.resources["source"]:
            raise BackendError("backend_error", "scripted HTTP 503", True, 503)
        return original(self, method, path, **kwargs)
    monkeypatch.setattr(ScriptedBackend, "request", fail_verification)
    result, data = invoke(["source", "delete", "s1", *mutation_args(dg, "delete-key")])
    assert result.exit_code == 2 and data["error"]["status"] == 503
