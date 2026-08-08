import importlib.util
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).parents[1]
sys.path.insert(0, str(BASE))
spec = importlib.util.spec_from_file_location("clawpod_image_studio", BASE / "clawpod_image_studio.py")
s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)


def call(root, command, value):
    return s.execute(command, value, s.root(str(root)))


def brief():
    return {
        "title": "Launch", "businessGoal": "Increase qualified visits 10%", "audience": ["buyers"],
        "message": "Precise and durable", "intendedUses": ["web"],
        "deliverables": [{"channelPresetId": "web-srgb-v1", "quantity": 1, "dueAt": "2026-12-01T00:00:00Z"}],
        "creativeDirection": {"mood": ["calm"], "palette": ["#112233"], "composition": ["centered"], "lighting": ["soft"], "forbiddenElements": ["text"]},
        "references": [], "brandConstraints": [],
        "rightsPolicy": {"territories": ["US"], "media": ["digital"], "term": "2026/2027", "realPersonPolicy": "not_applicable", "trademarkPolicy": "cleared marks only"},
        "privacyPolicy": {"promptRetention": "digest_only", "publicMetadata": ["copyright"]},
        "budget": {"currency": "USD", "projectHardCeiling": "5.00", "perShotHardCeiling": "1.00"},
        "successCriteria": [{"id": "crit_00000000-0000-0000-0000-000000000001", "metric": "human_review", "operator": "human_pass", "target": True}],
    }


def shot(project_id, **changes):
    value = {
        "shotSpecVersion": 1, "shotId": "shot_00000000-0000-0000-0000-000000000001",
        "projectId": project_id, "name": "hero-front", "priority": "required", "purpose": "web hero",
        "subject": {"kind": "product", "ids": ["SKU-1"], "referenceIds": [], "releases": []},
        "frame": {"aspectRatio": "4:5", "orientation": "portrait", "composition": "centered",
                  "cropSafetyPct": {"top": 8, "right": 8, "bottom": 8, "left": 8},
                  "camera": {"shotSize": "CU", "angle": "eye", "focalLengthEquivalentMm": 85, "perspective": "compressed"},
                  "subjectOccupancyPct": {"min": 55, "max": 68}},
        "look": {"continuitySpecId": "cont_1", "lighting": {"keyDirectionDeg": 315, "hardness": "soft", "contrast": "medium"}, "palette": ["#112233"], "background": "neutral", "materialRules": ["retain texture"]},
        "constraints": [{"id": "con_1", "scope": "color", "rule": "delta", "severity": "major", "evaluation": "tolerance", "tolerance": {"metric": "deltaE2000", "max": 2.0}, "referenceIds": []}],
        "variants": {"requested": 1, "maximumPaidAttempts": 2, "explorationMode": "bounded"},
        "providerPlan": {"preferredProvider": "openai", "preferredModel": "gpt-image-1", "requiredCapabilities": [], "optionalControls": [], "fallback": "none"},
        "outputs": ["out_1"], "acceptanceRubricId": "rub_1",
    }
    value.update(changes); return value


def setup_shot(root):
    project = call(root, "project.create", {"name": "Campaign", "actor": "producer"})
    saved = call(root, "brief.save", {"projectId": project["projectId"], "expectedProjectRevision": 1, "actor": "producer", "brief": brief()})
    approved = call(root, "brief.approve", {"projectId": project["projectId"], "briefId": saved["brief"]["briefId"], "expectedBriefRevision": 1, "approver": "creative-director", "role": "creative_director"})
    compiled = call(root, "shot.compile", {"projectId": project["projectId"], "expectedProjectRevision": approved["project"]["revision"], "actor": "producer", "shots": [shot(project["projectId"])]})
    return project, compiled["items"][0]


def stage(root, name, body):
    path = root / "studio" / "inputs" / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body); return name


def rubric():
    return {"rubricId": "rub_1", "revision": 1,
            "dimensions": [{"id": "technical", "weight": .4, "evaluator": "machine_then_human", "minimum": 4}, {"id": "creative", "weight": .6, "evaluator": "human", "minimum": 4}],
            "scoreScale": {"min": 1, "max": 5}, "pass": {"weightedMinimum": 4, "blockingSeveritiesAllowed": 0}}


