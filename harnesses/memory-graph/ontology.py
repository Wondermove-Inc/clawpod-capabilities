"""Memory Graph v0.9 deterministic private entity proposals and assertions.

This module performs bounded local validation only. It does not mutate canonical sources,
call a model, use a network, MCP, or a live graph.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ASSERTION_SCHEMA_VERSION = "memory-graph-assertions/v2"
LEGACY_ASSERTION_SCHEMA_VERSION = "memory-graph-assertions/v1"
ASSERTION_SHAPE_VERSION = "memory-graph-ontology-shapes/v2"
ASSERTION_CONTRACT_VERSION = "0.9"
STATUSES = {"candidate", "approved", "rejected", "superseded", "quarantined"}
METHODS = {"explicit", "extracted_candidate", "human_approved"}
PRECISIONS = {"instant", "day", "month", "year", "unknown"}
ENTITY_TYPES = {"Person", "Project", "Decision", "Event"}
ENDPOINTS = {
    "participates_in": ({"Person"}, {"Project", "Event"}),
    "decided": ({"Person"}, {"Decision"}),
    "caused": ({"Decision", "Event"}, {"Event"}),
    "supersedes": ({"Decision", "Event", "Project"}, {"Decision", "Event", "Project"}),
}
HASH_KEYS = ("source_content_hash", "claim_content_hash", "evidence_excerpt_hash")
PROPOSAL_HASH_KEYS = ("source_content_hash", "claim_content_hash")


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


def entity_proposal_id(namespace: str, item: dict[str, Any]) -> str:
    source, extractor = item["source"], item["extractor"]
    identity = [namespace, item["entity"]["type"], item["entity"]["entity_id"], item["source_claim_id"],
        source["path"], source["line_start"], source["line_end"], *(source[k] for k in PROPOSAL_HASH_KEYS),
        extractor["extractor_id"], extractor["extractor_version"], extractor["config_hash"], item["temporal"]]
    return "ep_" + digest(identity)


def _safe_record(reason: str, item: Any, kind: str = "assertion") -> dict[str, Any]:
    safe_hash = digest(item)
    key = "entity_proposal_id" if kind == "entity_proposal" else "assertion_id"
    prefix = "ep_" if kind == "entity_proposal" else "as_"
    if reason.startswith("secret_like_"):
        return {key: prefix + safe_hash, "reason_code": reason, "safe_input_hash": safe_hash,
                "record_kind": kind, "redacted": True}
    result = {key: item.get(key, prefix + safe_hash) if isinstance(item, dict) else prefix + safe_hash,
              "reason_code": reason, "safe_input_hash": safe_hash, "record_kind": kind}
    if isinstance(item, dict):
        result["source_claim_id"] = item.get("source_claim_id", "")
        if isinstance(item.get("source"), dict):
            result["locator"] = {k: item["source"].get(k) for k in ("path", "line_start", "line_end")}
    return result


def quarantine(reason: str, item: Any) -> dict[str, Any]:
    return _safe_record(reason, item)


def timestamp(value: Any) -> bool:
    if not isinstance(value, str) or "T" not in value or not (value.endswith("Z") or "+" in value[10:] or "-" in value[10:]): return False
    try: return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError: return False


def temporal(value: Any) -> bool:
    if value is None: return True
    if not isinstance(value, dict) or set(value) != {"start", "end", "precision", "timezone"}: return False
    if value["precision"] not in PRECISIONS or not isinstance(value["timezone"], str): return False
    if value["precision"] == "unknown": return value["start"] is None and value["end"] is None and value["timezone"] == "unknown"
    try: ZoneInfo(value["timezone"])
    except (ZoneInfoNotFoundError, ValueError, TypeError): return False
    values = []
    for key in ("start", "end"):
        if value[key] is None: values.append(None); continue
        if not timestamp(value[key]): return False
        values.append(datetime.fromisoformat(value[key].replace("Z", "+00:00")))
    if value["start"] is None or (values[1] is not None and values[0] > values[1]): return False
    return True


def _source_reason(source: Any, required_hashes: tuple[str, ...], hash_re: Any) -> str | None:
    keys = {"path", "line_start", "line_end", *required_hashes}
    if not isinstance(source, dict) or set(source) != keys: return "invalid_source_shape"
    path = source.get("path")
    if not isinstance(path, str) or path.startswith("/") or ".." in Path(path).parts: return "path_escape"
    if not isinstance(source["line_start"], int) or isinstance(source["line_start"], bool) or not isinstance(source["line_end"], int) or source["line_start"] < 1 or source["line_end"] < source["line_start"]: return "invalid_source_shape"
    if not all(isinstance(source[k], str) and hash_re.fullmatch(source[k]) for k in required_hashes): return "invalid_source_shape"
    return None


def _review_ok(review: Any) -> bool:
    return (isinstance(review, dict) and set(review) == {"reviewer_id", "reviewed_at", "review_reason"}
            and all(isinstance(review[k], str) and review[k] for k in review) and timestamp(review["reviewed_at"]))


def _extractor_ok(extractor: Any, hash_re: Any) -> bool:
    return (isinstance(extractor, dict) and set(extractor) == {"extractor_id", "extractor_version", "config_hash"}
            and isinstance(extractor["extractor_id"], str) and bool(extractor["extractor_id"])
            and isinstance(extractor["extractor_version"], str) and bool(extractor["extractor_version"])
            and isinstance(extractor["config_hash"], str) and bool(hash_re.fullmatch(extractor["config_hash"])))


def proposal_shape_reason(item: Any, namespace: str, hash_re: Any, id_re: Any, secret_like: Callable[[Any], bool]) -> str | None:
    required = {"entity_proposal_id", "namespace", "entity", "source_claim_id", "source", "extractor", "status", "review", "temporal"}
    if not isinstance(item, dict) or set(item) != required: return "invalid_entity_proposal_shape"
    if item["namespace"] != namespace: return "cross_namespace_entity"
    entity = item["entity"]
    if not isinstance(entity, dict) or set(entity) != {"entity_id", "type"}: return "invalid_entity_proposal_shape"
    if entity.get("type") not in ENTITY_TYPES: return "invalid_entity_type"
    if not isinstance(entity.get("entity_id"), str) or not id_re.fullmatch(entity["entity_id"]): return "invalid_entity_id"
    expected_prefix = entity["type"].lower() + ":"
    if not entity["entity_id"].startswith(expected_prefix): return "invalid_entity_id"
    if not isinstance(item["source_claim_id"], str) or not id_re.fullmatch(item["source_claim_id"]): return "invalid_entity_proposal_shape"
    reason = _source_reason(item["source"], PROPOSAL_HASH_KEYS, hash_re)
    if reason: return reason
    if not _extractor_ok(item["extractor"], hash_re): return "invalid_extractor"
    if item["status"] not in STATUSES: return "invalid_lifecycle"
    if item["status"] == "candidate" and item["review"] is not None: return "invalid_lifecycle"
    if item["status"] == "approved" and not _review_ok(item["review"]): return "missing_review"
    if item["status"] == "approved" and item["review"]["review_reason"] != "claim_explicitly_identifies_entity": return "invalid_review"
    if item["review"] is not None and not _review_ok(item["review"]): return "invalid_review"
    if entity["type"] in {"Person", "Project"} and item["temporal"] is not None: return "invalid_temporal_shape"
    if entity["type"] in {"Decision", "Event"} and not temporal(item["temporal"]): return "invalid_temporal_shape"
    if entity["type"] in {"Decision", "Event"} and item["temporal"] is None: return "invalid_temporal_shape"
    if secret_like(item): return "secret_like_entity_proposal"
    return None


def shape_reason(item: Any, hash_re: Any, id_re: Any, secret_like: Callable[[Any], bool]) -> str | None:
    required = {"assertion_id", "subject", "predicate", "object", "source_claim_id", "source", "method", "asserted_at", "valid_time", "status", "review", "extractor", "confidence"}
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
    reason = _source_reason(item["source"], HASH_KEYS, hash_re)
    if reason: return reason
    if item["method"] not in METHODS or item["status"] not in STATUSES or not timestamp(item["asserted_at"]): return "invalid_lifecycle"
    review, extractor, confidence = item["review"], item["extractor"], item["confidence"]
    if review is not None and not _review_ok(review): return "invalid_lifecycle"
    if extractor is not None and not _extractor_ok(extractor, hash_re): return "invalid_lifecycle"
    if item["method"] == "extracted_candidate":
        if extractor is None or not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not math.isfinite(confidence) or not 0 <= confidence <= 1: return "invalid_confidence"
        if item["status"] not in {"candidate", "rejected", "quarantined"}: return "invalid_lifecycle"
    elif extractor is not None or confidence is not None: return "invalid_lifecycle"
    if item["method"] == "human_approved" and review is None: return "missing_review"
    if item["method"] == "explicit" and (review is not None or item["status"] not in {"approved", "quarantined", "superseded"}): return "invalid_lifecycle"
    if item["predicate"] == "caused" and (item["method"] != "human_approved" or item["status"] != "approved" or review is None): return "causality_requires_human_approval"
    if item["predicate"] == "caused" and review is not None and review.get("review_reason") != "direct_causal_statement": return "causality_not_direct"
    if not temporal(item["valid_time"]): return "invalid_temporal_shape"
    if secret_like(item): return "secret_like_assertion"
    return None


def _freshness(item: dict[str, Any], claims: dict[str, Any], sources: dict[str, Any], evidence: bool) -> str | None:
    claim = claims.get(item.get("source_claim_id")); source = item.get("source", {})
    if claim is None: return "ineligible_claim"
    source_info = sources.get(source.get("path"), {})
    if source.get("path") != claim.get("path"): return "stale_provenance"
    if source.get("source_content_hash") != source_info.get("hash"): return "source_hash_mismatch"
    if source.get("claim_content_hash") != claim.get("content_hash"): return "claim_hash_mismatch"
    if source.get("line_start") != claim.get("line") or source.get("line_end") != claim.get("line"): return "stale_provenance"
    if evidence:
        hashes = {x.get("content_hash") for x in claim.get("evidence", []) if isinstance(x, dict)}
        if source.get("evidence_excerpt_hash") not in hashes: return "evidence_hash_mismatch"
    return None


def validate_bundle(root: Path, bundle: Any, agent_id: str, workspace_id: str | None, api: dict[str, Any]) -> dict[str, Any]:
    common = {"schema_version", "semantic_contract_version", "namespace", "source_snapshot_hash", "source_digest", "assertions", "identity_candidates"}
    if not isinstance(bundle, dict): raise api["error"]("invalid_assertion_bundle", "Assertion bundle has an invalid closed shape")
    legacy = (bundle.get("schema_version") in {LEGACY_ASSERTION_SCHEMA_VERSION, ASSERTION_SCHEMA_VERSION}
              and bundle.get("semantic_contract_version") == "0.8" and "entity_proposals" not in bundle)
    allowed = common if legacy else common | {"entity_proposals"}
    if set(bundle) != allowed or (not legacy and (bundle.get("schema_version") != ASSERTION_SCHEMA_VERSION or bundle.get("semantic_contract_version") != ASSERTION_CONTRACT_VERSION)):
        raise api["error"]("invalid_assertion_bundle", "Assertion schema or contract version is unsupported")
    if not isinstance(bundle["assertions"], list) or len(bundle["assertions"]) > 256: raise api["error"]("invalid_assertion_bundle", "assertions must be a bounded array")
    proposals = [] if legacy else bundle["entity_proposals"]
    if not isinstance(proposals, list) or len(proposals) > 256: raise api["error"]("invalid_assertion_bundle", "entity_proposals must be a bounded array")
    inspected = api["inspect"](root); ownership = api["namespace"](agent_id, root, workspace_id); snapshot = api["plan"](inspected, False, ownership)
    if bundle["namespace"] != ownership["namespace"]: raise api["error"]("namespace_mismatch", "Assertion namespace does not match ownership")
    if bundle["source_snapshot_hash"] != snapshot["snapshot_hash"] or bundle["source_digest"] != snapshot["source_digest"]: raise api["error"]("stale_provenance", "Bundle does not match fresh canonical snapshot")
    canonical_entities: dict[tuple[str, str], dict[str, Any]] = {}
    for entity in snapshot["entities"]:
        if entity.get("entityType") in api["semantic_types"] and ":semantic:" in entity.get("name", ""):
            obs = json.loads(entity["observations"][0]); canonical_entities[(entity["entityType"], obs["entity_id"])] = {"name": entity["name"], "entity_source": "canonical_explicit", "entity_proposal_ids": []}
    claims = {x["claim_id"]: x for x in snapshot["claims"]}; sources = {x["path"]: x for x in inspected["sources"]}
    accepted_proposals, proposal_quarantine, proposal_seen, invalid_proposal_endpoints = [], [], {}, {}
    for item in proposals:
        reason = proposal_shape_reason(item, ownership["namespace"], api["hash_re"], api["id_re"], api["secret_like"])
        if reason is None and item["entity_proposal_id"] != entity_proposal_id(ownership["namespace"], item): reason = "entity_proposal_id_mismatch"
        pid = item.get("entity_proposal_id") if isinstance(item, dict) else None
        if reason is None and pid in proposal_seen and proposal_seen[pid] != canonical_bytes(item): raise api["error"]("conflicting_entity_proposal", "One proposal ID identifies differing content")
        if reason is None: proposal_seen[pid] = canonical_bytes(item)
        if reason is None: reason = _freshness(item, claims, sources, False)
        if reason:
            if isinstance(item, dict) and isinstance(item.get("entity"), dict):
                endpoint = (item["entity"].get("type"), item["entity"].get("entity_id"))
                if all(isinstance(x, str) for x in endpoint):
                    invalid_proposal_endpoints.setdefault(endpoint, set()).add(reason)
            proposal_quarantine.append(_safe_record(reason, item, "entity_proposal")); continue
        normalized = json.loads(canonical_bytes(item)); normalized.update({"canonical": False, "locator_only": True, "rehydration_required": True, "entity_source": "approved_private_proposal" if item["status"] == "approved" else "private_entity_proposal"})
        accepted_proposals.append(normalized)
    accepted_proposals = sorted({x["entity_proposal_id"]: x for x in accepted_proposals}.values(), key=lambda x: x["entity_proposal_id"])
    proposed_entities: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for proposal in accepted_proposals:
        if proposal["status"] == "approved": proposed_entities.setdefault((proposal["entity"]["type"], proposal["entity"]["entity_id"]), []).append(proposal)
    conflicts = {key for key, values in proposed_entities.items() if len({digest(v["temporal"]) for v in values}) > 1}
    entities = dict(canonical_entities)
    for key, values in proposed_entities.items():
        if key in conflicts or key in canonical_entities: continue
        entities[key] = {"name": f"{ownership['namespace']}proposal:{key[0]}:{key[1]}", "entity_source": "approved_private_proposal", "entity_proposal_ids": sorted(x["entity_proposal_id"] for x in values)}
    accepted, rejected, seen = [], proposal_quarantine[:], {}
    for item in bundle["assertions"]:
        reason = shape_reason(item, api["hash_re"], api["id_re"], api["secret_like"])
        if reason is None and item["assertion_id"] != assertion_id(ownership["namespace"], item): reason = "id_mismatch"
        aid = item.get("assertion_id") if isinstance(item, dict) else None
        if reason is None and aid in seen and seen[aid] != canonical_bytes(item): raise api["error"]("conflicting_assertions", "One assertion ID identifies differing content")
        if reason is None: seen[aid] = canonical_bytes(item)
        if reason is None:
            reason = _freshness(item, claims, sources, True)
            if legacy and reason in {"source_hash_mismatch", "claim_hash_mismatch"}: reason = "stale_provenance"
        if reason is None:
            endpoints = [(item["subject"]["type"], item["subject"]["entity_id"]), (item["object"]["type"], item["object"]["entity_id"])]
            if any(ep in conflicts for ep in endpoints): reason = "conflicting_entity_identity"
            elif any(ep not in entities for ep in endpoints):
                known_inert = {(x["entity"]["type"], x["entity"]["entity_id"]) for x in accepted_proposals if x["status"] != "approved"}
                if any(ep in known_inert for ep in endpoints): reason = "unapproved_entity_proposal"
                elif any(ep in invalid_proposal_endpoints for ep in endpoints): reason = "stale_entity_proposal"
                else: reason = "dangling_endpoint"
        if reason: rejected.append(quarantine(reason, item)); continue
        value = json.loads(canonical_bytes(item)); sub = entities[(item["subject"]["type"], item["subject"]["entity_id"])]; obj = entities[(item["object"]["type"], item["object"]["entity_id"])]
        value.update({"canonical": item["method"] == "explicit" and sub["entity_source"] == obj["entity_source"] == "canonical_explicit", "locator_only": True, "rehydration_required": True,
            "subject_name": sub["name"], "object_name": obj["name"], "subject_entity_source": sub["entity_source"], "object_entity_source": obj["entity_source"],
            "subject_entity_proposal_ids": sub["entity_proposal_ids"], "object_entity_proposal_ids": obj["entity_proposal_ids"]})
        accepted.append(value)
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
    for candidate in identity:
        keys = {"candidate_id", "left", "right", "feature_codes", "score", "method", "version", "config_hash", "source_claim_ids"}; epkeys = {"entity_id", "type"}
        endpoints_ok = isinstance(candidate, dict) and all(isinstance(candidate.get(k), dict) and set(candidate[k]) == epkeys for k in ("left", "right"))
        endpoint_values = endpoints_ok and all((ep["type"], ep["entity_id"]) in entities for ep in (candidate["left"], candidate["right"]))
        score = candidate.get("score") if isinstance(candidate, dict) else None
        valid = (isinstance(candidate, dict) and set(candidate) == keys and not api["secret_like"](candidate)
            and isinstance(candidate.get("candidate_id"), str) and api["id_re"].fullmatch(candidate["candidate_id"])
            and isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score) and 0 <= score <= 1
            and endpoints_ok and endpoint_values and candidate["left"] != candidate["right"] and candidate["left"]["type"] == candidate["right"]["type"]
            and isinstance(candidate.get("feature_codes"), list) and candidate["feature_codes"] and all(isinstance(x, str) and api["id_re"].fullmatch(x) for x in candidate["feature_codes"])
            and isinstance(candidate.get("source_claim_ids"), list) and candidate["source_claim_ids"] and all(x in claims for x in candidate["source_claim_ids"])
            and all(isinstance(candidate.get(k), str) and candidate[k] for k in ("method", "version"))
            and isinstance(candidate.get("config_hash"), str) and api["hash_re"].fullmatch(candidate["config_hash"]))
        if not valid: rejected.append(quarantine("invalid_identity_candidate", candidate)); continue
        safe_identity.append({**candidate, "status": "candidate", "auto_merge": False, "projected": False, "aliases_inert": True})
    rejected.sort(key=lambda x: (x["reason_code"], x.get("source_claim_id", ""), x.get("entity_proposal_id", x.get("assertion_id", ""))))
    endpoint_catalog = [{"type": k[0], "entity_id": k[1], **v} for k, v in sorted(entities.items())]
    report = {"conforms": not rejected, "shape_version": ASSERTION_SHAPE_VERSION, "semantic_contract_version": ASSERTION_CONTRACT_VERSION,
        "namespace": ownership["namespace"], "source_snapshot_hash": snapshot["snapshot_hash"], "source_digest": snapshot["source_digest"],
        "migration": {"from": "0.8" if legacy else None, "to": "0.9", "input_rewritten": False}, "entity_proposals": accepted_proposals,
        "approved_endpoint_catalog": endpoint_catalog, "accepted_assertions": accepted, "quarantine": rejected,
        "identity_candidates": sorted(safe_identity, key=lambda x: x["candidate_id"])}
    report["report_hash"] = digest(report); return report


def review_queue(validated: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": "memory-graph-review-queue/v2", "namespace": validated["namespace"],
        "entity_candidates": [x for x in validated["entity_proposals"] if x["status"] == "candidate"],
        "candidates": [x for x in validated["accepted_assertions"] if x["status"] == "candidate"],
        "identity_candidates": validated["identity_candidates"], "quarantine": validated["quarantine"], "mutation_performed": False}


def semantic_view(validated: dict[str, Any], include_candidates: bool = False) -> dict[str, Any]:
    def edge(item: dict[str, Any], label: str, style: str) -> dict[str, Any]:
        return {"assertion_id": item["assertion_id"], "from": item["subject_name"], "to": item["object_name"], "predicate": item["predicate"], "label": label, "style": style,
            "status": item["status"], "method": item["method"], "valid_time": item["valid_time"], "endpoint_sources": [item["subject_entity_source"], item["object_entity_source"]],
            "entity_proposal_ids": sorted(set(item["subject_entity_proposal_ids"] + item["object_entity_proposal_ids"])),
            "why_this_edge": {"source_claim_id": item["source_claim_id"], **item["source"]}, "canonical": item["canonical"], "locator_only": True, "rehydration_required": True}
    approved = [edge(x, "Approved explicit", "solid") for x in validated["accepted_assertions"] if x["status"] == "approved"][:200]
    candidates = [edge(x, "Candidate, noncanonical", "dashed") for x in validated["accepted_assertions"] if include_candidates and x["status"] == "candidate"][:max(0, 200-len(approved))]
    private_nodes = [{"entity_id": x["entity"]["entity_id"], "type": x["entity"]["type"], "label": "Approved private entity proposal", "style": "solid", "entity_proposal_id": x["entity_proposal_id"]} for x in validated["entity_proposals"] if x["status"] == "approved"][:100]
    result = {"schema_version": "memory-graph-semantic-view/v2", "namespace": validated["namespace"], "view_types": ["path", "ego", "timeline"], "structural_relations": [],
        "nodes": private_nodes, "approved_assertions": approved, "candidate_assertions": candidates,
        "legends": [{"label":"Approved explicit","style":"solid"},{"label":"Approved private entity proposal","style":"solid"},{"label":"Candidate, noncanonical","style":"dashed"}], "canonical_grounding_required": True}
    result["view_hash"] = digest(result); return result


def cq_evaluate(validated: dict[str, Any]) -> dict[str, Any]:
    approved = [x for x in validated["accepted_assertions"] if x["status"] == "approved"]; predicates = sorted({x["predicate"] for x in approved}); caused = [x for x in approved if x["predicate"] == "caused"]
    locators = all(x["source"].get("path") and x["source"].get("line_start") and all(len(x["source"][k]) == 64 for k in HASH_KEYS) for x in approved)
    supported = [x for x in approved if shape_reason({k:x[k] for k in {"assertion_id","subject","predicate","object","source_claim_id","source","method","asserted_at","valid_time","status","review","extractor","confidence"}}, type("R",(),{"fullmatch":lambda _,v: bool(isinstance(v,str) and len(v)==64)})(), type("I",(),{"fullmatch":lambda _,v: bool(v)})(), lambda _:False) is None]
    checks = {"CQ1": any(x["predicate"] == "decided" for x in approved), "CQ2": bool(caused) and all(x["method"] == "human_approved" and x["review"]["review_reason"] == "direct_causal_statement" for x in caused),
        "CQ3": any(x["predicate"] == "supersedes" for x in approved), "CQ4": any(x["predicate"] == "participates_in" for x in approved) and all(temporal(x["valid_time"]) for x in approved), "CQ5": locators}
    metrics = {"approved_assertion_count": len(approved), "represented_predicates": predicates, "unsupported_approved_edge_count": len(approved)-len(supported),
        "locator_completeness": 1.0 if locators else 0.0, "canonical_hydration_locator_coverage": 1.0 if locators else 0.0, "cq_pass_count": sum(checks.values())}
    gates = {"semantic_assertions_gte_12": len(approved) >= 12, "cq_5_of_5": all(checks.values()), "unsupported_approved_edge_zero": metrics["unsupported_approved_edge_count"] == 0, "canonical_hydration_locator_coverage_100_percent": locators}
    result = {"schema_version":"memory-graph-cq-evaluation/v2","namespace":validated["namespace"],"competency_questions":checks,"metrics":metrics,"gates":gates,"passed":all(gates.values())}; result["evaluation_hash"] = digest(result); return result
