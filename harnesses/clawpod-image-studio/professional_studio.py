"""Deterministic, offline professional photo-studio records.

This module deliberately has no transport code.  Provider execution remains in
clawpod_image_studio.py and results are registered here only after they exist.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import struct
import tempfile
import uuid
import zipfile
from pathlib import Path

STUDIO_COMMANDS = """project.create project.get project.list brief.save brief.approve
shot.compile shot.list candidate.register generation.register qa.evaluate critic.input
select.record revision.plan finish.record master.approve contact_sheet.create
delivery.prepare delivery.package audit.verify""".split()

PROJECT_STATES = ["intake", "brief_pending", "brief_approved", "shot_plan_approved",
                  "look_development", "production", "selects", "retouch",
                  "continuity_review", "proofing", "approval", "delivery_ready",
                  "delivered", "archived"]
ROLES = {"source", "reference", "attempt", "variant", "select", "editable_master",
         "review_proxy", "proof", "rendition", "delivery_manifest"}
SHOT_TOP = {"shotSpecVersion", "shotId", "projectId", "name", "priority", "purpose",
            "subject", "frame", "look", "constraints", "variants", "providerPlan",
            "outputs", "acceptanceRubricId"}
SHOT_REQUIRED = SHOT_TOP


def _stable(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value):
    data = value if isinstance(value, bytes) else _stable(value).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _id(prefix):
    return prefix + "_" + str(uuid.uuid4())


def _closed(api, value, allowed, required=()):
    api.closed(value, allowed, required)


def _dir(root, kind):
    path = root / "studio" / kind
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def _record_path(root, kind, ident):
    if not isinstance(ident, str) or not re.fullmatch(r"[a-z]+_[0-9a-f-]{36}", ident):
        raise ValueError("invalid record id")
    return _dir(root, kind) / (ident + ".json")


def _load(api, root, kind, ident):
    try:
        path = _record_path(root, kind, ident)
    except ValueError:
        raise api.E("SCHEMA_INVALID", "invalid record identifier")
    value = api.readj(path, None)
    if value is None:
        raise api.E("NOT_FOUND", f"{kind} record unavailable", 3)
    return value


def _save(api, root, kind, record):
    api.atomic(_record_path(root, kind, record[_primary(kind)]), record)
    return record


def _primary(kind):
    return {"projects": "projectId", "briefs": "briefId", "shots": "shotId",
            "versions": "versionId", "qa": "qaId", "critics": "criticInputId",
            "selections": "selectionId", "revisions": "revisionPlanId",
            "finishes": "finishId", "approvals": "approvalId",
            "contacts": "contactSheetId", "deliveries": "deliveryId"}[kind]


def _base(api, prefix, id_key, actor="system"):
    stamp = api.now()
    return {"schemaVersion": 1, id_key: _id(prefix), "revision": 1,
            "createdAt": stamp, "updatedAt": stamp, "actor": actor}


def _expect(api, record, expected):
    if expected != record["revision"]:
        raise api.E("STALE_REVISION", "expected revision does not match current record",
                    details={"expectedRevision": expected, "actualRevision": record["revision"]})


def _mutate(api, record):
    record = dict(record)
    record["revision"] += 1
    record["updatedAt"] = api.now()
    return record


def _project(api, root, project_id):
    return _load(api, root, "projects", project_id)


def _asset_path(api, root, raw):
    # Registration may read either provider artifacts or explicitly staged studio input.
    for base in (root / "artifacts", root / "studio" / "inputs"):
        try:
            candidate = api.safe_output(base, raw)
        except api.E:
            continue
        if candidate.is_file() and not candidate.is_symlink():
            return candidate, str(candidate.relative_to(root))
    raise api.E("NOT_FOUND", "asset path unavailable under artifacts or studio/inputs", 3)


def _inspect(api, path):
    try:
        item = api.inspect_artifact(path)
    except api.E as exc:
        raise api.E("CORRUPT_ASSET", exc.msg, 8, details=exc.details)
    return item


def _version_for_hash(api, root, digest):
    for path in sorted(_dir(root, "versions").glob("*.json")):
        rec = api.readj(path, {})
        if rec.get("sha256") == digest:
            return rec
    return None


def _register(api, root, x, generation=False):
    allowed = {"projectId", "shotId", "path", "role", "parentVersionIds", "actor",
               "provider", "model", "providerRequestId", "preparedDigest",
               "promptDigest", "referenceHashes", "controls"}
    _closed(api, x, allowed, ("projectId", "shotId", "path", "actor"))
    project = _project(api, root, x["projectId"])
    shot = _load(api, root, "shots", x["shotId"])
    if shot["projectId"] != project["projectId"]:
        raise api.E("SCHEMA_INVALID", "shot does not belong to project")
    role = x.get("role", "variant" if generation else "source")
    if role not in ROLES or (generation and role not in {"attempt", "variant"}):
        raise api.E("SCHEMA_INVALID", "invalid asset role")
    path, relative = _asset_path(api, root, x["path"])
    inspected = _inspect(api, path)
    parents = x.get("parentVersionIds", [])
    if not isinstance(parents, list) or len(set(parents)) != len(parents):
        raise api.E("LINEAGE_INVALID", "parentVersionIds must be a unique list")
    for parent in parents:
        p = _load(api, root, "versions", parent)
        if p["projectId"] != project["projectId"]:
            raise api.E("LINEAGE_INVALID", "parent is missing from this project")
    if generation:
        for key in ("provider", "model", "preparedDigest", "promptDigest"):
            if not isinstance(x.get(key), str) or not x[key]:
                raise api.E("SCHEMA_INVALID", f"generation registration requires {key}")
        for key in ("preparedDigest", "promptDigest"):
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", x[key]):
                raise api.E("SCHEMA_INVALID", f"{key} must be lowercase SHA-256")
        if x["provider"] not in api.PROVIDERS or x["model"] not in api.PROVIDERS[x["provider"]]["models"]:
            raise api.E("PROVIDER_MODEL_DRIFT", "provider/model is not declared by this harness")
    existing = _version_for_hash(api, root, inspected["sha256"])
    if existing and existing["path"] == relative and existing["role"] == role:
        return {"version": existing, "registered": False, "idempotent": True}
    record = _base(api, "ver", "versionId", x["actor"])
    record.update({"assetId": _id("ast"), "projectId": project["projectId"],
                   "shotId": shot["shotId"], "role": role, "path": relative,
                   "sha256": inspected["sha256"], "bytes": inspected["bytes"],
                   "mimeType": inspected["mimeType"], "dimensions": inspected["dimensions"],
                   "alpha": None, "bitDepth": None, "iccProfile": None,
                   "parentVersionIds": parents, "qa": inspected["qa"],
                   "provenance": {k: x[k] for k in ("provider", "model", "providerRequestId",
                                  "preparedDigest", "promptDigest", "referenceHashes", "controls") if k in x}})
    _save(api, root, "versions", record)
    return {"version": record, "registered": True, "offline": True}


def _validate_brief(api, brief):
    required = {"title", "businessGoal", "audience", "message", "intendedUses",
                "deliverables", "creativeDirection", "references", "brandConstraints",
                "rightsPolicy", "privacyPolicy", "budget", "successCriteria"}
    unknown = set(brief) - required
    missing = required - set(brief)
    if unknown:
        raise api.E("UNKNOWN_FIELD", "unknown brief fields", details={"fields": sorted(unknown)})
    if missing:
        raise api.E("SCHEMA_INVALID", "missing brief fields", details={"fields": sorted(missing)})
    rp, pp, budget = brief["rightsPolicy"], brief["privacyPolicy"], brief["budget"]
    if not isinstance(rp, dict) or not all(rp.get(k) for k in ("territories", "media", "term", "realPersonPolicy", "trademarkPolicy")):
        raise api.E("RIGHTS_NOT_CLEARED", "complete rights policy is required")
    if rp["realPersonPolicy"] not in {"prohibited", "consented_only", "not_applicable"}:
        raise api.E("SCHEMA_INVALID", "invalid realPersonPolicy")
    if not isinstance(pp, dict) or pp.get("promptRetention") not in {"allowed", "redacted", "digest_only"} or not isinstance(pp.get("publicMetadata"), list):
        raise api.E("SCHEMA_INVALID", "complete privacy policy is required")
    if not isinstance(budget, dict) or budget.get("currency") != "USD":
        raise api.E("SCHEMA_INVALID", "USD budget with hard ceilings is required")
    try:
        if float(budget["projectHardCeiling"]) < 0 or float(budget["perShotHardCeiling"]) < 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise api.E("SCHEMA_INVALID", "budget hard ceilings must be non-negative decimal strings")
    if not isinstance(brief["successCriteria"], list) or not brief["successCriteria"]:
        raise api.E("SCHEMA_INVALID", "at least one success criterion is required")


def _validate_shot(api, spec, project_id):
    if not isinstance(spec, dict):
        raise api.E("SCHEMA_INVALID", "shot spec must be an object")
    unknown = set(spec) - SHOT_TOP
    missing = SHOT_REQUIRED - set(spec)
    if unknown:
        raise api.E("UNKNOWN_FIELD", "unknown shot spec fields", details={"fields": sorted(unknown)})
    if missing:
        raise api.E("SCHEMA_INVALID", "missing shot spec fields", details={"fields": sorted(missing)})
    if spec["shotSpecVersion"] != 1 or spec["projectId"] != project_id:
        raise api.E("SCHEMA_INVALID", "shotSpecVersion/projectId mismatch")
    if spec["priority"] not in {"required", "optional"}:
        raise api.E("SCHEMA_INVALID", "invalid priority")
    subject, frame, variants, plan = spec["subject"], spec["frame"], spec["variants"], spec["providerPlan"]
    if set(subject) != {"kind", "ids", "referenceIds", "releases"} or subject["kind"] not in {"product", "person", "place", "composite", "illustration"}:
        raise api.E("SCHEMA_INVALID", "invalid subject contract")
    if not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", str(frame.get("aspectRatio", ""))) or frame.get("orientation") not in {"portrait", "landscape", "square"}:
        raise api.E("SCHEMA_INVALID", "explicit aspect ratio and orientation are required")
    crop = frame.get("cropSafetyPct")
    if not isinstance(crop, dict) or set(crop) != {"top", "right", "bottom", "left"} or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 49 for v in crop.values()):
        raise api.E("SCHEMA_INVALID", "cropSafetyPct requires four percentages in [0,49]")
    if not isinstance(variants.get("requested"), int) or not 1 <= variants["requested"] <= api.MAX_COUNT or not isinstance(variants.get("maximumPaidAttempts"), int) or variants["maximumPaidAttempts"] < variants["requested"]:
        raise api.E("SCHEMA_INVALID", "invalid bounded variants")
    if plan.get("fallback") not in {"none", "fresh_approval"}:
        raise api.E("SCHEMA_INVALID", "provider fallback must be explicit")
    provider, model = plan.get("preferredProvider"), plan.get("preferredModel")
    if provider not in api.PROVIDERS or model not in api.PROVIDERS[provider]["models"]:
        raise api.E("PROVIDER_MODEL_DRIFT", "preferred provider/model is unavailable")
    unsupported = set(plan.get("requiredCapabilities", [])) - set(api.PROVIDERS[provider]["features"])
    if unsupported:
        raise api.E("UNSUPPORTED_CONTROL", "provider lacks required capabilities", details={"controls": sorted(unsupported)})
    constraints = spec["constraints"]
    if not isinstance(constraints, list):
        raise api.E("SCHEMA_INVALID", "constraints must be a list")
    for constraint in constraints:
        allowed = {"id", "scope", "rule", "severity", "evaluation", "tolerance", "referenceIds"}
        if not isinstance(constraint, dict) or set(constraint) - allowed or not {"id", "scope", "rule", "severity", "evaluation", "referenceIds"} <= set(constraint):
            raise api.E("SCHEMA_INVALID", "invalid constraint contract")
        if constraint["severity"] not in {"blocking", "major", "minor"} or constraint["evaluation"] not in {"exact", "tolerance", "human"}:
            raise api.E("SCHEMA_INVALID", "invalid constraint enum")
        if constraint["evaluation"] == "tolerance" and (not isinstance(constraint.get("tolerance"), dict) or set(constraint["tolerance"]) != {"metric", "max"}):
            raise api.E("SCHEMA_INVALID", "numeric tolerance requires metric and max")
        if constraint["scope"] in {"logo", "text"} and constraint["evaluation"] != "exact":
            raise api.E("SCHEMA_INVALID", "logo/text constraints require exact evaluation")


def _qa(api, version):
    path = Path(version["_absolutePath"])
    data = path.read_bytes()
    findings = []
    if _digest(data) != version["sha256"]:
        findings.append({"code": "HASH_MISMATCH", "severity": "blocking"})
    if not data:
        findings.append({"code": "CORRUPT_ASSET", "severity": "blocking"})
    if version["mimeType"] == "image/png":
        if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            findings.append({"code": "CORRUPT_ASSET", "severity": "blocking"})
        else:
            width, height = struct.unpack(">II", data[16:24])
            if version.get("dimensions") != {"width": width, "height": height}:
                findings.append({"code": "DIMENSION_MISMATCH", "severity": "blocking"})
    return findings


def execute(api, cmd, x, root):
    if cmd == "project.create":
        _closed(api, x, {"name", "actor"}, ("name", "actor"))
        if not isinstance(x["name"], str) or not x["name"].strip():
            raise api.E("SCHEMA_INVALID", "project name is required")
        rec = _base(api, "prj", "projectId", x["actor"])
        rec.update({"name": x["name"].strip(), "state": "intake"})
        return _save(api, root, "projects", rec)
    if cmd == "project.get":
        _closed(api, x, {"projectId"}, ("projectId",))
        return _project(api, root, x["projectId"])
    if cmd == "project.list":
        _closed(api, x, set())
        return {"items": [api.readj(p, {}) for p in sorted(_dir(root, "projects").glob("*.json"))]}
    if cmd == "brief.save":
        _closed(api, x, {"projectId", "expectedProjectRevision", "actor", "brief"}, ("projectId", "expectedProjectRevision", "actor", "brief"))
        project = _project(api, root, x["projectId"]); _expect(api, project, x["expectedProjectRevision"])
        _validate_brief(api, x["brief"])
        rec = next((v for p in sorted(_dir(root, "briefs").glob("*.json"))
                    if (v := api.readj(p, {})).get("projectId") == project["projectId"]), None)
        if rec:
            rec = _mutate(api, rec); rec.update(x["brief"]); rec["approval"] = {"status": "invalidated", "approvalId": None}
        else:
            rec = _base(api, "brf", "briefId", x["actor"]); rec.update(x["brief"]); rec.update({"projectId": project["projectId"], "approval": {"status": "draft", "approvalId": None}})
        project = _mutate(api, project); project["state"] = "brief_pending"
        _save(api, root, "projects", project); _save(api, root, "briefs", rec)
        return {"brief": rec, "project": project}
    if cmd == "brief.approve":
        _closed(api, x, {"projectId", "briefId", "expectedBriefRevision", "approver", "role"}, ("projectId", "briefId", "expectedBriefRevision", "approver", "role"))
        brief = _load(api, root, "briefs", x["briefId"]); _expect(api, brief, x["expectedBriefRevision"]); _validate_brief(api, {k: brief[k] for k in ("title", "businessGoal", "audience", "message", "intendedUses", "deliverables", "creativeDirection", "references", "brandConstraints", "rightsPolicy", "privacyPolicy", "budget", "successCriteria")})
        approval = _base(api, "apr", "approvalId", x["approver"]); approval.update({"purpose": "brief", "status": "active", "projectId": x["projectId"], "recordId": brief["briefId"], "recordRevision": brief["revision"], "reviewerRole": x["role"]})
        brief = _mutate(api, brief); brief["approval"] = {"status": "approved", "approvalId": approval["approvalId"]}
        project = _project(api, root, x["projectId"]); project = _mutate(api, project); project["state"] = "brief_approved"
        _save(api, root, "approvals", approval); _save(api, root, "briefs", brief); _save(api, root, "projects", project)
        return {"brief": brief, "approval": approval, "project": project}
    if cmd == "shot.compile":
        _closed(api, x, {"projectId", "expectedProjectRevision", "actor", "shots"}, ("projectId", "expectedProjectRevision", "actor", "shots"))
        project = _project(api, root, x["projectId"]); _expect(api, project, x["expectedProjectRevision"])
        if project["state"] != "brief_approved": raise api.E("MISSING_GATE", "approved brief required")
        if not isinstance(x["shots"], list) or not x["shots"]: raise api.E("SCHEMA_INVALID", "non-empty shots list required")
        compiled = []
        for spec in x["shots"]:
            spec = dict(spec); spec.setdefault("shotId", _id("shot")); _validate_shot(api, spec, project["projectId"])
            rec = _base(api, "shot", "_unused", x["actor"]); rec.pop("_unused"); rec.update(spec); rec["state"] = "planned"; rec["specDigest"] = _digest(spec)
            compiled.append(rec)
        if len({s["name"] for s in compiled}) != len(compiled): raise api.E("SCHEMA_INVALID", "shot names must be unique")
        for rec in compiled: _save(api, root, "shots", rec)
        return {"items": compiled, "shotListDigest": _digest([s["specDigest"] for s in compiled])}
    if cmd == "shot.list":
        _closed(api, x, {"projectId"}, ("projectId",))
        return {"items": [v for p in sorted(_dir(root, "shots").glob("*.json")) if (v := api.readj(p, {})).get("projectId") == x["projectId"]]}
    if cmd in {"candidate.register", "generation.register"}:
        return _register(api, root, x, cmd == "generation.register")
    if cmd == "qa.evaluate":
        _closed(api, x, {"versionId", "actor"}, ("versionId", "actor"))
        version = _load(api, root, "versions", x["versionId"]); path = root / version["path"]
        if not path.is_file() or path.is_symlink(): raise api.E("CORRUPT_ASSET", "registered asset is unavailable")
        work = dict(version); work["_absolutePath"] = str(path); findings = _qa(api, work)
        rec = _base(api, "qa", "qaId", x["actor"]); rec.update({"versionId": version["versionId"], "assetSha256": version["sha256"], "checksVersion": "technical-v1", "findings": findings, "passed": not any(f["severity"] == "blocking" for f in findings)})
        return _save(api, root, "qa", rec)
    if cmd == "critic.input":
        _closed(api, x, {"versionId", "qaId", "rubric", "actor"}, ("versionId", "qaId", "rubric", "actor"))
        version = _load(api, root, "versions", x["versionId"]); qa = _load(api, root, "qa", x["qaId"])
        if qa["assetSha256"] != version["sha256"]: raise api.E("HASH_MISMATCH", "QA does not bind this asset")
        rubric = x["rubric"]
        if not isinstance(rubric, dict) or set(rubric) != {"rubricId", "revision", "dimensions", "scoreScale", "pass"}: raise api.E("SCHEMA_INVALID", "strict rubric contract required")
        dimensions = rubric["dimensions"]
        if not isinstance(dimensions, list) or abs(sum(float(d.get("weight", 0)) for d in dimensions)-1.0) > 1e-9: raise api.E("SCHEMA_INVALID", "rubric weights must sum to 1.0")
        rec = _base(api, "crit", "criticInputId", x["actor"]); rec.update({"projectId": version["projectId"], "shotId": version["shotId"], "versionId": version["versionId"], "assetSha256": version["sha256"], "qaId": qa["qaId"], "technicalBlockers": qa["findings"], "rubric": rubric, "humanGates": ["identity", "product_truth", "regulated_claims", "brand_critical", "creative", "rights"], "advisoryOnly": True})
        rec["inputDigest"] = _digest({k: v for k, v in rec.items() if k not in {"createdAt", "updatedAt", "revision", "actor", "criticInputId", "inputDigest"}})
        return _save(api, root, "critics", rec)
    if cmd == "select.record":
        _closed(api, x, {"versionId", "expectedShotRevision", "reviewer", "role", "reason"}, ("versionId", "expectedShotRevision", "reviewer", "role", "reason"))
        version = _load(api, root, "versions", x["versionId"]); shot = _load(api, root, "shots", version["shotId"]); _expect(api, shot, x["expectedShotRevision"])
        rec = _base(api, "sel", "selectionId", x["reviewer"]); rec.update({"projectId": version["projectId"], "shotId": version["shotId"], "versionId": version["versionId"], "assetSha256": version["sha256"], "reviewerRole": x["role"], "decision": "selected", "reason": x["reason"]})
        shot = _mutate(api, shot); shot["state"] = "selected"; _save(api, root, "shots", shot); _save(api, root, "selections", rec)
        return {"selection": rec, "shot": shot}
    if cmd == "revision.plan":
        allowed = {"baseVersionId", "selectionId", "objective", "preserve", "issues", "order", "maximumPaidOperations", "approvalImpact", "actor"}
        _closed(api, x, allowed, allowed)
        version = _load(api, root, "versions", x["baseVersionId"]); selection = _load(api, root, "selections", x["selectionId"])
        if selection["assetSha256"] != version["sha256"]: raise api.E("HASH_MISMATCH", "selection and base version differ")
        if not isinstance(x["issues"], list) or not x["issues"]: raise api.E("SCHEMA_INVALID", "revision issues required")
        issue_ids = [i.get("issueId") for i in x["issues"]]
        if x["order"] != issue_ids or any(i.get("operation") not in {"local_edit", "composite", "color_adjust", "metadata", "export", "regenerate"} for i in x["issues"]): raise api.E("SCHEMA_INVALID", "issues/order must be explicit and complete")
        rec = _base(api, "rev", "revisionPlanId", x["actor"]); rec.update({k: x[k] for k in allowed if k != "actor"}); rec.update({"baseSha256": version["sha256"], "projectId": version["projectId"], "shotId": version["shotId"], "round": 1, "status": "open"})
        return _save(api, root, "revisions", rec)
    if cmd == "finish.record":
        _closed(api, x, {"baseVersionId", "path", "recipe", "actor"}, ("baseVersionId", "path", "recipe", "actor"))
        base = _load(api, root, "versions", x["baseVersionId"])
        result = _register(api, root, {"projectId": base["projectId"], "shotId": base["shotId"], "path": x["path"], "role": "editable_master", "parentVersionIds": [base["versionId"]], "actor": x["actor"]})
        if result["version"]["sha256"] == base["sha256"]: raise api.E("NONDETERMINISTIC_OUTPUT", "finish must create distinct immutable bytes")
        rec = _base(api, "fin", "finishId", x["actor"]); rec.update({"projectId": base["projectId"], "shotId": base["shotId"], "inputVersionId": base["versionId"], "inputSha256": base["sha256"], "outputVersionId": result["version"]["versionId"], "outputSha256": result["version"]["sha256"], "recipe": x["recipe"], "recipeDigest": _digest(x["recipe"]), "nonDestructive": True})
        return _save(api, root, "finishes", rec)
    if cmd == "master.approve":
        _closed(api, x, {"versionId", "approver", "role", "proofCondition"}, ("versionId", "approver", "role", "proofCondition"))
        version = _load(api, root, "versions", x["versionId"])
        if version["role"] != "editable_master": raise api.E("MISSING_GATE", "editable master required")
        qa_records = [api.readj(p, {}) for p in _dir(root, "qa").glob("*.json")]
        if not any(q.get("assetSha256") == version["sha256"] and q.get("passed") for q in qa_records): raise api.E("MISSING_GATE", "passing hash-bound technical QA required")
        rec = _base(api, "apr", "approvalId", x["approver"]); rec.update({"purpose": "master", "status": "active", "projectId": version["projectId"], "shotId": version["shotId"], "versionId": version["versionId"], "assetSha256": version["sha256"], "recordRevision": version["revision"], "proofCondition": x["proofCondition"], "reviewerRole": x["role"]})
        return _save(api, root, "approvals", rec)
    if cmd == "contact_sheet.create":
        _closed(api, x, {"projectId", "versionIds", "columns", "actor"}, ("projectId", "versionIds", "columns", "actor"))
        versions = [_load(api, root, "versions", v) for v in x["versionIds"]]
        if not versions or any(v["projectId"] != x["projectId"] for v in versions) or not isinstance(x["columns"], int) or not 1 <= x["columns"] <= 8: raise api.E("SCHEMA_INVALID", "valid project versions and 1-8 columns required")
        versions.sort(key=lambda v: (v["shotId"], v["versionId"]))
        manifest = {"schemaVersion": 1, "projectId": x["projectId"], "rendererVersion": "svg-contact-v1", "colorLimitation": "review proxy; not delivery master", "items": [{"shotId": v["shotId"], "versionId": v["versionId"], "sha256": v["sha256"], "mimeType": v["mimeType"], "dimensions": v["dimensions"], "provider": v["provenance"].get("provider"), "model": v["provenance"].get("model")} for v in versions], "columns": x["columns"]}
        digest = _digest(manifest); out_dir = _dir(root, "contact-artifacts"); stem = digest[7:]
        labels = "".join(f'<text x="20" y="{45+i*34}" font-size="14">{i+1}. {v["shotId"]} {v["sha256"][7:19]} REVIEW PROXY</text>' for i, v in enumerate(versions))
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{100+34*len(versions)}"><rect width="100%" height="100%" fill="#eee"/><text x="20" y="22">NOT DELIVERY MASTER — COLOR LIMITED</text>{labels}</svg>'.encode()
        api.atomic_bytes(out_dir/(stem+".svg"), svg); api.atomic(out_dir/(stem+".manifest.json"), manifest)
        rec = _base(api, "cs", "contactSheetId", x["actor"]); rec.update({"projectId": x["projectId"], "manifestDigest": digest, "manifestPath": str((out_dir/(stem+".manifest.json")).relative_to(root)), "path": str((out_dir/(stem+".svg")).relative_to(root)), "sourceHashes": [v["sha256"] for v in versions], "rendererVersion": "svg-contact-v1"})
        return _save(api, root, "contacts", rec)
    if cmd == "delivery.prepare":
        _closed(api, x, {"projectId", "versionIds", "destination", "external", "actor"}, ("projectId", "versionIds", "destination", "external", "actor"))
        versions = [_load(api, root, "versions", v) for v in x["versionIds"]]
        approvals = [api.readj(p, {}) for p in _dir(root, "approvals").glob("*.json")]
        items = []
        for v in sorted(versions, key=lambda z: (z["shotId"], z["versionId"])):
            approval = next((a for a in approvals if a.get("purpose") == "master" and a.get("assetSha256") == v["sha256"] and a.get("status") == "active"), None)
            if not approval: raise api.E("MISSING_GATE", "active hash-bound master approval required", details={"versionId": v["versionId"]})
            path = root/v["path"]
            if not path.is_file() or _digest(path.read_bytes()) != v["sha256"]: raise api.E("HASH_MISMATCH", "delivery source bytes changed")
            items.append({k: v.get(k) for k in ("projectId", "shotId", "versionId", "path", "sha256", "bytes", "mimeType", "dimensions", "iccProfile", "provenance")} | {"approvalId": approval["approvalId"]})
        manifest = {"schemaVersion": 1, "projectId": x["projectId"], "destination": x["destination"], "external": x["external"], "items": items}
        digest = _digest(manifest); out_dir = _dir(root, "delivery-artifacts"); mp = out_dir/(digest[7:]+".manifest.json"); api.atomic(mp, manifest)
        rec = _base(api, "del", "deliveryId", x["actor"]); rec.update({"projectId": x["projectId"], "status": "prepared", "manifestDigest": digest, "manifestPath": str(mp.relative_to(root)), "destination": x["destination"], "external": x["external"], "itemCount": len(items)})
        return _save(api, root, "deliveries", rec)
    if cmd == "delivery.package":
        _closed(api, x, {"deliveryId", "manifestDigest", "durableRoot", "publicationApprovalId", "actor"}, ("deliveryId", "manifestDigest", "durableRoot", "actor"))
        delivery = _load(api, root, "deliveries", x["deliveryId"])
        if delivery["manifestDigest"] != x["manifestDigest"]: raise api.E("HASH_MISMATCH", "delivery manifest digest changed")
        if delivery["external"] and not x.get("publicationApprovalId"): raise api.E("PUBLICATION_APPROVAL_REQUIRED", "external delivery needs separate publication approval")
        durable = Path(x["durableRoot"]).expanduser().resolve()
        if not durable.is_dir() or durable.is_symlink(): raise api.E("DURABLE_ROOT_UNAVAILABLE", "durable root must already exist")
        manifest = api.readj(root/delivery["manifestPath"], None)
        if not manifest or _digest(manifest) != delivery["manifestDigest"]: raise api.E("HASH_MISMATCH", "manifest file changed")
        target = durable/(delivery["manifestDigest"][7:]+".zip")
        if target.exists():
            return {"delivery": delivery, "packagePath": str(target), "packageSha256": _digest(target.read_bytes()), "idempotent": True}
        fd, tmp = tempfile.mkstemp(dir=durable, prefix=".studio-"); os.close(fd)
        try:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as z:
                def add(name, data):
                    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); info.external_attr = 0o600 << 16; z.writestr(info, data)
                add("manifest.json", (_stable(manifest)+"\n").encode())
                for i, item in enumerate(manifest["items"]): add(f"assets/{i+1:03d}-{Path(item['path']).name}", (root/item["path"]).read_bytes())
            os.replace(tmp, target)
        finally:
            try: os.unlink(tmp)
            except FileNotFoundError: pass
        delivery = _mutate(api, delivery); delivery.update({"status": "packaged", "packagePath": str(target), "packageSha256": _digest(target.read_bytes()), "publicationApprovalId": x.get("publicationApprovalId")})
        _save(api, root, "deliveries", delivery)
        return {"delivery": delivery, "packagePath": str(target), "packageSha256": delivery["packageSha256"], "idempotent": False}
    if cmd == "audit.verify":
        _closed(api, x, {"projectId"}, ("projectId",)); _project(api, root, x["projectId"])
        counts = {}; findings = []
        for kind in ("shots", "versions", "qa", "critics", "selections", "revisions", "finishes", "approvals", "contacts", "deliveries"):
            records = [api.readj(p, {}) for p in _dir(root, kind).glob("*.json")]
            records = [r for r in records if r.get("projectId") == x["projectId"]]
            counts[kind] = len(records)
            if kind == "versions":
                for v in records:
                    path = root/v["path"]
                    if not path.is_file() or _digest(path.read_bytes()) != v["sha256"]: findings.append({"code": "HASH_MISMATCH", "versionId": v["versionId"], "severity": "blocking"})
                    for parent in v["parentVersionIds"]:
                        try: _load(api, root, "versions", parent)
                        except api.E: findings.append({"code": "LINEAGE_INVALID", "versionId": v["versionId"], "severity": "blocking"})
        return {"projectId": x["projectId"], "counts": counts, "findings": findings, "blocking": sum(f["severity"] == "blocking" for f in findings), "valid": not findings}
    raise api.E("INVALID_COMMAND", "unknown professional studio command")