def test_project_brief_revision_and_strict_shot_compilation(tmp_path):
    project = call(tmp_path, "project.create", {"name": "Campaign", "actor": "owner"})
    with pytest.raises(s.E) as exc:
        call(tmp_path, "brief.save", {"projectId": project["projectId"], "expectedProjectRevision": 0, "actor": "owner", "brief": brief()})
    assert exc.value.code == "STALE_REVISION"
    saved = call(tmp_path, "brief.save", {"projectId": project["projectId"], "expectedProjectRevision": 1, "actor": "owner", "brief": brief()})
    approved = call(tmp_path, "brief.approve", {"projectId": project["projectId"], "briefId": saved["brief"]["briefId"], "expectedBriefRevision": 1, "approver": "Ada", "role": "creative_director"})
    invalid = shot(project["projectId"]); invalid["surprise"] = True
    with pytest.raises(s.E) as exc:
        call(tmp_path, "shot.compile", {"projectId": project["projectId"], "expectedProjectRevision": approved["project"]["revision"], "actor": "owner", "shots": [invalid]})
    assert exc.value.code == "UNKNOWN_FIELD" and call(tmp_path, "shot.list", {"projectId": project["projectId"]})["items"] == []
    unsupported = shot(project["projectId"]); unsupported["providerPlan"]["requiredCapabilities"] = ["seed"]
    with pytest.raises(s.E) as exc:
        call(tmp_path, "shot.compile", {"projectId": project["projectId"], "expectedProjectRevision": approved["project"]["revision"], "actor": "owner", "shots": [unsupported]})
    assert exc.value.code == "UNSUPPORTED_CONTROL"


