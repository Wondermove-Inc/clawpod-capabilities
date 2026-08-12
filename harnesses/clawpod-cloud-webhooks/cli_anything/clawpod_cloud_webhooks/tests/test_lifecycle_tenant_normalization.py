import pytest

from cli_anything.clawpod_cloud_webhooks.core.contracts import (
    create_preview,
    delete_preview,
    preflight,
)
from cli_anything.clawpod_cloud_webhooks.core.lifecycle import execute_plan
from cli_anything.clawpod_cloud_webhooks.utils.backend import BackendError


def test_preflight_accepts_backend_numeric_tenant_for_cli_string_tenant():
    preflight({"tenant_id": 2}, "2")
    preflight({"targets": [{"tenant_id": 2}]}, "2")


def test_preflight_still_rejects_cross_tenant_values():
    with pytest.raises(ValueError, match="tenant isolation mismatch"):
        preflight({"tenant_id": 3}, "2")
    with pytest.raises(ValueError, match="target tenant isolation mismatch"):
        preflight({"targets": [{"tenant_id": 3}]}, "2")


def test_source_create_and_cleanup_accept_numeric_readback_tenant():
    class SourceBackend:
        def __init__(self):
            self.item = None

        def request(self, method, path, body=None, idempotency=None, deadline=None):
            if method == "POST":
                self.item = {**body, "id": 36, "tenant_id": 2}
                return {"source": {"id": 36}}
            if method == "DELETE":
                self.item = None
                return {"deleted": True}
            if method == "GET":
                if self.item is None:
                    raise BackendError("not_found", "backend HTTP 404", True, 404)
                return dict(self.item)
            raise AssertionError(method)

    backend = SourceBackend()
    payload = {"name": "disposable", "tenant_id": "2"}
    create_key = "source-create-regression"
    create = {
        "name": "create",
        "operation": "source.create",
        "tenant_id": "2",
        "payload": payload,
        "approve": True,
        "idempotency_key": create_key,
        "effect_digest": create_preview("source", payload, "2", create_key)["effect_digest"],
    }
    created = execute_plan(backend, {"steps": [create]})
    assert created["ok"] is True

    readback = created["completed_steps"][0]["readback"]
    delete_key = "source-delete-regression"
    delete = {
        "name": "delete",
        "operation": "source.delete",
        "tenant_id": "2",
        "resource_id": readback["id"],
        "approve": True,
        "idempotency_key": delete_key,
        "effect_digest": delete_preview("source", readback["id"], readback, "2", delete_key)["effect_digest"],
    }
    deleted = execute_plan(backend, {"steps": [delete]})
    assert deleted["ok"] is True
    assert deleted["completed_steps"][0]["readback"]["absent"] is True
