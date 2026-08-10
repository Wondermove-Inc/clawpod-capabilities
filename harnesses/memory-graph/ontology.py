"""Memory Graph v0.8 deterministic assertion ontology, no I/O or network."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ASSERTION_SCHEMA_VERSION = "memory-graph-assertions/v1"
ASSERTION_SHAPE_VERSION = "memory-graph-ontology-shapes/v1"
ASSERTION_CONTRACT_VERSION = "0.8"
STATUSES = {"candidate", "approved", "rejected", "superseded", "quarantined"}
METHODS = {"explicit", "extracted_candidate", "human_approved"}
PRECISIONS = {"instant", "day", "month", "year", "unknown"}
ENDPOINTS = {
    "participates_in": ({"Person"}, {"Project", "Event"}),
    "decided": ({"Person"}, {"Decision"}),
    "caused": ({"Decision", "Event"}, {"Event"}),
    "supersedes": ({"Decision", "Event", "Project"}, {"Decision", "Event", "Project"}),
}
HASH_KEYS = ("source_content_hash", "claim_content_hash", "evidence_excerpt_hash")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def assertion_id(namespace: str, item: dict[str, Any]) -> str:
    source, extractor = item["source"], item.get("extractor")
    identity = [namespace, item["subject"]["type"], item["subject"]["entity_id"], item["predicate"],
        item["object"]["type"], item["object"]["entity_id"], item["source_claim_id"], source["path"],
        source["line_start"], source["line_end"], *(source[k] for k in HASH_KEYS), item["method"],
        digest(extractor) if extractor is not None else ""]
    return "as_" + digest(identity)


def quarantine(reason: str, item: Any) -> dict[str, Any]:
    safe_hash = digest(item)
    result = {"assertion_id": item.get("assertion_id", "as_" + safe_hash) if isinstance(item, dict) else "as_" + safe_hash,
        "reason_code": reason, "safe_input_hash": safe_hash}
    if isinstance(item, dict):
        result["source_claim_id"] = item.get("source_claim_id", "")
        if isinstance(item.get("source"), dict):
            result["locator"] = {k: item["source"].get(k) for k in ("path", "line_start", "line_end")}
    return result


def timestamp(value: Any) -> bool:
    if not isinstance(value, str) or "T" not in value or not (value.endswith("Z") or "+" in value[10:] or "-" in value[10:]): return False
    try: return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError: return False


def temporal(value: Any) -> bool:
    if value is None: return True
    if not isinstance(value, dict) or set(value) != {"start", "end", "precision", "timezone"}: return False
    if value["precision"] not in PRECISIONS or not isinstance(value["timezone"], str): return False
    try: ZoneInfo(value["timezone"])
    except (ZoneInfoNotFoundError, ValueError, TypeError): return False
    values = []
    for key in ("start", "end"):
        if value[key] is None: values.append(None); continue
        if not timestamp(value[key]): return False
        try: values.append(datetime.fromisoformat(value[key].replace("Z", "+00:00")))
        except ValueError: return False
    if value["start"] is None and value["end"] is not None: return False
    return not (values[0] is not None and values[1] is not None and values[0] > values[1])


def shape_reason(item: Any, hash_re: Any, id_re: Any, secret_like: Callable[[Any], bool]) -> str | None:
    required = {"assertion_id", "subject", "predicate", "object", "source_claim_id", "source", "method",
        "asserted_at", "valid_time", "status", "review", "extractor", "confidence"}
    if not isinstance(item, dict) or set(item) != required: return "invalid_assertion_shape"
    epkeys = {"entity_id", "type"}
    for ep in (item["subject"], item["object"]):
        if not isinstance(ep, dict) or set(ep) != epkeys or not all(isinstance(ep[k], str) and ep[k] for k in epkeys): return "invalid_assertion_shape"
    if item["predicate"] not in ENDPOINTS: return "unknown_predicate"
    domains, ranges = ENDPOINTS[item["predicate"]]
    if item["subject"]["type"] not in domains or item["object"]["type"] not in ranges: return "invalid_endpoint_type"
    if item["predicate"] == "supersedes" and item["subject"]["type"] != item["object"]["type"]: return "invalid_endpoint_type"
    if item["subject"] == item["object"]: return "self_relation"
    if not isinstance(item["source_claim_id"], str) or not id_re.fullmatch(item["source_claim_id"]): return "invalid_assertion_shape"
    source = item["source"]
    if (not isinstance(source, dict) or set(source) != {"path", "line_start", "line_end", *HASH_KEYS}
            or not isinstance(source["path"], str) or source["path"].startswith("/") or ".." in Path(source["path"]).parts
            or not isinstance(source["line_start"], int) or not isinstance(source["line_end"], int)
            or source["line_start"] < 1 or source["line_end"] < source["line_start"]
            or not all(isinstance(source[k], str) and hash_re.fullmatch(source[k]) for k in HASH_KEYS)): return "invalid_source_shape"
    if item["method"] not in METHODS or item["status"] not in STATUSES or not timestamp(item["asserted_at"]): return "invalid_lifecycle"
    review, extractor, confidence = item["review"], item["extractor"], item["confidence"]
    if review is not None and (not isinstance(review, dict) or set(review) != {"reviewer_id", "reviewed_at", "review_reason"}
            or not all(isinstance(review[k], str) and review[k] for k in review) or not timestamp(review["reviewed_at"])): return "invalid_lifecycle"
    if extractor is not None and (not isinstance(extractor, dict) or set(extractor) != {"extractor_id", "extractor_version", "config_hash"}
            or not isinstance(extractor["extractor_id"], str) or not isinstance(extractor["extractor_version"], str)
            or not isinstance(extractor["config_hash"], str) or not hash_re.fullmatch(extractor["config_hash"])): return "invalid_lifecycle"
    if item["method"] == "extracted_candidate":
        if extractor is None or not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not math.isfinite(confidence) or not 0 <= confidence <= 1: return "invalid_confidence"
        if item["status"] not in {"candidate", "rejected", "quarantined"}: return "invalid_lifecycle"
    elif extractor is not None or confidence is not None: return "invalid_lifecycle"
    if item["method"] == "human_approved" and review is None: return "missing_review"
    if item["method"] == "explicit" and (review is not None or item["status"] not in {"approved", "quarantined", "superseded"}): return "invalid_lifecycle"
    if item["status"] == "approved" and item["method"] == "extracted_candidate": return "invalid_lifecycle"
    if item["predicate"] == "caused" and (item["method"] != "human_approved" or item["status"] != "approved" or review is None): return "causality_requires_human_approval"
    if item["predicate"] == "caused" and review is not None and review.get("review_reason") != "direct_causal_statement": return "causality_not_direct"
    if not temporal(item["valid_time"]): return "invalid_temporal_shape"
    if secret_like(item): return "secret_like_assertion"
    return None


def validate_bundle(root: Path, bundle: Any, agent_id: str, workspace_id: str | None, api: dict[str, Any]) -> dict[str, Any]:
    allowed = {"schema_version", "semantic_contract_version", "namespace", "source_snapshot_hash", "source_digest", "assertions", "identity_candidates"}
    if not isinstance(bundle, dict) or set(bundle) - allowed or set(bundle) < allowed - {"identity_candidates"}: raise api["error"]("invalid_assertion_bundle", "Assertion bundle has an invalid closed shape")
    if bundle.get("schema_version") != ASSERTION_SCHEMA_VERSION or bundle.get("semantic_contract_version") != ASSERTION_CONTRACT_VERSION: raise api["error"]("invalid_assertion_bundle", "Assertion schema or contract version is unsupported")
    if not isinstance(bundle["assertions"], list) or len(bundle["assertions"]) > 256: raise api["error"]("invalid_assertion_bundle", "assertions must be a bounded array")
    inspected = api["inspect"](root); ownership = api["namespace"](agent_id, root, workspace_id); snapshot = api["plan"](inspected, False, ownership)
    if bundle["namespace"] != ownership["namespace"]: raise api["error"]("namespace_mismatch", "Assertion namespace does not match ownership")
    if bundle["source_snapshot_hash"] != snapshot["snapshot_hash"] or bundle["source_digest"] != snapshot["source_digest"]: raise api["error"]("stale_provenance", "Bundle does not match fresh canonical snapshot")
    entities = {}
    for entity in snapshot["entities"]:
        if entity.get("entityType") in api["semantic_types"] and ":semantic:" in entity.get("name", ""):
            obs = json.loads(entity["observations"][0]); entities[(entity["entityType"], obs["entity_id"])] = entity["name"]
    claims = {x["claim_id"]: x for x in snapshot["claims"]}; sources = {x["path"]: x for x in inspected["sources"]}
    accepted, rejected, seen = [], [], {}
    for item in bundle["assertions"]:
        reason = shape_reason(item, api["hash_re"], api["id_re"], api["secret_like"])
        if reason is None and item["assertion_id"] != assertion_id(ownership["namespace"], item): reason = "id_mismatch"
        if reason is None and item["assertion_id"] in seen and seen[item["assertion_id"]] != canonical_bytes(item): raise api["error"]("conflicting_assertions", "One assertion ID identifies differing content")
        if reason is None: seen[item["assertion_id"]] = canonical_bytes(item)
        claim = claims.get(item.get("source_claim_id")) if isinstance(item, dict) else None; source = item.get("source", {}) if isinstance(item, dict) else {}
        if reason is None and claim is None: reason = "ineligible_claim"
        if reason is None and ((item["subject"]["type"], item["subject"]["entity_id"]) not in entities or (item["object"]["type"], item["object"]["entity_id"]) not in entities): reason = "dangling_endpoint"
        if reason is None and (source["path"] != claim["path"] or source["claim_content_hash"] != claim["content_hash"] or source["source_content_hash"] != sources.get(source["path"], {}).get("hash")): reason = "stale_provenance"
        evidence = {e.get("content_hash") for e in claim.get("evidence", []) if isinstance(e, dict)} if claim else set()
        if reason is None and source["evidence_excerpt_hash"] not in evidence: reason = "evidence_hash_mismatch"
        if reason is None and source["line_start"] != claim["line"]: reason = "stale_provenance"
        if reason: rejected.append(quarantine(reason, item)); continue
        value = json.loads(canonical_bytes(item)); value.update({"canonical": item["method"] == "explicit", "locator_only": True, "rehydration_required": True,
            "subject_name": entities[(item["subject"]["type"], item["subject"]["entity_id"])], "object_name": entities[(item["object"]["type"], item["object"]["entity_id"])]}); accepted.append(value)
    # Supersession is explicit but must still be acyclic within a validated bundle.
    supersedes = [(x["subject"]["entity_id"], x["object"]["entity_id"], x["assertion_id"]) for x in accepted if x["predicate"] == "supersedes"]
    graph: dict[str, set[str]] = {}
    for left, right, _ in supersedes: graph.setdefault(left, set()).add(right)
    def cyclic(start: str) -> bool:
        stack = [(start, iter(graph.get(start, ())))]; active = {start}
        while stack:
            node, children = stack[-1]
            try: child = next(children)
            except StopIteration: active.remove(node); stack.pop(); continue
            if child in active: return True
            stack.append((child, iter(graph.get(child, ())))); active.add(child)
        return False
    cycle_ids = {aid for left, _, aid in supersedes if cyclic(left)}
    if cycle_ids:
        rejected.extend(quarantine("supersession_cycle", x) for x in accepted if x["assertion_id"] in cycle_ids)
        accepted = [x for x in accepted if x["assertion_id"] not in cycle_ids]
    accepted = sorted({x["assertion_id"]: x for x in accepted}.values(), key=lambda x: x["assertion_id"])
    identity = bundle.get("identity_candidates", []); safe_identity = []
    if not isinstance(identity, list) or len(identity) > 256: raise api["error"]("invalid_identity_candidates", "identity_candidates must be a bounded array")
    epkeys = {"entity_id", "type"}
    for candidate in identity:
        keys = {"candidate_id", "left", "right", "feature_codes", "score", "method", "version", "config_hash", "source_claim_ids"}
        endpoints_ok = isinstance(candidate, dict) and all(isinstance(candidate.get(k), dict) and set(candidate[k]) == epkeys for k in ("left", "right"))
        endpoint_values = endpoints_ok and all((ep["type"], ep["entity_id"]) in entities for ep in (candidate["left"], candidate["right"]))
        feature_ok = isinstance(candidate, dict) and isinstance(candidate.get("feature_codes"), list) and candidate["feature_codes"] and all(isinstance(x, str) and api["id_re"].fullmatch(x) for x in candidate["feature_codes"])
        claims_ok = isinstance(candidate, dict) and isinstance(candidate.get("source_claim_ids"), list) and candidate["source_claim_ids"] and all(x in claims for x in candidate["source_claim_ids"])
        score = candidate.get("score") if isinstance(candidate, dict) else None
        if (not isinstance(candidate, dict) or set(candidate) != keys or api["secret_like"](candidate)
                or not isinstance(candidate.get("candidate_id"), str) or not api["id_re"].fullmatch(candidate["candidate_id"])
                or not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(score) or not 0 <= score <= 1
                or not endpoints_ok or not endpoint_values or candidate["left"] == candidate["right"]
                or candidate["left"]["type"] != candidate["right"]["type"] or not feature_ok or not claims_ok
                or not isinstance(candidate.get("method"), str) or not candidate["method"]
                or not isinstance(candidate.get("version"), str) or not candidate["version"]
                or not isinstance(candidate.get("config_hash"), str) or not api["hash_re"].fullmatch(candidate["config_hash"])):
            rejected.append(quarantine("invalid_identity_candidate", candidate)); continue
        safe_identity.append({**candidate, "status": "candidate", "auto_merge": False, "projected": False})
    rejected.sort(key=lambda x: (x["reason_code"], x.get("source_claim_id", ""), x["assertion_id"]))
    report = {"conforms": not rejected, "shape_version": ASSERTION_SHAPE_VERSION, "namespace": ownership["namespace"], "source_snapshot_hash": snapshot["snapshot_hash"], "source_digest": snapshot["source_digest"], "accepted_assertions": accepted, "quarantine": rejected, "identity_candidates": sorted(safe_identity, key=lambda x: x["candidate_id"])}
    report["report_hash"] = digest(report); return report


def review_queue(validated: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": "memory-graph-review-queue/v1", "namespace": validated["namespace"], "candidates": [x for x in validated["accepted_assertions"] if x["status"] == "candidate"], "identity_candidates": validated["identity_candidates"], "quarantine": validated["quarantine"], "mutation_performed": False}


def semantic_view(validated: dict[str, Any], include_candidates: bool = False) -> dict[str, Any]:
    def edge(item: dict[str, Any], label: str, style: str) -> dict[str, Any]:
        return {"assertion_id": item["assertion_id"], "from": item["subject_name"], "to": item["object_name"], "predicate": item["predicate"], "label": label, "style": style, "status": item["status"], "method": item["method"], "valid_time": item["valid_time"], "why_this_edge": {"source_claim_id": item["source_claim_id"], **item["source"]}, "canonical": item["canonical"], "locator_only": True, "rehydration_required": True}
    approved = [edge(x, "Approved explicit", "solid") for x in validated["accepted_assertions"] if x["status"] == "approved"][:200]
    candidates = [edge(x, "Candidate, noncanonical", "dashed") for x in validated["accepted_assertions"] if include_candidates and x["status"] == "candidate"][:max(0, 200 - len(approved))]
    result = {"schema_version": "memory-graph-semantic-view/v1", "namespace": validated["namespace"], "view_types": ["path", "ego", "timeline"], "structural_relations": [], "nodes": sorted({e[k] for e in approved + candidates for k in ("from", "to")}), "approved_assertions": approved, "candidate_assertions": candidates, "legends": [{"label":"Approved explicit","style":"solid"},{"label":"Candidate, noncanonical","style":"dashed"}], "canonical_grounding_required": True}
    result["view_hash"] = digest(result); return result


def cq_evaluate(validated: dict[str, Any]) -> dict[str, Any]:
    approved = [x for x in validated["accepted_assertions"] if x["status"] == "approved"]; predicates = sorted({x["predicate"] for x in approved}); caused = [x for x in approved if x["predicate"] == "caused"]
    locators = all(x["source"].get("path") and x["source"].get("line_start") and all(len(x["source"][k]) == 64 for k in HASH_KEYS) for x in approved)
    checks = {"CQ1": any(x["predicate"] == "decided" for x in approved), "CQ2": bool(caused) and all(x["method"] == "human_approved" and x["review"]["review_reason"] == "direct_causal_statement" for x in caused), "CQ3": any(x["predicate"] == "supersedes" for x in approved), "CQ4": any(x["predicate"] == "participates_in" for x in approved) and all(temporal(x["valid_time"]) for x in approved), "CQ5": locators}
    metrics = {"approved_assertion_count": len(approved), "represented_predicates": predicates, "unsupported_approved_edge_count": 0, "locator_completeness": 1.0 if locators else 0.0, "cq_pass_count": sum(checks.values())}
    gates = {"A": len(approved) >= 12 and len(predicates) >= 3, "B": locators and not validated["quarantine"] and all(checks.values())}
    result = {"schema_version":"memory-graph-cq-evaluation/v1","namespace":validated["namespace"],"competency_questions":checks,"metrics":metrics,"gates":gates,"passed":all(gates.values())}; result["evaluation_hash"] = digest(result); return result