def test_offline_generation_qa_critic_selection_revision_and_finish(tmp_path, monkeypatch):
    project, shot_record = setup_shot(tmp_path)
    path = stage(tmp_path, "variant.svg", b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="30"><rect width="20" height="30"/></svg>')
    monkeypatch.setattr(s, "transport", lambda *_: (_ for _ in ()).throw(AssertionError("network forbidden")))
    registered = call(tmp_path, "generation.register", {"projectId": project["projectId"], "shotId": shot_record["shotId"], "path": path, "actor": "producer", "provider": "openai", "model": "gpt-image-1", "preparedDigest": "sha256:"+"1"*64, "promptDigest": "sha256:"+"2"*64})
    version = registered["version"]; assert registered["offline"] and version["role"] == "variant"
    assert call(tmp_path, "generation.register", {"projectId": project["projectId"], "shotId": shot_record["shotId"], "path": path, "actor": "producer", "provider": "openai", "model": "gpt-image-1", "preparedDigest": "sha256:"+"1"*64, "promptDigest": "sha256:"+"2"*64})["idempotent"]
    qa = call(tmp_path, "qa.evaluate", {"versionId": version["versionId"], "actor": "qa"}); assert qa["passed"]
    critic = call(tmp_path, "critic.input", {"versionId": version["versionId"], "qaId": qa["qaId"], "rubric": rubric(), "actor": "critic"})
    assert critic["assetSha256"] == version["sha256"] and critic["advisoryOnly"] and "identity" in critic["humanGates"]
    selected = call(tmp_path, "select.record", {"versionId": version["versionId"], "expectedShotRevision": shot_record["revision"], "reviewer": "director", "role": "creative_director", "reason": "best composition"})
    issue = {"issueId": "issue_1", "sourceAnnotationIds": [], "category": "cleanup", "severity": "minor", "acceptance": "spot absent", "operation": "local_edit", "maskVersionId": None, "owner": "human"}
    plan = call(tmp_path, "revision.plan", {"baseVersionId": version["versionId"], "selectionId": selected["selection"]["selectionId"], "objective": "clean spot", "preserve": ["SKU"], "issues": [issue], "order": ["issue_1"], "maximumPaidOperations": 0, "approvalImpact": ["master"], "actor": "retoucher"})
    assert plan["baseSha256"] == version["sha256"]
    master_path = stage(tmp_path, "master.svg", b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="30"><rect fill="#112233" width="20" height="30"/></svg>')
    finished = call(tmp_path, "finish.record", {"baseVersionId": version["versionId"], "path": master_path, "recipe": [{"kind": "cleanup", "maskVersionId": "ver_mask", "parameters": {"region": "spot"}}], "actor": "retoucher"})
    master = finished["outputVersionId"]; master_qa = call(tmp_path, "qa.evaluate", {"versionId": master, "actor": "qa"})
    approval = call(tmp_path, "master.approve", {"versionId": master, "approver": "director", "role": "creative_director", "proofCondition": "calibrated sRGB"})
    assert master_qa["passed"] and approval["assetSha256"] == finished["outputSha256"]


def test_deterministic_contact_sheet_delivery_and_audit(tmp_path):
    project, shot_record = setup_shot(tmp_path)
    path = stage(tmp_path, "candidate.svg", b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><circle r="4" cx="5" cy="5"/></svg>')
    version = call(tmp_path, "candidate.register", {"projectId": project["projectId"], "shotId": shot_record["shotId"], "path": path, "role": "editable_master", "actor": "retoucher"})["version"]
    call(tmp_path, "qa.evaluate", {"versionId": version["versionId"], "actor": "qa"})
    call(tmp_path, "master.approve", {"versionId": version["versionId"], "approver": "director", "role": "creative_director", "proofCondition": "review display"})
    one = call(tmp_path, "contact_sheet.create", {"projectId": project["projectId"], "versionIds": [version["versionId"]], "columns": 1, "actor": "producer"})
    two = call(tmp_path, "contact_sheet.create", {"projectId": project["projectId"], "versionIds": [version["versionId"]], "columns": 1, "actor": "producer"})
    assert (tmp_path/one["path"]).read_bytes() == (tmp_path/two["path"]).read_bytes() and one["manifestDigest"] == two["manifestDigest"]
    delivery = call(tmp_path, "delivery.prepare", {"projectId": project["projectId"], "versionIds": [version["versionId"]], "destination": "client handoff", "external": False, "actor": "producer"})
    durable = tmp_path/"durable"; durable.mkdir()
    packaged = call(tmp_path, "delivery.package", {"deliveryId": delivery["deliveryId"], "manifestDigest": delivery["manifestDigest"], "durableRoot": str(durable), "actor": "producer"})
    again = call(tmp_path, "delivery.package", {"deliveryId": delivery["deliveryId"], "manifestDigest": delivery["manifestDigest"], "durableRoot": str(durable), "actor": "producer"})
    assert packaged["packageSha256"] == again["packageSha256"] and again["idempotent"]
    audit = call(tmp_path, "audit.verify", {"projectId": project["projectId"]})
    assert audit["valid"] and audit["blocking"] == 0 and audit["counts"]["deliveries"] == 1


def test_hash_change_and_external_delivery_gates(tmp_path):
    project, shot_record = setup_shot(tmp_path)
    name = stage(tmp_path, "master.svg", b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>')
    version = call(tmp_path, "candidate.register", {"projectId": project["projectId"], "shotId": shot_record["shotId"], "path": name, "role": "editable_master", "actor": "owner"})["version"]
    call(tmp_path, "qa.evaluate", {"versionId": version["versionId"], "actor": "qa"}); call(tmp_path, "master.approve", {"versionId": version["versionId"], "approver": "owner", "role": "director", "proofCondition": "sRGB"})
    delivery = call(tmp_path, "delivery.prepare", {"projectId": project["projectId"], "versionIds": [version["versionId"]], "destination": "public", "external": True, "actor": "owner"})
    durable = tmp_path/"durable"; durable.mkdir()
    with pytest.raises(s.E) as exc: call(tmp_path, "delivery.package", {"deliveryId": delivery["deliveryId"], "manifestDigest": delivery["manifestDigest"], "durableRoot": str(durable), "actor": "owner"})
    assert exc.value.code == "PUBLICATION_APPROVAL_REQUIRED"
    (tmp_path/version["path"]).write_bytes(b"changed")
    audit = call(tmp_path, "audit.verify", {"projectId": project["projectId"]})
    assert not audit["valid"] and audit["findings"][0]["code"] == "HASH_MISMATCH"
