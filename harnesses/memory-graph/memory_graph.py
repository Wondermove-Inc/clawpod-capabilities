#!/usr/bin/env python3
"""Build a deterministic, noncanonical graph plan from canonical Markdown memory."""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import math
import importlib.util
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_ONTOLOGY_SPEC = importlib.util.spec_from_file_location("memory_graph_ontology", Path(__file__).with_name("ontology.py"))
if _ONTOLOGY_SPEC is None or _ONTOLOGY_SPEC.loader is None:  # pragma: no cover - import machinery failure
    raise RuntimeError("Unable to load local ontology module")
ontology = importlib.util.module_from_spec(_ONTOLOGY_SPEC)
_ONTOLOGY_SPEC.loader.exec_module(ontology)
_SEMANTIC_V10_SPEC = importlib.util.spec_from_file_location("memory_graph_semantic_v10", Path(__file__).with_name("semantic_v10.py"))
if _SEMANTIC_V10_SPEC is None or _SEMANTIC_V10_SPEC.loader is None:
    raise RuntimeError("Unable to load local semantic v0.10 module")
semantic_v10 = importlib.util.module_from_spec(_SEMANTIC_V10_SPEC)
_SEMANTIC_V10_SPEC.loader.exec_module(semantic_v10)

SCHEMA_VERSION = 6
CONTRACT_VERSION = "0.10.0"
SEMANTIC_CONTRACT_VERSION = "1.0.0"
INFERENCE_CONTRACT_VERSION = "0.7"
INFERENCE_SCHEMA_VERSION = "memory-graph-inference-candidates/v1"
ASSERTION_SCHEMA_VERSION = "memory-graph-assertions/v2"
ASSERTION_SHAPE_VERSION = "memory-graph-ontology-shapes/v2"
ASSERTION_CONTRACT_VERSION = "0.9"
MAX_INFERENCE_BUNDLE_BYTES = 1024 * 1024
MAX_INFERENCE_CANDIDATES = 1000
MAX_SOURCE_FILES = 256
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_MCP_OUTPUT_BYTES = 1024 * 1024
MAX_MCP_ARGV_BYTES = 48 * 1024
MAX_MCP_BATCH_ITEMS = 100
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
BLOCK_RE = re.compile(r"^```memory-claim\s*$\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)
WRITER_ID_RE = re.compile(r"^<!--\s*openclaw-memory-claim:([^\s>]+)\s*-->\s*$", re.MULTILINE)
WRITER_JSON_RE = re.compile(r"^<!--\s*openclaw-memory-claim-json:(.*?)\s*-->\s*$", re.MULTILINE)
HEADING_RE = re.compile(r"^#{2,6}\s+.+$", re.MULTILINE)
FIELD_RE = re.compile(r"^- (Status|Claim|Confidence|Evidence|Updated):(?:\s+(.*))?$", re.MULTILINE)
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
AGENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"(?i)\b(?:password|passwd|api[_ -]?key|access[_ -]?token)\s*[:=]\s*[^\s,;]{8,}"),
]
ALLOWED_STATUS = {"current", "tentative", "superseded", "rejected", "conflicted", "archived", "active"}
ELIGIBLE_STATUS = {"current", "tentative", "active"}
SEMANTIC_TYPES = {"Person", "Project", "Decision", "Event"}
SEMANTIC_RELATIONS = {
    "participates_in": ({"Person"}, {"Project", "Event"}),
    "decided": ({"Person"}, {"Decision"}),
    "caused": ({"Decision", "Event"}, {"Event"}),
    "supersedes": ({"Decision"}, {"Decision"}),
}

# Canonical graph inputs are only direct memory/*.md topic files.
MEMORY_AUTHORITY = "canonical_memory"

class InputError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def mcp_argv(executable: str, tool: str, arguments: dict[str, Any]) -> list[str]:
    return [executable, "call", f"memory.{tool}", "--args",
            json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))]


def argv_payload_bytes(argv: list[str]) -> int:
    """Bytes consumed by argv strings, including their terminating NULs."""
    return sum(len(argument.encode("utf-8")) + 1 for argument in argv)


def mutation_batches(executable: str, tool: str, key: str, items: list[Any],
                     count_cap: int = MAX_MCP_BATCH_ITEMS) -> list[dict[str, Any]]:
    """Deterministically preserve order while respecting count and argv byte caps."""
    batches: list[dict[str, Any]] = []
    pending: list[Any] = []
    for index, item in enumerate(items):
        candidate = pending + [item]
        arguments = {key: candidate}
        payload_bytes = argv_payload_bytes(mcp_argv(executable, tool, arguments))
        if len(candidate) <= count_cap and payload_bytes <= MAX_MCP_ARGV_BYTES:
            pending = candidate
            continue
        if not pending:
            raise InputError("mutation_item_too_large",
                "A single MCP mutation item exceeds the safe argv payload cap; no mutation was attempted",
                {"tool": tool, "item_index": index, "payload_bytes": payload_bytes,
                 "payload_cap_bytes": MAX_MCP_ARGV_BYTES, "mutation_performed": False})
        batches.append({"tool": tool, "arguments": {key: pending}})
        pending = [item]
        single_bytes = argv_payload_bytes(mcp_argv(executable, tool, {key: pending}))
        if single_bytes > MAX_MCP_ARGV_BYTES:
            raise InputError("mutation_item_too_large",
                "A single MCP mutation item exceeds the safe argv payload cap; no mutation was attempted",
                {"tool": tool, "item_index": index, "payload_bytes": single_bytes,
                 "payload_cap_bytes": MAX_MCP_ARGV_BYTES, "mutation_performed": False})
    if pending:
        batches.append({"tool": tool, "arguments": {key: pending}})
    return batches


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def safe_resolve(root: Path, raw: str) -> Path:
    candidate = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise InputError("path_outside_root", "Input path must remain within workspace root", {"path": raw}) from exc
    return candidate


def safe_output_resolve(root: Path, raw: str) -> Path:
    """Resolve an HTML output without following attacker-controlled symlinks."""
    rel = Path(raw)
    if rel.is_absolute() or not rel.parts or any(part in {"", ".", ".."} for part in rel.parts) or rel.suffix.lower() != ".html":
        raise InputError("invalid_output_path", "Output must be a relative .html path without dot segments", {"path": raw})
    root = root.resolve()
    cursor = root
    for part in rel.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise InputError("output_symlink", "Output path must not contain symlinks", {"path": raw})
    if cursor.exists() and not cursor.is_file():
        raise InputError("invalid_output_path", "Existing output must be a regular file", {"path": raw})
    return cursor


def recognized_files(root: Path) -> list[tuple[Path, str, str, str | None]]:
    """Return only direct, regular, non-symlink ``memory/*.md`` files.

    Root/context Markdown and nested memory metadata/evidence are deliberately
    outside the canonical graph source boundary. A direct Markdown symlink or
    non-regular entry fails closed instead of being followed.
    """
    root = root.resolve()
    paths: list[tuple[Path, str, str, str | None]] = []
    folder = root / "memory"
    if folder.is_symlink():
        raise InputError("unsafe_memory_path", "Memory directory must not be a symlink", {"path": "memory"})
    if folder.exists() and not folder.is_dir():
        raise InputError("unsafe_memory_path", "Memory directory must be a regular directory", {"path": "memory"})
    if folder.is_dir():
        for p in folder.iterdir():
            if not p.name.endswith(".md"):
                continue
            rel = p.relative_to(root).as_posix()
            if p.is_symlink() or not p.is_file():
                raise InputError("unsafe_memory_path", "Memory topic sources must be regular non-symlink files", {"path": rel})
            paths.append((p, "memory_claim", MEMORY_AUTHORITY, None))
    result = sorted(paths, key=lambda item: item[0].relative_to(root).as_posix())
    if len(result) > MAX_SOURCE_FILES:
        raise InputError("source_limit", "Too many canonical memory source files", {"limit": MAX_SOURCE_FILES})
    return result


def namespace_for(agent_id: str, root: Path, workspace_id: str | None = None) -> dict[str, str]:
    if not AGENT_ID_RE.fullmatch(agent_id):
        raise InputError("invalid_agent_id", "agent-id must be explicit and portable", {"pattern": AGENT_ID_RE.pattern})
    identity = workspace_id if workspace_id is not None else root.resolve().as_posix()
    if not identity or len(identity.encode()) > 4096:
        raise InputError("invalid_workspace_id", "workspace-id must be non-empty and bounded")
    workspace_hash = hashlib.sha256(identity.encode()).hexdigest()
    owner_hash = hashlib.sha256(canonical_bytes({"agent_id": agent_id, "workspace_hash": workspace_hash})).hexdigest()[:24]
    return {"agent_id": agent_id, "workspace_hash": workspace_hash, "namespace": f"memory-graph:v1:{owner_hash}:"}


def apply_namespace(snapshot: dict[str, Any], ownership: dict[str, str]) -> dict[str, Any]:
    prefix = ownership["namespace"]
    mapping = {entity["name"]: prefix + entity["name"] for entity in snapshot["entities"]}
    def relation(value: dict[str, str]) -> dict[str, str]:
        return {"from": mapping[value["from"]], "to": mapping[value["to"]], "relationType": value["relationType"]}
    result = dict(snapshot)
    result["ownership"] = ownership
    result["entities"] = [
        {"name": mapping[e["name"]], "entityType": e["entityType"], "observations": e["observations"]}
        for e in snapshot["entities"]
    ]
    for field in ("explicit_relations", "structural_relations", "inferred_relations"):
        result[field] = [relation(r) for r in snapshot[field]]
    result["semantic_relations"] = [{**r, "from": mapping[r["from"]], "to": mapping[r["to"]]} for r in snapshot.get("semantic_relations", [])]
    result.pop("snapshot_hash", None)
    result["snapshot_hash"] = digest(result)
    return result


def secret_like(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def redact(value: Any, sensitive_context: bool = False) -> Any:
    if isinstance(value, str):
        return "[REDACTED]" if sensitive_context or secret_like(value) else value
    if isinstance(value, list):
        return [redact(item, sensitive_context) for item in value]
    if isinstance(value, dict):
        return {key: redact(item, sensitive_context or bool(re.search(r"(?i)(password|passwd|secret|api.?key|access.?token)", key))) for key, item in value.items()}
    return value


def _id_array(raw: dict[str, Any], field: str, path: str, line: int) -> list[str]:
    value = raw.get(field, [])
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(x, str) and ID_RE.fullmatch(x) for x in value):
        raise InputError("malformed_metadata", f"{field} must be a claim-id array", {"path": path, "line": line})
    return sorted(set(value))


def validate_claim(raw: Any, path: str, line: int, secret_policy: str, bullets: dict[str, str] | None = None, marker_id: str | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise InputError("malformed_metadata", "Claim metadata must be a JSON object", {"path": path, "line": line})
    if "claim_key" in raw and "key" in raw and raw["claim_key"] != raw["key"]:
        raise InputError("malformed_metadata", "claim_key and legacy key disagree", {"path": path, "line": line})
    required = ("claim_id", "status", "evidence")
    missing = [key for key in required if key not in raw]
    if "claim_key" not in raw and "key" not in raw:
        missing.append("claim_key")
    if missing:
        raise InputError("malformed_metadata", "Claim metadata is missing required fields", {"path": path, "line": line, "fields": missing})
    if not isinstance(raw["claim_id"], str) or not ID_RE.fullmatch(raw["claim_id"]):
        raise InputError("invalid_claim_id", "claim_id has an invalid format", {"path": path, "line": line})
    claim_key = raw.get("claim_key", raw.get("key"))
    if not isinstance(claim_key, str) or not claim_key.strip():
        raise InputError("malformed_metadata", "claim_key must be a non-empty string", {"path": path, "line": line})
    if marker_id is not None and marker_id != raw["claim_id"]:
        raise InputError("malformed_metadata", "Claim marker and JSON claim_id disagree", {"path": path, "line": line})
    if raw["status"] not in ALLOWED_STATUS:
        raise InputError("malformed_metadata", "status is not supported", {"path": path, "line": line, "status": raw["status"]})
    evidence = raw["evidence"]
    valid_evidence = isinstance(evidence, list) and bool(evidence) and all(
        (isinstance(x, str) and bool(x)) or
        (isinstance(x, dict) and isinstance(x.get("evidence_id"), str) and bool(x["evidence_id"])
         and isinstance(x.get("path"), str) and bool(x["path"])
         and isinstance(x.get("content_hash"), str) and bool(re.fullmatch(r"[0-9a-f]{64}", x["content_hash"])))
        for x in evidence
    )
    if not valid_evidence:
        raise InputError("malformed_metadata", "evidence must be a non-empty array of evidence metadata or legacy strings", {"path": path, "line": line})
    supersedes = _id_array(raw, "supersedes", path, line)
    superseded_by = _id_array(raw, "superseded_by", path, line)
    relations = raw.get("relations", [])
    if not isinstance(relations, list):
        raise InputError("malformed_metadata", "relations must be an array", {"path": path, "line": line})
    for relation in relations:
        if not isinstance(relation, dict) or set(("to", "type")) - relation.keys() or not all(isinstance(relation[k], str) and relation[k] for k in ("to", "type")):
            raise InputError("malformed_metadata", "Each relation requires string to and type fields", {"path": path, "line": line})
    content = dict(raw)
    content.pop("key", None)
    content["claim_key"] = claim_key
    content["relations"] = relations
    if bullets is not None:
        required_bullets = {"Status", "Claim", "Confidence", "Evidence", "Updated"}
        missing_bullets = sorted(required_bullets - bullets.keys())
        if missing_bullets:
            raise InputError("malformed_metadata", "Writer claim is missing required bullet fields", {"path": path, "line": line, "fields": missing_bullets})
        if bullets["Status"] != raw["status"]:
            raise InputError("malformed_metadata", "Status bullet disagrees with metadata", {"path": path, "line": line})
        if "updated_at" in raw and bullets["Updated"] != raw["updated_at"]:
            raise InputError("malformed_metadata", "Updated bullet disagrees with metadata", {"path": path, "line": line})
        try:
            confidence = float(bullets["Confidence"])
        except ValueError as exc:
            raise InputError("malformed_metadata", "Confidence must be numeric", {"path": path, "line": line}) from exc
        if not 0 <= confidence <= 1 or not bullets["Claim"].strip() or not bullets["Evidence"].strip():
            raise InputError("malformed_metadata", "Writer bullet values are invalid", {"path": path, "line": line})
        content.update({"claim": bullets["Claim"], "confidence": confidence, "evidence_text": bullets["Evidence"], "updated": bullets["Updated"]})
    if secret_like(content):
        if secret_policy == "reject":
            raise InputError("secret_like_text", "Secret-like claim text rejected", {"path": path, "line": line})
        content = redact(content)
    content["supersedes"] = sorted(set(supersedes))
    content["superseded_by"] = superseded_by
    content["evidence"] = sorted(content["evidence"], key=lambda x: canonical_bytes(x))
    content["relations"] = sorted(content["relations"], key=lambda x: (x["to"], x["type"]))
    # Normalize nested semantic arrays before claim hashing so harmless JSON
    # reordering cannot perturb semantic IDs or provenance content hashes.
    semantic = content.get("semantic")
    if isinstance(semantic, dict):
        normalized_semantic = dict(semantic)
        if isinstance(normalized_semantic.get("entities"), list):
            normalized_entities = []
            for item in normalized_semantic["entities"]:
                item = dict(item) if isinstance(item, dict) else item
                if isinstance(item, dict):
                    for field in ("aliases", "external_ids"):
                        if isinstance(item.get(field), list):
                            item[field] = sorted(set(item[field]), key=canonical_bytes)
                normalized_entities.append(item)
            normalized_semantic["entities"] = sorted(normalized_entities, key=canonical_bytes)
        if isinstance(normalized_semantic.get("relations"), list):
            normalized_semantic["relations"] = sorted(normalized_semantic["relations"], key=canonical_bytes)
        content["semantic"] = normalized_semantic
    claim_hash = digest(content)
    content["path"] = path
    content["line"] = line
    content["hash"] = claim_hash
    content["content_hash"] = claim_hash
    return content


def _quarantine(reason: str, claim: dict[str, Any], candidate: Any) -> dict[str, Any]:
    candidate_hash = digest(candidate)
    return {"quarantine_id": digest({"reason": reason, "claim": claim["claim_id"], "candidate": candidate_hash}),
            "reason_code": reason, "source_claim_id": claim["claim_id"], "path": claim["path"],
            "line": claim["line"], "candidate_hash": candidate_hash,
            "remediation": "Correct explicit canonical semantic metadata and provenance."}


def _normalized_display(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split()).casefold()


def _temporal_value(value: Any) -> tuple[str, str] | None:
    """Validate contract time syntax and return (kind, normalized value)."""
    if not isinstance(value, str):
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            date.fromisoformat(value)
            return ("date", value)
        # RFC 3339 requires an explicit Z or numeric offset.
        if not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", value):
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return ("timestamp", parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))
    except ValueError:
        return None


def _normalize_semantic_entity(entity: dict[str, Any]) -> dict[str, Any] | None:
    result = dict(entity)
    aliases = result.get("aliases", [])
    external = result.get("external_ids", [])
    if (not isinstance(aliases, list) or not all(isinstance(x, str) and x.strip() for x in aliases)
            or not isinstance(external, list) or not all(isinstance(x, str) and x.strip() for x in external)):
        return None
    result["aliases"] = sorted(set(aliases), key=lambda x: (_normalized_display(x), x))
    result["external_ids"] = sorted(set(external))
    for field in ("valid_from", "valid_to", "effective_at", "occurred_at"):
        if field in result:
            parsed = _temporal_value(result[field])
            if parsed is None:
                return None
            result[field + "_normalized"] = parsed[1]
    if "interval" in result:
        interval = result["interval"]
        if not isinstance(interval, dict) or set(interval) != {"start", "end"}:
            return None
        start, end = _temporal_value(interval["start"]), _temporal_value(interval["end"])
        if start is None or end is None or start[0] != end[0] or start[1] > end[1]:
            return None
        result["interval_normalized"] = {"start": start[1], "end": end[1]}
    if "valid_from" in result and "valid_to" in result:
        start, end = _temporal_value(result["valid_from"]), _temporal_value(result["valid_to"])
        if start is None or end is None or start[0] != end[0] or start[1] > end[1]:
            return None
    return result


def build_semantic_projection(claims: list[dict[str, Any]], sources: dict[str, dict[str, Any]], namespace: str = "") -> dict[str, Any]:
    """Project only explicit, fully grounded claim metadata. Invalid records are inert."""
    records: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    quarantined: list[dict[str, Any]] = []
    relations_raw: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for claim in claims:
        semantic = claim.get("semantic")
        if semantic is None or claim["status"] not in ELIGIBLE_STATUS:
            continue
        if not isinstance(semantic, dict) or set(semantic) - {"entities", "relations"}:
            quarantined.append(_quarantine("unknown_type", claim, semantic)); continue
        evidence = claim.get("evidence", [])
        source = sources.get(claim["path"], {})
        provenance_ok = (claim.get("line", 0) > 0 and HASH_RE.fullmatch(str(source.get("hash", "")))
                         and evidence and all(isinstance(e, dict) and e.get("evidence_id")
                         and isinstance(e.get("path"), str) and HASH_RE.fullmatch(str(e.get("content_hash", ""))) for e in evidence))
        if not provenance_ok:
            quarantined.append(_quarantine("missing_provenance", claim, semantic)); continue
        entities = semantic.get("entities", [])
        relations = semantic.get("relations", [])
        if not isinstance(entities, list) or not isinstance(relations, list):
            quarantined.append(_quarantine("unknown_type", claim, semantic)); continue
        for entity in entities:
            if not isinstance(entity, dict) or entity.get("type") not in SEMANTIC_TYPES:
                quarantined.append(_quarantine("unknown_type", claim, entity)); continue
            if set(entity) - {"entity_id", "type", "canonical_name", "aliases", "external_ids", "valid_from", "valid_to", "effective_at", "occurred_at", "interval", "time_unknown"}:
                quarantined.append(_quarantine("unknown_type", claim, entity)); continue
            eid, name = entity.get("entity_id"), entity.get("canonical_name")
            if not isinstance(eid, str) or not ID_RE.fullmatch(eid) or not isinstance(name, str) or not name.strip() or secret_like(entity):
                quarantined.append(_quarantine("identity_conflict", claim, {"entity_id": eid, "type": entity.get("type")})); continue
            if entity["type"] in {"Decision", "Event"} and not (entity.get("effective_at") or entity.get("occurred_at") or entity.get("interval") or entity.get("time_unknown") is True):
                quarantined.append(_quarantine("temporal_conflict", claim, entity)); continue
            normalized = _normalize_semantic_entity(entity)
            if normalized is None:
                quarantined.append(_quarantine("temporal_conflict", claim, entity)); continue
            entity = normalized
            records.setdefault((entity["type"], eid), []).append((claim, entity))
        for relation in relations:
            relations_raw.append((claim, relation))
    semantic_entities, lookup = [], {}
    conflicted_ids = {eid for _, eid in records if len({etype for etype, other in records if other == eid}) > 1}
    for (etype, eid), grounded in sorted(records.items()):
        if eid in conflicted_ids:
            for claim, entity in grounded: quarantined.append(_quarantine("identity_conflict", claim, entity))
            continue
        definitions = {canonical_bytes(entity) for _, entity in grounded}
        if len(definitions) != 1:
            for claim, entity in grounded: quarantined.append(_quarantine("multiple_current_assertions", claim, entity))
            continue
        entity = grounded[0][1]
        prov = []
        for claim, _ in grounded:
            source = sources[claim["path"]]
            prov.append({"source_claim_id": claim["claim_id"], "claim_key": claim["claim_key"], "status": claim["status"],
                "content_hash": claim["content_hash"], "path": claim["path"], "line": claim["line"],
                "source_content_hash": source["hash"], "evidence": claim["evidence"],
                "writer_version": claim.get("writer_version"), "extraction_version": claim.get("extraction_version"),
                "semantic_contract_version": SEMANTIC_CONTRACT_VERSION, "semantic_record_hash": digest(entity),
                "created_at": claim.get("created_at"), "updated_at": claim.get("updated_at"),
                "confidence": claim.get("confidence"), "captured_at": claim.get("captured_at")})
        local = f"semantic:{etype}:{eid}"; lookup[eid] = (local, etype)
        observation = {**entity, "grounding_claim_ids": sorted(x[0]["claim_id"] for x in grounded), "provenance": sorted(prov, key=canonical_bytes)}
        semantic_entities.append({"name": namespace + local, "entityType": etype, "observations": [json.dumps(observation, ensure_ascii=False, sort_keys=True, separators=(",", ":"))]})
    # Reject semantic supersession cycles as complete inert components.
    supersession_candidates = [(claim, rel) for claim, rel in relations_raw
        if isinstance(rel, dict) and rel.get("type") == "supersedes"
        and rel.get("from") in lookup and rel.get("to") in lookup]
    supersession_graph: dict[str, set[str]] = {}
    for _, rel in supersession_candidates:
        supersession_graph.setdefault(rel["from"], set()).add(rel["to"])
    cyclic_nodes: set[str] = set()
    def visit(node: str, trail: tuple[str, ...]) -> None:
        if node in trail:
            cyclic_nodes.update(trail[trail.index(node):]); return
        for nxt in supersession_graph.get(node, set()): visit(nxt, trail + (node,))
    for node in sorted(supersession_graph): visit(node, ())

    semantic_relations = []
    for claim, relation in relations_raw:
        if not isinstance(relation, dict) or relation.get("type") not in SEMANTIC_RELATIONS:
            quarantined.append(_quarantine("unknown_relation", claim, relation)); continue
        src, dst = lookup.get(relation.get("from"), (None, None)), lookup.get(relation.get("to"), (None, None))
        if src[0] is None or dst[0] is None:
            quarantined.append(_quarantine("unresolved_endpoint", claim, relation)); continue
        domains, ranges = SEMANTIC_RELATIONS[relation["type"]]
        if src[1] not in domains or dst[1] not in ranges:
            quarantined.append(_quarantine("invalid_endpoint_type", claim, relation)); continue
        if relation["type"] == "supersedes":
            if relation.get("from") == relation.get("to") or relation.get("from") in cyclic_nodes or relation.get("to") in cyclic_nodes:
                quarantined.append(_quarantine("supersession_cycle", claim, relation)); continue
            source_obs = json.loads(next(e["observations"][0] for e in semantic_entities if e["name"] == namespace + src[0]))
            target_obs = json.loads(next(e["observations"][0] for e in semantic_entities if e["name"] == namespace + dst[0]))
            newer, older = source_obs.get("effective_at_normalized"), target_obs.get("effective_at_normalized")
            if newer and older and newer < older:
                quarantined.append(_quarantine("temporal_conflict", claim, relation)); continue
        claim_ids = [claim["claim_id"]]
        edge_id = hashlib.sha256((namespace + relation["from"] + relation["type"] + relation["to"] + json.dumps(claim_ids)).encode()).hexdigest()
        semantic_relations.append({"from": namespace + src[0], "to": namespace + dst[0], "relationType": relation["type"],
            "edge_id": edge_id, "source_claim_ids": claim_ids,
            "provenance": {"path": claim["path"], "line": claim["line"], "content_hash": claim["content_hash"]}})
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for relation in semantic_relations:
        key = (relation["from"], relation["to"], relation["relationType"])
        if key not in merged:
            merged[key] = {**relation, "provenance": [relation["provenance"]]}
        else:
            merged[key]["source_claim_ids"] = sorted(set(merged[key]["source_claim_ids"] + relation["source_claim_ids"]))
            merged[key]["provenance"].append(relation["provenance"])
    for relation in merged.values():
        relation["provenance"] = sorted(relation["provenance"], key=canonical_bytes)
        from_id = relation["from"].rsplit(":semantic:", 1)[-1].split(":", 1)[-1] if ":semantic:" in relation["from"] else relation["from"].split(":", 2)[-1]
        to_id = relation["to"].rsplit(":semantic:", 1)[-1].split(":", 1)[-1] if ":semantic:" in relation["to"] else relation["to"].split(":", 2)[-1]
        relation["edge_id"] = hashlib.sha256((namespace + from_id + relation["relationType"] + to_id + json.dumps(relation["source_claim_ids"])).encode()).hexdigest()
    quarantined.sort(key=lambda x: (x["reason_code"], x["source_claim_id"], x["candidate_hash"]))
    return {"semantic_contract_version": SEMANTIC_CONTRACT_VERSION, "semantic_entities": semantic_entities,
            "semantic_relations": sorted(merged.values(), key=lambda x: (x["from"], x["to"], x["relationType"])),
            "semantic_quarantine": quarantined}


def parse_writer_claims(text: str, path: str, secret_policy: str) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    markers = list(WRITER_ID_RE.finditer(text))
    json_comments = list(WRITER_JSON_RE.finditer(text))
    if len(markers) != len(json_comments):
        raise InputError("malformed_metadata", "Writer claim markers and JSON comments are unpaired", {"path": path})
    for index, marker in enumerate(markers):
        line = text.count("\n", 0, marker.start()) + 1
        preceding = [value for value in text[:marker.start()].splitlines() if value.strip()]
        if not preceding or not re.fullmatch(r"#{2,6}\s+.+", preceding[-1]):
            raise InputError("malformed_metadata", "Writer claim marker must follow a section heading", {"path": path, "line": line})
        meta = next((item for item in json_comments if item.start() > marker.end() and (index + 1 == len(markers) or item.start() < markers[index + 1].start())), None)
        if meta is None:
            raise InputError("malformed_metadata", "Writer claim is missing its JSON comment", {"path": path, "line": line})
        boundary = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        heading = HEADING_RE.search(text, meta.end(), boundary)
        section_end = heading.start() if heading else boundary
        fields: dict[str, str] = {}
        for field in FIELD_RE.finditer(text, meta.end(), section_end):
            if field.group(1) in fields:
                raise InputError("malformed_metadata", "Writer claim has duplicate bullet fields", {"path": path, "line": line, "field": field.group(1)})
            fields[field.group(1)] = field.group(2) or ""
        try:
            raw = json.loads(meta.group(1))
        except json.JSONDecodeError as exc:
            raise InputError("malformed_metadata", "Writer claim JSON comment contains invalid JSON", {"path": path, "line": line, "column": exc.colno}) from exc
        claims.append(validate_claim(raw, path, line, secret_policy, fields, marker.group(1)))
    return claims


def inspect_workspace(root: Path, secret_policy: str = "reject") -> dict[str, Any]:
    if not root.is_dir():
        raise InputError("invalid_root", "Workspace root does not exist or is not a directory", {"root": str(root)})
    claims: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    total_bytes = 0
    for file, source_class, authority, relation in recognized_files(root):
        rel = file.relative_to(root).as_posix()
        size = file.stat().st_size
        total_bytes += size
        if total_bytes > MAX_SOURCE_BYTES:
            raise InputError("source_limit", "Canonical memory sources exceed the byte limit", {"limit": MAX_SOURCE_BYTES})
        text = file.read_text(encoding="utf-8")
        source_hash = hashlib.sha256(text.encode()).hexdigest()
        sources.append({"path": rel, "hash": source_hash, "source_class": source_class,
                        "authority_class": authority, "precedence_class": authority})
        if source_class == "memory_claim":
            writer_claims = parse_writer_claims(text, rel, secret_policy)
            claims.extend(writer_claims)
            for match in BLOCK_RE.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                try:
                    raw = json.loads(match.group(1))
                except json.JSONDecodeError as exc:
                    raise InputError("malformed_metadata", "Claim block contains invalid JSON", {"path": rel, "line": line, "column": exc.colno}) from exc
                claims.append(validate_claim(raw, rel, line, secret_policy))
    ids: dict[str, dict[str, Any]] = {}
    for claim in claims:
        if claim["claim_id"] in ids:
            raise InputError("duplicate_claim_id", "Duplicate claim_id", {"claim_id": claim["claim_id"], "paths": sorted([ids[claim["claim_id"]]["path"], claim["path"]])})
        ids[claim["claim_id"]] = claim
    claims.sort(key=lambda x: (x["claim_key"], x["claim_id"], x["path"], x["line"]))
    sources.sort(key=lambda x: x["path"])
    documents.sort(key=lambda x: x["path"])
    sections.sort(key=lambda x: (x["path"], x["line_start"], x["heading_level"], x["heading"]))
    return {"schema_version": SCHEMA_VERSION, "canonical_source": "direct_memory_markdown",
            "claims": claims, "sources": sources, "core_documents": documents,
            "core_sections": sections, "source_digest": digest(sources)}


def build_plan(inspected: dict[str, Any], include_inferred: bool = False, ownership: dict[str, str] | None = None) -> dict[str, Any]:
    claims = inspected["claims"]
    by_id = {c["claim_id"]: c for c in claims}
    superseded_ids = {old for c in claims for old in c["supersedes"]}
    referenced_ids = superseded_ids | {new for c in claims for new in c["superseded_by"]}
    for claim_id in referenced_ids:
        if claim_id not in by_id:
            raise InputError("unknown_superseded_claim", "Supersession references an unknown claim", {"claim_id": claim_id})
    for claim in claims:
        if claim["claim_id"] in claim["supersedes"] or claim["claim_id"] in claim["superseded_by"]:
            raise InputError("inconsistent_supersession", "A claim cannot supersede itself", {"claim_id": claim["claim_id"]})
    candidates = [c for c in claims if c["status"] in ELIGIBLE_STATUS and c["claim_id"] not in superseded_ids and not c["superseded_by"]]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for claim in candidates:
        grouped.setdefault(claim["claim_key"], []).append(claim)
    ambiguous_claim_keys = [
        {"claim_key": key, "claim_ids": sorted(c["claim_id"] for c in vals)}
        for key, vals in sorted(grouped.items()) if len(vals) > 1
    ]
    selected = sorted(candidates, key=lambda x: (x["claim_key"], x["claim_id"]))
    entities: dict[str, dict[str, Any]] = {}
    explicit: list[dict[str, str]] = []
    structural: list[dict[str, str]] = []
    inferred: list[dict[str, str]] = []
    claim_names: dict[str, str] = {}
    key_names = {key: f"claim-key:{key}" for key in grouped}
    reserved_key_names = set(key_names.values())
    source_by_path = {source["path"]: source for source in inspected.get("sources", [])}
    semantic = build_semantic_projection(claims, source_by_path)

    entities["agent:self"] = {"name": "agent:self", "entityType": "Agent", "observations": [json.dumps({"role": "workspace_agent"}, sort_keys=True, separators=(",", ":"))]}
    entities["workspace:self"] = {"name": "workspace:self", "entityType": "Workspace", "observations": [json.dumps({"role": "owner_workspace"}, sort_keys=True, separators=(",", ":"))]}
    structural.append({"from": "agent:self", "to": "workspace:self", "relationType": "operates_in_workspace"})

    # Resolve the whole claim namespace before insertion so no entity can be
    # silently overwritten. Explicit names are accepted only when globally
    # collision-free, including against derived ClaimKey entities.
    for claim in selected:
        entity = claim.get("entity", {})
        if entity and not isinstance(entity, dict):
            raise InputError("malformed_metadata", "entity must be an object", {"claim_id": claim["claim_id"]})
        name = entity.get("name", f"claim:{claim['claim_id']}")
        etype = entity.get("type", "MemoryClaim")
        if not isinstance(name, str) or not name or not isinstance(etype, str) or not etype:
            raise InputError("malformed_metadata", "entity name and type must be non-empty strings", {"claim_id": claim["claim_id"]})
        if name in entities or name in claim_names.values() or name in reserved_key_names:
            colliding = sorted(cid for cid, other_name in claim_names.items() if other_name == name)
            raise InputError("entity_name_collision", "Claim entity name is not collision-free", {"claim_id": claim["claim_id"], "entity_name": name, "collides_with_claim_ids": colliding})
        claim_names[claim["claim_id"]] = name

    for key, name in sorted(key_names.items()):
        entities[name] = {"name": name, "entityType": "ClaimKey", "observations": [json.dumps({"claim_key": key}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))]}

    for claim in selected:
        entity = claim.get("entity", {})
        name = claim_names[claim["claim_id"]]
        etype = entity.get("type", "MemoryClaim")
        source = source_by_path.get(claim["path"], {})
        observation = json.dumps({"claim_id": claim["claim_id"], "claim_key": claim["claim_key"], "status": claim["status"], "supersedes": claim["supersedes"], "superseded_by": claim["superseded_by"], "evidence": claim["evidence"], "claim": claim.get("claim", claim.get("value")), "confidence": claim.get("confidence"), "path": claim["path"], "line": claim["line"], "content_hash": claim["content_hash"], "source_content_hash": source.get("hash"), "source_class": source.get("source_class", "memory_claim"), "authority_class": source.get("authority_class", MEMORY_AUTHORITY), "precedence_class": source.get("precedence_class", MEMORY_AUTHORITY)}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        entities[name] = {"name": name, "entityType": etype, "observations": [observation]}
        structural.append({"from": name, "to": key_names[claim["claim_key"]], "relationType": "has_claim_key"})
        structural.append({"from": "agent:self", "to": name, "relationType": "has_memory_claim"})
        for relation in claim["relations"]:
            explicit.append({"from": name, "to": relation["to"], "relationType": relation["type"]})
        if include_inferred and "." in claim["claim_key"]:
            parent = claim["claim_key"].rsplit(".", 1)[0]
            if parent in grouped and len(grouped[parent]) == 1:
                inferred.append({"from": name, "to": claim_names[grouped[parent][0]["claim_id"]], "relationType": "derived_from_key_namespace"})
    for relation in explicit:
        if relation["from"] not in entities or relation["to"] not in entities:
            raise InputError("dangling_relation", "Explicit relation endpoint is absent from the current graph", relation)
    for entity in semantic["semantic_entities"]:
        entities[entity["name"]] = entity
    for relation in semantic["semantic_relations"]:
        explicit.append({"from": relation["from"], "to": relation["to"], "relationType": relation["relationType"]})
    entity_list = sorted(entities.values(), key=lambda x: x["name"])
    explicit = sorted({tuple(x.values()): x for x in explicit}.values(), key=lambda x: (x["from"], x["to"], x["relationType"]))
    structural = sorted({tuple(x.values()): x for x in structural}.values(), key=lambda x: (x["from"], x["to"], x["relationType"]))
    inferred = sorted({tuple(x.values()): x for x in inferred}.values(), key=lambda x: (x["from"], x["to"], x["relationType"]))
    result = {"schema_version": SCHEMA_VERSION, "canonical": False, "rebuildable": True, "source_digest": inspected["source_digest"], "claims": selected, "core_documents": inspected.get("core_documents", []), "core_sections": inspected.get("core_sections", []), "entities": entity_list, "explicit_relations": explicit, "structural_relations": structural, "inferred_relations": inferred, "conflicts": {"ambiguous_claim_keys": ambiguous_claim_keys}, "excluded_claims": sorted([c["claim_id"] for c in claims if c not in selected]), **{k: semantic[k] for k in ("semantic_contract_version", "semantic_relations", "semantic_quarantine")}}
    result["snapshot_hash"] = digest(result)
    return apply_namespace(result, ownership) if ownership else result


def validate_snapshot(snapshot: Any) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise InputError("invalid_snapshot", "Snapshot must be a JSON object")
    required = {"schema_version", "canonical", "rebuildable", "source_digest", "entities", "explicit_relations", "structural_relations", "inferred_relations", "conflicts", "snapshot_hash"}
    if missing := sorted(required - snapshot.keys()):
        raise InputError("invalid_snapshot", "Snapshot is missing required fields", {"fields": missing})
    allowed = required | {"claims", "core_documents", "core_sections", "excluded_claims", "ownership", "semantic_contract_version", "semantic_relations", "semantic_quarantine"}
    if extra := sorted(snapshot.keys() - allowed):
        raise InputError("invalid_snapshot", "Snapshot contains unsupported fields", {"fields": extra})
    # v0.8 is additive: stored v0.7/schema-v5 snapshots remain valid inputs and
    # can be diffed against a fresh schema-v6 rebuild.
    if snapshot["schema_version"] not in {5, SCHEMA_VERSION} or not isinstance(snapshot["source_digest"], str) or not HASH_RE.fullmatch(snapshot["source_digest"]):
        raise InputError("invalid_snapshot", "Snapshot schema version or source digest is invalid")
    if snapshot["canonical"] is not False or snapshot["rebuildable"] is not True:
        raise InputError("invalid_snapshot", "Snapshot must declare canonical=false and rebuildable=true")
    unhashed = dict(snapshot)
    supplied = unhashed.pop("snapshot_hash")
    if supplied != digest(unhashed):
        raise InputError("invalid_snapshot_hash", "Snapshot hash does not match content")
    if not isinstance(snapshot["entities"], list) or not all(isinstance(e, dict) and set(e) == {"name", "entityType", "observations"} for e in snapshot["entities"]):
        raise InputError("invalid_snapshot", "entities must be an object array")
    names = [e.get("name") for e in snapshot["entities"]]
    valid_entity = all(isinstance(e.get("name"), str) and e["name"] and isinstance(e.get("entityType"), str) and e["entityType"] and isinstance(e.get("observations"), list) and all(isinstance(x, str) for x in e["observations"]) for e in snapshot["entities"])
    if not valid_entity or len(names) != len(set(names)):
        raise InputError("invalid_snapshot", "Entities require unique names, entityType, and string observations")
    endpoints = set(names)
    ownership = snapshot.get("ownership")
    if ownership is not None:
        if (not isinstance(ownership, dict) or set(ownership) != {"agent_id", "workspace_hash", "namespace"}
                or not AGENT_ID_RE.fullmatch(ownership.get("agent_id", ""))
                or not HASH_RE.fullmatch(ownership.get("workspace_hash", ""))
                or not isinstance(ownership.get("namespace"), str)
                or not ownership["namespace"].startswith("memory-graph:v1:")
                or not all(name.startswith(ownership["namespace"]) for name in names)):
            raise InputError("invalid_snapshot", "Snapshot ownership namespace is invalid")
        recomputed = hashlib.sha256(canonical_bytes({"agent_id": ownership["agent_id"], "workspace_hash": ownership["workspace_hash"]})).hexdigest()[:24]
        if ownership["namespace"] != f"memory-graph:v1:{recomputed}:":
            raise InputError("invalid_snapshot", "Snapshot ownership namespace does not match its explicit identity")
    _validate_conflicts(snapshot["conflicts"], "invalid_snapshot")
    ambiguous = snapshot["conflicts"]["ambiguous_claim_keys"]
    for field in ("explicit_relations", "structural_relations", "inferred_relations"):
        relations = snapshot[field]
        if not isinstance(relations, list):
            raise InputError("invalid_snapshot", f"{field} must be an array")
        for relation in relations:
            if not isinstance(relation, dict) or set(relation) != {"from", "to", "relationType"} or not all(isinstance(relation[k], str) and relation[k] for k in relation):
                raise InputError("invalid_snapshot", f"{field} contains an invalid relation")
            if relation["from"] not in endpoints or relation["to"] not in endpoints:
                raise InputError("invalid_snapshot", f"{field} contains a dangling relation", relation)
    entity_types = {e["name"]: e["entityType"] for e in snapshot["entities"]}
    structural_types = {"has_claim_key", "has_memory_claim", "operates_in_workspace", "contains_core_document", "has_section", "follows_persona", "has_identity", "has_user_profile", "follows_policy", "belongs_to_organization_context", "follows_workflow"}  # legacy snapshot cleanup compatibility
    for relation in snapshot["structural_relations"]:
        if relation["relationType"] not in structural_types:
            raise InputError("invalid_snapshot", "structural_relations contains an unsupported structural link", relation)
        if relation["relationType"] == "has_claim_key" and entity_types[relation["to"]] != "ClaimKey":
            raise InputError("invalid_snapshot", "has_claim_key must target a ClaimKey entity", relation)
    return {"valid": True, "schema_version": snapshot["schema_version"], "snapshot_hash": supplied, "entity_count": len(names), "explicit_relation_count": len(snapshot["explicit_relations"]), "structural_relation_count": len(snapshot["structural_relations"]), "inferred_relation_count": len(snapshot["inferred_relations"]), "ambiguous_claim_key_count": len(ambiguous)}


def graph_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(old); validate_snapshot(new)
    if old.get("ownership") is None or old.get("ownership") != new.get("ownership"):
        raise InputError("ownership_mismatch", "Old and new snapshots must have the same recomputed ownership")
    old_e, new_e = {x["name"]: x for x in old["entities"]}, {x["name"]: x for x in new["entities"]}
    old_r = {tuple((x[k] for k in ("from", "to", "relationType"))) for field in ("explicit_relations", "structural_relations") for x in old[field]}
    new_r = {tuple((x[k] for k in ("from", "to", "relationType"))) for field in ("explicit_relations", "structural_relations") for x in new[field]}
    changed = sorted(name for name in old_e.keys() & new_e.keys() if old_e[name] != new_e[name])
    deletes = sorted(old_e.keys() - new_e.keys()) + changed
    creates = sorted(new_e.keys() - old_e.keys()) + changed
    changed_set = set(changed)
    delete_r = (old_r - new_r) | {r for r in old_r if r[0] in changed_set or r[1] in changed_set}
    create_r = (new_r - old_r) | {r for r in new_r if r[0] in changed_set or r[1] in changed_set}
    return {"schema_version": SCHEMA_VERSION, "ownership": new["ownership"], "from_snapshot_hash": old["snapshot_hash"], "to_snapshot_hash": new["snapshot_hash"], "conflicts": new["conflicts"], "delete_relations": [{"from": a, "to": b, "relationType": c} for a,b,c in sorted(delete_r)], "delete_entities": sorted(deletes), "create_entities": [new_e[name] for name in sorted(creates)], "create_relations": [{"from": a, "to": b, "relationType": c} for a,b,c in sorted(create_r)], "unchanged_entities": sorted((old_e.keys() & new_e.keys()) - changed_set)}


def semantic_query(snapshot: dict[str, Any], entity_id: str | None, entity_type: str | None,
                   relation: str | None, direction: str, statuses: str,
                   max_depth: int, max_entities: int, max_edges: int, explain: bool,
                   overlay: dict[str, Any] | None = None, include_inferred: bool = False) -> dict[str, Any]:
    validate_snapshot(snapshot)
    if not 0 <= max_depth <= 3 or not 1 <= max_entities <= 100 or not 1 <= max_edges <= 200:
        raise InputError("query_bounds", "Semantic query exceeds deterministic bounds")
    wanted_status = set(statuses.split(",")) if statuses else {"current", "active"}
    if not wanted_status <= (ALLOWED_STATUS | {"quarantined", "stale_pending_resolution"}):
        raise InputError("query_status", "Semantic query status is unsupported")
    prefix = snapshot.get("ownership", {}).get("namespace", "") + "semantic:"
    entities = {e["name"]: e for e in snapshot["entities"] if e["name"].startswith(prefix)}
    starts = []
    for name, entity in entities.items():
        obs = json.loads(entity["observations"][0])
        grounding_status = {p["status"] for p in obs.get("provenance", [])}
        if entity_id and obs.get("entity_id") != entity_id: continue
        if entity_type and entity["entityType"] != entity_type: continue
        if grounding_status and not grounding_status & wanted_status: continue
        starts.append(name)
    rels = snapshot.get("semantic_relations", [])
    inferred_rels: list[dict[str, Any]] = []
    if include_inferred and overlay is not None:
        if (not isinstance(overlay, dict) or overlay.get("namespace") != snapshot.get("ownership", {}).get("namespace")
                or overlay.get("source_snapshot_hash") != snapshot["snapshot_hash"]
                or overlay.get("overlay_hash") != digest({k: v for k, v in overlay.items() if k != "overlay_hash"})):
            raise InputError("stale_overlay", "Inference overlay is invalid, stale, or cross-namespace")
        inferred_rels = list(overlay.get("inferred_relations", []))
    if relation:
        requested = set(relation.split(","))
        if not requested <= set(SEMANTIC_RELATIONS): raise InputError("query_relation", "Unknown semantic relation")
        rels = [r for r in rels if r["relationType"] in requested]
        inferred_rels = [r for r in inferred_rels if r["relationType"] in requested]
    visited, frontier, edges, inferred_edges = set(starts), sorted(starts), [], []
    for _ in range(max_depth):
        next_frontier = []
        for rel in rels:
            hit = ((direction in {"out", "both"} and rel["from"] in frontier) or
                   (direction in {"in", "both"} and rel["to"] in frontier))
            if hit:
                edges.append(rel)
                other = rel["to"] if rel["from"] in frontier else rel["from"]
                if other in entities and other not in visited: visited.add(other); next_frontier.append(other)
        if include_inferred:
            for rel in inferred_rels:
                hit = ((direction in {"out", "both"} and rel["from"] in frontier) or
                       (direction in {"in", "both"} and rel["to"] in frontier))
                if hit:
                    inferred_edges.append(rel)
                    other = rel["to"] if rel["from"] in frontier else rel["from"]
                    if other in entities and other not in visited: visited.add(other); next_frontier.append(other)
        frontier = sorted(set(next_frontier))
        if not frontier: break
    ordered_entities = [entities[n] for n in sorted(visited)[:max_entities]]
    ordered_edges = sorted({r["edge_id"]: r for r in edges}.values(), key=lambda r: r["edge_id"])[:max_edges]
    hydration = sorted({(p["source_claim_id"], p["path"], p["line"], p["content_hash"])
        for e in ordered_entities for p in json.loads(e["observations"][0]).get("provenance", [])})
    inferred_hits = sorted({edge["inferred_edge_id"]: edge for edge in inferred_edges}.values(),
                           key=lambda edge: (-edge["confidence"], edge["inferred_edge_id"]))[:max_edges]
    return {"canonical": False, "locator_only": True, "namespace": snapshot.get("ownership", {}).get("namespace"),
            "source_digest": snapshot["source_digest"], "snapshot_hash": snapshot["snapshot_hash"],
            "entities": ordered_entities, "edges": ordered_edges, "explicit_relations": ordered_edges,
            "inferred_relations": inferred_hits, "include_inferred": include_inferred,
            "path_classification": "inferred" if inferred_hits else "explicit",
            "hydration_requests": [{"source_claim_id": a, "path": b, "line": c, "content_hash": d} for a,b,c,d in hydration] if explain else [],
            "quarantine": snapshot.get("semantic_quarantine", []) if "quarantined" in wanted_status else [],
            "truncated": len(visited) > max_entities or len(edges) > max_edges or len(inferred_edges) > max_edges,
            "conflicts": snapshot["conflicts"]}


def _inference_candidate_id(namespace: str, candidate: dict[str, Any], extractor: dict[str, str]) -> str:
    parts = (namespace, candidate["source_claim_id"], candidate["source"]["claim_content_hash"],
             candidate["from"]["type"], candidate["from"]["entity_id"], candidate["relation_type"],
             candidate["to"]["type"], candidate["to"]["entity_id"], extractor["name"],
             extractor["version"], extractor["config_hash"])
    return "ic_" + hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()


def _safe_candidate_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _inference_quarantine(namespace: str, reason: str, candidate: Any) -> dict[str, Any]:
    candidate_hash = _safe_candidate_hash(candidate)
    candidate_id = candidate.get("candidate_id") if isinstance(candidate, dict) else None
    if not isinstance(candidate_id, str) or not re.fullmatch(r"ic_[0-9a-f]{64}", candidate_id):
        candidate_id = "ic_" + candidate_hash
    claim_id = candidate.get("source_claim_id", "") if isinstance(candidate, dict) else ""
    if not isinstance(claim_id, str) or secret_like(claim_id):
        claim_id = ""
    source = candidate.get("source", {}) if isinstance(candidate, dict) else {}
    locator = {}
    if isinstance(source, dict):
        if isinstance(source.get("path"), str) and re.fullmatch(r"memory/[^/]+\.md", source["path"]):
            locator["path"] = source["path"]
        for field in ("line_start", "line_end"):
            if isinstance(source.get(field), int) and source[field] > 0:
                locator[field] = source[field]
    safe_key = candidate_id if candidate_id else candidate_hash
    return {"quarantine_id": "iq_" + hashlib.sha256((namespace + safe_key + reason).encode()).hexdigest(),
            "reason_code": reason, "source_claim_id": claim_id,
            "candidate_id": candidate_id, "candidate_hash": candidate_hash, "locator": locator}


def _candidate_shape_reason(candidate: Any) -> str | None:
    if not isinstance(candidate, dict):
        return "id_mismatch"
    if set(candidate) != {"candidate_id", "source_claim_id", "source", "from", "relation_type", "to", "confidence", "basis"}:
        return "id_mismatch"
    source = candidate.get("source")
    endpoint_keys = {"entity_id", "type"}
    if (not isinstance(candidate.get("candidate_id"), str) or not isinstance(candidate.get("source_claim_id"), str)
            or not isinstance(candidate.get("relation_type"), str) or not isinstance(candidate.get("basis"), str)):
        return "id_mismatch"
    if not isinstance(source, dict) or set(source) != {"path", "line_start", "line_end", "source_content_hash", "claim_content_hash"}:
        return "line_mismatch"
    if any(not isinstance(candidate.get(k), dict) or set(candidate[k]) != endpoint_keys for k in ("from", "to")):
        return "invalid_endpoint_type"
    if any(not all(isinstance(endpoint.get(field), str) for field in endpoint_keys)
           for endpoint in (candidate["from"], candidate["to"])):
        return "invalid_endpoint_type"
    return None


def validate_inference_candidates(root: Path, bundle: Any, agent_id: str,
                                  workspace_id: str | None) -> dict[str, Any]:
    """Validate extractor output without repairing, resolving, calling a model, or mutating state."""
    allowed = {"schema_version", "semantic_contract_version", "namespace", "source_snapshot_hash",
               "source_digest", "extractor", "candidates"}
    if not isinstance(bundle, dict) or set(bundle) != allowed:
        raise InputError("invalid_bundle", "Inference bundle has missing or unknown keys")
    extractor = bundle.get("extractor")
    if (bundle.get("schema_version") != INFERENCE_SCHEMA_VERSION
            or bundle.get("semantic_contract_version") != INFERENCE_CONTRACT_VERSION
            or not isinstance(extractor, dict) or set(extractor) != {"name", "version", "config_hash"}
            or extractor.get("name") != "agent-semantic-inference"
            or not isinstance(extractor.get("version"), str) or not ID_RE.fullmatch(extractor["version"])
            or not isinstance(extractor.get("config_hash"), str) or not HASH_RE.fullmatch(extractor["config_hash"])):
        raise InputError("invalid_extractor", "Inference schema or immutable extractor identity is invalid")
    metadata = {key: value for key, value in bundle.items() if key != "candidates"}
    if secret_like(metadata):
        raise InputError("secret_like_bundle", "Secret-like inference bundle metadata rejected")
    candidates = bundle.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > MAX_INFERENCE_CANDIDATES:
        raise InputError("invalid_bundle", "candidates must be a bounded array", {"limit": MAX_INFERENCE_CANDIDATES})
    ownership = namespace_for(agent_id, root, workspace_id)
    if bundle.get("namespace") != ownership["namespace"]:
        raise InputError("namespace_mismatch", "Inference namespace does not match explicit identity")
    inspected = inspect_workspace(root)
    snapshot = build_plan(inspected, False, ownership)
    if bundle.get("source_snapshot_hash") != snapshot["snapshot_hash"] or bundle.get("source_digest") != inspected["source_digest"]:
        raise InputError("stale_snapshot", "Inference bundle does not match the current source snapshot")
    ids: dict[str, bytes] = {}
    for candidate in candidates:
        if isinstance(candidate, dict) and isinstance(candidate.get("candidate_id"), str):
            rendered = canonical_bytes(candidate)
            if candidate["candidate_id"] in ids and ids[candidate["candidate_id"]] != rendered:
                raise InputError("duplicate_candidate_id", "A candidate ID has differing content")
            ids[candidate["candidate_id"]] = rendered
    claims = {claim["claim_id"]: claim for claim in inspected["claims"]}
    sources = {source["path"]: source for source in inspected["sources"]}
    endpoint_names: dict[tuple[str, str], str] = {}
    for entity in snapshot["entities"]:
        if entity["entityType"] not in SEMANTIC_TYPES or not entity["name"].startswith(ownership["namespace"] + "semantic:"):
            continue
        observation = json.loads(entity["observations"][0])
        endpoint_names[(entity["entityType"], observation["entity_id"])] = entity["name"]
    explicit_tuples = {(r["from"], r["relationType"], r["to"]) for r in snapshot["semantic_relations"]}
    checked: list[tuple[dict[str, Any], str | None, dict[str, Any] | None]] = []
    checked_bytes: set[bytes] = set()
    for candidate in candidates:
        rendered_candidate = canonical_bytes(candidate)
        if rendered_candidate in checked_bytes:
            continue
        checked_bytes.add(rendered_candidate)
        reason = _candidate_shape_reason(candidate)
        normalized = None
        if reason is None:
            source = candidate["source"]
            if secret_like(candidate):
                reason = "secret_like_candidate"
            elif candidate["relation_type"] not in SEMANTIC_RELATIONS:
                reason = "unknown_relation"
            elif candidate["basis"] not in {"direct_statement", "direct_causal_statement"}:
                reason = "causality_not_direct" if candidate["relation_type"] == "caused" else "id_mismatch"
            elif (not isinstance(candidate["confidence"], (int, float)) or isinstance(candidate["confidence"], bool)
                  or not math.isfinite(candidate["confidence"]) or not 0 <= candidate["confidence"] <= 1):
                reason = "invalid_confidence"
            elif not isinstance(source["path"], str) or not re.fullmatch(r"memory/[^/]+\.md", source["path"]):
                reason = "stale_source"
            elif source["path"] not in sources:
                reason = "stale_source"
            elif any(not isinstance(source.get(k), int) or isinstance(source[k], bool) or source[k] < 1 for k in ("line_start", "line_end")) or source["line_end"] < source["line_start"]:
                reason = "line_mismatch"
            elif any(not isinstance(source.get(k), str) or not HASH_RE.fullmatch(source[k]) for k in ("source_content_hash", "claim_content_hash")):
                reason = "claim_hash_mismatch"
            elif candidate["source_claim_id"] not in claims:
                reason = "ineligible_claim"
            else:
                claim = claims[candidate["source_claim_id"]]
                path = root / source["path"]
                if path.is_symlink() or not path.is_file() or path.resolve().parent != (root / "memory").resolve():
                    reason = "stale_source"
                else:
                    raw = path.read_bytes()
                    if hashlib.sha256(raw).hexdigest() != source["source_content_hash"] or source["source_content_hash"] != sources[source["path"]]["hash"]:
                        reason = "stale_source"
                    elif claim["path"] != source["path"] or claim["content_hash"] != source["claim_content_hash"]:
                        reason = "claim_hash_mismatch"
                    elif claim["status"] not in ELIGIBLE_STATUS or claim not in snapshot["claims"]:
                        reason = "ineligible_claim"
                    else:
                        lines = raw.decode("utf-8").splitlines()
                        selected = "\n".join(lines[source["line_start"] - 1:source["line_end"]]) if source["line_end"] <= len(lines) else ""
                        marker = f"openclaw-memory-claim:{claim['claim_id']}"
                        legacy = "```memory-claim"
                        if source["line_end"] > len(lines) or claim["line"] < source["line_start"] or claim["line"] > source["line_end"] or (marker not in selected and legacy not in selected):
                            reason = "line_mismatch"
                        elif candidate["relation_type"] == "caused" and (candidate["basis"] != "direct_causal_statement" or not re.search(r"(?i)\b(?:caused|because|led to|resulted in|triggered|due to)\b", selected)):
                            reason = "causality_not_direct"
            if reason is None:
                frm, to = candidate["from"], candidate["to"]
                if frm["type"] not in SEMANTIC_TYPES or to["type"] not in SEMANTIC_TYPES:
                    reason = "invalid_endpoint_type"
                elif any(endpoint["entity_id"].startswith("memory-graph:v1:") for endpoint in (frm, to)):
                    reason = "cross_namespace_endpoint"
                else:
                    domains, ranges = SEMANTIC_RELATIONS[candidate["relation_type"]]
                    if frm["type"] not in domains or to["type"] not in ranges:
                        reason = "invalid_endpoint_type"
                if reason is None and ((frm["type"], frm["entity_id"]) not in endpoint_names or (to["type"], to["entity_id"]) not in endpoint_names):
                    reason = "unresolved_explicit_endpoint"
                elif reason is None and frm == to:
                    reason = "self_relation"
                elif reason is None:
                    if candidate["candidate_id"] != _inference_candidate_id(ownership["namespace"], candidate, extractor):
                        reason = "id_mismatch"
                    else:
                        normalized = {**candidate, "confidence": candidate["confidence"] + 0.0,
                            "from_name": endpoint_names[(frm["type"], frm["entity_id"])],
                            "to_name": endpoint_names[(to["type"], to["entity_id"])]}
                        if (normalized["from_name"], candidate["relation_type"], normalized["to_name"]) in explicit_tuples:
                            reason = "shadowed_by_explicit"
        checked.append((candidate, reason, normalized))
    # Supersession candidates must remain acyclic as one inert component.
    supersession_graph: dict[str, set[str]] = {}
    for _, reason, normalized in checked:
        if reason is None and normalized and normalized["relation_type"] == "supersedes":
            supersession_graph.setdefault(normalized["from"]["entity_id"], set()).add(normalized["to"]["entity_id"])
    cyclic: set[str] = set()
    def inference_visit(node: str, trail: tuple[str, ...]) -> None:
        if node in trail:
            cyclic.update(trail[trail.index(node):]); return
        for nxt in supersession_graph.get(node, set()):
            inference_visit(nxt, trail + (node,))
    for node in sorted(supersession_graph):
        inference_visit(node, ())
    checked = [(candidate,
                "supersession_cycle" if reason is None and normalized and normalized["relation_type"] == "supersedes"
                and (normalized["from"]["entity_id"] in cyclic or normalized["to"]["entity_id"] in cyclic) else reason,
                normalized) for candidate, reason, normalized in checked]
    # Deterministically quarantine all mutually contradictory alternatives.
    groups: dict[tuple[str, str, str], set[str]] = {}
    for candidate, reason, normalized in checked:
        if reason is None and normalized:
            key = (candidate["source_claim_id"], normalized["from_name"], candidate["relation_type"])
            groups.setdefault(key, set()).add(normalized["to_name"])
    contradictory = {key for key, targets in groups.items() if len(targets) > 1}
    accepted, quarantine = [], []
    seen = set()
    for candidate, reason, normalized in checked:
        if reason is None and normalized and (candidate["source_claim_id"], normalized["from_name"], candidate["relation_type"]) in contradictory:
            reason = "contradictory_candidates"
        if reason is None and normalized:
            canonical = {k: v for k, v in normalized.items() if k not in {"from_name", "to_name"}}
            key = canonical_bytes(canonical)
            if key not in seen:
                seen.add(key); accepted.append(canonical)
        else:
            quarantine.append(_inference_quarantine(ownership["namespace"], reason or "id_mismatch", candidate))
    accepted.sort(key=lambda c: c["candidate_id"])
    quarantine.sort(key=lambda q: (q["reason_code"], q["source_claim_id"], q["candidate_id"]))
    normalized_bundle = {**metadata, "candidates": sorted(candidates, key=canonical_bytes)}
    return {"schema_version": INFERENCE_SCHEMA_VERSION, "semantic_contract_version": INFERENCE_CONTRACT_VERSION,
            "namespace": ownership["namespace"], "source_snapshot_hash": snapshot["snapshot_hash"],
            "source_digest": inspected["source_digest"], "extractor": extractor,
            "candidate_bundle_hash": digest(normalized_bundle), "accepted_candidates": accepted,
            "quarantine": quarantine, "accepted_count": len(accepted), "quarantine_count": len(quarantine),
            "fresh": True, "canonical": False, "locator_only": True}


def project_inference_overlay(validated: dict[str, Any]) -> dict[str, Any]:
    inferred = []
    namespace = validated["namespace"]
    extractor = validated["extractor"]
    for candidate in validated["accepted_candidates"]:
        inferred.append({"inferred_edge_id": "ie_" + hashlib.sha256((namespace + candidate["candidate_id"]).encode()).hexdigest(),
            "candidate_id": candidate["candidate_id"], "from": namespace + "semantic:" + candidate["from"]["type"] + ":" + candidate["from"]["entity_id"],
            "to": namespace + "semantic:" + candidate["to"]["type"] + ":" + candidate["to"]["entity_id"],
            "relationType": candidate["relation_type"], "source_claim_id": candidate["source_claim_id"],
            "locator": candidate["source"], "confidence": candidate["confidence"], "basis": candidate["basis"],
            "extractor": extractor, "semantic_contract_version": INFERENCE_CONTRACT_VERSION,
            "namespace": namespace, "source_snapshot_hash": validated["source_snapshot_hash"],
            "inferred": True, "canonical": False, "locator_only": True})
    inferred.sort(key=lambda edge: edge["inferred_edge_id"])
    payload = {"schema_version": "memory-graph-inference-overlay/v1", "semantic_contract_version": INFERENCE_CONTRACT_VERSION,
               "namespace": namespace, "source_snapshot_hash": validated["source_snapshot_hash"],
               "source_digest": validated["source_digest"], "candidate_bundle_hash": validated["candidate_bundle_hash"],
               "inferred_relations": inferred, "quarantine": validated["quarantine"],
               "canonical": False, "locator_only": True}
    payload["overlay_hash"] = digest(payload)
    return payload


def cache_inference_overlay(state_root: Path, validated: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    namespace = validated["namespace"]
    owner = namespace.removeprefix("memory-graph:v1:").removesuffix(":")
    if not re.fullmatch(r"[0-9a-f]{24}", owner):
        raise InputError("unsafe_state_path", "Inference cache namespace is invalid")
    lexical_state_root = state_root.absolute()
    cursor = Path(lexical_state_root.anchor)
    for part in lexical_state_root.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise InputError("unsafe_state_path", "State root and its parents must not be symlinks")
    state_root = lexical_state_root.resolve()
    if state_root.exists() and not state_root.is_dir():
        raise InputError("unsafe_state_path", "State root must be a regular directory")
    extractor = validated["extractor"]
    cache_key = hashlib.sha256("".join((namespace, validated["source_snapshot_hash"], extractor["name"],
        extractor["version"], extractor["config_hash"], validated["candidate_bundle_hash"],
        INFERENCE_CONTRACT_VERSION)).encode()).hexdigest()
    target = state_root / owner / "inference" / (cache_key + ".json")
    value = {"cache_key": cache_key, "namespace": namespace, "source_snapshot_hash": validated["source_snapshot_hash"],
             "source_digest": validated["source_digest"], "extractor": extractor,
             "candidate_bundle_hash": validated["candidate_bundle_hash"], "semantic_contract_version": INFERENCE_CONTRACT_VERSION,
             "overlay": overlay, "quarantine": validated["quarantine"]}
    hit = False
    if target.exists():
        if target.is_symlink() or not target.is_file():
            raise InputError("unsafe_state_path", "Inference cache entry must be a regular file")
        try:
            hit = json.loads(target.read_text(encoding="utf-8")) == value
        except json.JSONDecodeError:
            hit = False
    cache_dir = target.parent
    removed = []
    if cache_dir.exists():
        for entry in sorted(cache_dir.iterdir()):
            if entry == target:
                continue
            if entry.is_symlink() or not entry.is_file() or not re.fullmatch(r"[0-9a-f]{64}\.json", entry.name):
                raise InputError("unsafe_state_path", "Inference cache contains an unsafe entry")
            entry.unlink()
            removed.append(entry.name)
    if not hit:
        atomic_private_json(target, value)
    elif (target.stat().st_mode & 0o777) != 0o600:
        os.chmod(target, 0o600)
    return {"cache_key": cache_key, "cache_hit": hit, "cache_path": f"{owner}/inference/{cache_key}.json",
            "removed_stale_entries": removed, "mode": "0600"}


def export_visualization(snapshot: dict[str, Any], overlay: dict[str, Any] | None,
                         include_inferred: bool) -> dict[str, Any]:
    validate_snapshot(snapshot)
    explicit = [{**edge, "line_style": "solid", "label": "Explicit", "inferred": False}
                for edge in snapshot.get("semantic_relations", [])]
    inferred: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    if include_inferred and overlay is not None:
        if (overlay.get("namespace") != snapshot.get("ownership", {}).get("namespace")
                or overlay.get("source_snapshot_hash") != snapshot["snapshot_hash"]
                or overlay.get("overlay_hash") != digest({k: v for k, v in overlay.items() if k != "overlay_hash"})):
            raise InputError("stale_overlay", "Inference overlay is invalid, stale, or cross-namespace")
        inferred = [{**edge, "line_style": "dashed", "label": f"Inferred, noncanonical ({edge['confidence']:.2f})"}
                    for edge in overlay.get("inferred_relations", [])]
        quarantine = overlay.get("quarantine", [])
    return {"schema_version": "memory-graph-visualization/v1", "namespace": snapshot.get("ownership", {}).get("namespace"),
            "explicit_relations": explicit, "inferred_relations": inferred,
            "legend": [{"label": "Explicit", "line_style": "solid"},
                       {"label": "Inferred, noncanonical", "line_style": "dashed"}],
            "quarantine_panel": quarantine, "color_only": False, "canonical": False}


def _validate_conflicts(conflicts: Any, code: str) -> None:
    if not isinstance(conflicts, dict) or set(conflicts) != {"ambiguous_claim_keys"}:
        raise InputError(code, "conflicts has an invalid shape")
    groups = conflicts["ambiguous_claim_keys"]
    if not isinstance(groups, list) or groups != sorted(groups, key=lambda x: x.get("claim_key", "") if isinstance(x, dict) else ""):
        raise InputError(code, "ambiguous claim-key conflicts must be an ordered array")
    for group in groups:
        if (not isinstance(group, dict) or set(group) != {"claim_key", "claim_ids"}
                or not isinstance(group["claim_key"], str) or not group["claim_key"]
                or not isinstance(group["claim_ids"], list) or len(group["claim_ids"]) < 2
                or group["claim_ids"] != sorted(set(group["claim_ids"]))
                or not all(isinstance(x, str) and ID_RE.fullmatch(x) for x in group["claim_ids"])):
            raise InputError(code, "conflicts contains an invalid ambiguity group")


def _validate_entities(entities: Any, code: str) -> list[str]:
    if not isinstance(entities, list):
        raise InputError(code, "create_entities must be an array")
    names: list[str] = []
    for entity in entities:
        if (not isinstance(entity, dict) or set(entity) != {"name", "entityType", "observations"}
                or not isinstance(entity["name"], str) or not entity["name"]
                or not isinstance(entity["entityType"], str) or not entity["entityType"]
                or not isinstance(entity["observations"], list)
                or not all(isinstance(x, str) for x in entity["observations"])):
            raise InputError(code, "create_entities contains an invalid entity")
        names.append(entity["name"])
    if names != sorted(set(names)):
        raise InputError(code, "create entity names must be unique and ordered")
    return names


def _validate_relations(relations: Any, field: str, code: str) -> list[tuple[str, str, str]]:
    if not isinstance(relations, list):
        raise InputError(code, f"{field} must be an array")
    result = []
    for relation in relations:
        if (not isinstance(relation, dict) or set(relation) != {"from", "to", "relationType"}
                or not all(isinstance(relation[k], str) and relation[k] for k in ("from", "to", "relationType"))):
            raise InputError(code, f"{field} contains an invalid relation")
        result.append((relation["from"], relation["to"], relation["relationType"]))
    if result != sorted(set(result)):
        raise InputError(code, f"{field} relations must be unique and ordered")
    return result


def validate_diff(value: Any) -> dict[str, Any]:
    code = "invalid_diff"
    allowed = {"schema_version", "ownership", "from_snapshot_hash", "to_snapshot_hash", "conflicts", "delete_relations", "delete_entities", "create_entities", "create_relations", "unchanged_entities"}
    if not isinstance(value, dict) or set(value) != allowed or value.get("schema_version") != SCHEMA_VERSION:
        raise InputError(code, "Diff must contain exactly the supported fields and schema version")
    if not all(isinstance(value[k], str) and HASH_RE.fullmatch(value[k]) for k in ("from_snapshot_hash", "to_snapshot_hash")):
        raise InputError(code, "Diff snapshot hashes must be lowercase SHA-256 values")
    ownership = value["ownership"]
    if not isinstance(ownership, dict) or set(ownership) != {"agent_id", "workspace_hash", "namespace"}:
        raise InputError(code, "Diff ownership is invalid")
    expected = f"memory-graph:v1:{hashlib.sha256(canonical_bytes({'agent_id': ownership.get('agent_id'), 'workspace_hash': ownership.get('workspace_hash')})).hexdigest()[:24]}:"
    if ownership.get("namespace") != expected:
        raise InputError(code, "Diff ownership namespace does not match its explicit identity")
    _validate_conflicts(value["conflicts"], code)
    deleted = value["delete_entities"]
    unchanged = value["unchanged_entities"]
    if (not isinstance(deleted, list) or deleted != sorted(set(deleted)) or not all(isinstance(x, str) and x for x in deleted)
            or not isinstance(unchanged, list) or unchanged != sorted(set(unchanged)) or not all(isinstance(x, str) and x for x in unchanged)):
        raise InputError(code, "Entity name arrays must contain unique ordered non-empty strings")
    created = _validate_entities(value["create_entities"], code)
    if set(deleted) & set(unchanged) or set(created) & set(unchanged):
        raise InputError(code, "Diff entity sets conflict")
    old_endpoints, new_endpoints = set(deleted) | set(unchanged), set(created) | set(unchanged)
    for relation in _validate_relations(value["delete_relations"], "delete_relations", code):
        if relation[0] not in old_endpoints or relation[1] not in old_endpoints:
            raise InputError(code, "delete_relations contains an invalid old endpoint")
    for relation in _validate_relations(value["create_relations"], "create_relations", code):
        if relation[0] not in new_endpoints or relation[1] not in new_endpoints:
            raise InputError(code, "create_relations contains an invalid new endpoint")
    return value


def export_batches(value: dict[str, Any], include_inferred: bool, batch_size: int) -> dict[str, Any]:
    if batch_size < 1 or batch_size > 1000:
        raise InputError("invalid_batch_size", "batch-size must be between 1 and 1000")
    batches: list[dict[str, Any]] = []
    def add(tool: str, key: str, items: list[Any]) -> None:
        batches.extend(mutation_batches("mcporter", tool, key, items, batch_size))
    if "entities" in value:
        validate_snapshot(value)
        add("create_entities", "entities", value["entities"])
        rels = value["explicit_relations"] + value["structural_relations"] + (value["inferred_relations"] if include_inferred else [])
        add("create_relations", "relations", sorted(rels, key=lambda x: (x["from"], x["to"], x["relationType"])))
    else:
        validate_diff(value)
        add("delete_relations", "relations", value.get("delete_relations", []))
        add("delete_entities", "entityNames", value.get("delete_entities", []))
        add("create_entities", "entities", value.get("create_entities", []))
        add("create_relations", "relations", value.get("create_relations", []))
    return {"schema_version": SCHEMA_VERSION, "memory_mcp_compatible": True, "mutation_performed": False, "conflicts": value.get("conflicts", {"ambiguous_claim_keys": []}), "batches": batches}


def load_json(path: str, root: Path) -> Any:
    target = safe_resolve(root, path)
    if not target.is_file():
        raise InputError("missing_snapshot", "JSON input file does not exist", {"path": path})
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InputError("invalid_json", "Input file contains invalid JSON", {"path": path, "line": exc.lineno, "column": exc.colno}) from exc


def load_inference_bundle(path: str, root: Path) -> tuple[Any, str]:
    """Bounded, regular-file-only JSON load for untrusted extractor output."""
    raw_path = Path(path)
    lexical = raw_path if raw_path.is_absolute() else root / raw_path
    cursor = Path(lexical.anchor) if lexical.is_absolute() else Path()
    for part in lexical.parts[1:] if lexical.is_absolute() else lexical.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise InputError("invalid_bundle", "Inference input must be a regular non-symlink file")
    target = safe_resolve(root, path)
    if target.is_symlink() or not target.is_file():
        raise InputError("invalid_bundle", "Inference input must be a regular non-symlink file")
    raw = target.read_bytes()
    if len(raw) > MAX_INFERENCE_BUNDLE_BYTES:
        raise InputError("oversized_bundle", "Inference candidate bundle exceeds the byte limit",
                         {"limit": MAX_INFERENCE_BUNDLE_BYTES})
    try:
        return json.loads(raw), hashlib.sha256(raw).hexdigest()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InputError("malformed_bundle", "Inference candidate bundle is not valid UTF-8 JSON") from exc


def load_semantic_bundle(path: str, root: Path) -> Any:
    """Bounded, regular-file-only JSON load for the semantic authoring lane."""
    raw_path = Path(path); lexical = raw_path if raw_path.is_absolute() else root / raw_path
    cursor = Path(lexical.anchor) if lexical.is_absolute() else Path()
    for part in lexical.parts[1:] if lexical.is_absolute() else lexical.parts:
        cursor = cursor / part
        if cursor.is_symlink(): raise InputError("invalid_semantic_bundle", "Semantic input must be a regular non-symlink file")
    target = safe_resolve(root, path)
    if target.is_symlink() or not target.is_file(): raise InputError("invalid_semantic_bundle", "Semantic input must be a regular non-symlink file")
    raw = target.read_bytes()
    if len(raw) > MAX_INFERENCE_BUNDLE_BYTES: raise InputError("oversized_semantic_bundle", "Semantic input exceeds the 1 MiB byte limit", {"limit":MAX_INFERENCE_BUNDLE_BYTES})
    try: value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc: raise InputError("malformed_semantic_bundle", "Semantic input is not valid UTF-8 JSON") from exc
    # Bound parser output as well as bytes.  Small, deeply nested JSON can exhaust
    # recursion, and huge collections/strings make later canonicalization costly.
    items = 0
    def check(node: Any, depth: int = 0) -> None:
        nonlocal items
        if depth > 32: raise InputError("complex_semantic_bundle", "Semantic input nesting exceeds 32 levels")
        items += 1
        if items > 10000: raise InputError("complex_semantic_bundle", "Semantic input exceeds 10000 JSON values")
        if isinstance(node, str) and len(node) > 16384: raise InputError("complex_semantic_bundle", "Semantic string exceeds 16384 characters")
        if isinstance(node, dict):
            if len(node) > 256: raise InputError("complex_semantic_bundle", "Semantic object exceeds 256 members")
            for key, child in node.items():
                if len(key) > 256: raise InputError("complex_semantic_bundle", "Semantic object key exceeds 256 characters")
                check(child, depth + 1)
        elif isinstance(node, list):
            if len(node) > 2000: raise InputError("complex_semantic_bundle", "Semantic array exceeds 2000 items")
            for child in node: check(child, depth + 1)
    check(value)
    return value


def atomic_private_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or path.is_symlink():
        raise InputError("unsafe_state_path", "Private state paths must not be symlinks")
    os.chmod(path.parent, 0o700)
    fd, raw = tempfile.mkstemp(prefix=".memory-graph-", dir=path.parent)
    tmp = Path(raw)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_bytes(value) + b"\n")
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if tmp.exists():
            tmp.unlink()


def mcp_run(argv: list[str], timeout_seconds: float) -> Any:
    stdout_file = tempfile.TemporaryFile()
    stderr_file = tempfile.TemporaryFile()
    try:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=stdout_file, stderr=stderr_file)
        deadline = time.monotonic() + timeout_seconds
        while process.poll() is None:
            if stdout_file.tell() > MAX_MCP_OUTPUT_BYTES or stderr_file.tell() > MAX_MCP_OUTPUT_BYTES:
                process.kill(); process.wait()
                raise InputError("backend_output_limit", "Memory MCP command output exceeded the safety limit")
            if time.monotonic() >= deadline:
                process.kill(); process.wait()
                raise InputError("backend_unavailable", "Memory MCP command was unavailable or timed out", {"type": "TimeoutExpired"})
            time.sleep(0.01)
        stdout_file.seek(0); stderr_file.seek(0)
        stdout = stdout_file.read(MAX_MCP_OUTPUT_BYTES + 1)
        stderr = stderr_file.read(MAX_MCP_OUTPUT_BYTES + 1)
    except OSError as exc:
        details = {"type": type(exc).__name__, "errno": exc.errno, "spawned": False,
                   "mutation_definitely_not_performed": True}
        if exc.errno == errno.ENOENT:
            raise InputError("backend_unavailable",
                "Memory MCP backend executable is unavailable", details) from exc
        if exc.errno == errno.E2BIG:
            raise InputError("backend_argv_too_large",
                "Memory MCP argv exceeded the operating-system limit before spawn; no mutation occurred", details) from exc
        raise InputError("backend_unavailable", "Memory MCP command could not be spawned", details) from exc
    finally:
        stdout_file.close(); stderr_file.close()
    if len(stdout) > MAX_MCP_OUTPUT_BYTES or len(stderr) > MAX_MCP_OUTPUT_BYTES:
        raise InputError("backend_output_limit", "Memory MCP command output exceeded the safety limit")
    if process.returncode:
        raise InputError("backend_failure", "Memory MCP command failed", {"returncode": process.returncode})
    text = stdout.decode("utf-8", "replace").strip()
    try:
        return json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise InputError("backend_parse_error", "Memory MCP command returned invalid JSON") from exc


def mcp_call(executable: str, tool: str, arguments: dict[str, Any], timeout_seconds: float) -> Any:
    return mcp_run(mcp_argv(executable, tool, arguments), timeout_seconds)


def _graph_payload(value: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if isinstance(value, dict):
        if isinstance(value.get("entities"), list) and isinstance(value.get("relations"), list):
            return value["entities"], value["relations"]
        for child in value.values():
            entities, relations = _graph_payload(child)
            if entities or relations:
                return entities, relations
    if isinstance(value, list):
        for child in value:
            entities, relations = _graph_payload(child)
            if entities or relations:
                return entities, relations
    return [], []


REQUIRED_MCP_SIGNATURES = {
    "create_entities": "entities", "create_relations": "relations",
    "delete_entities": "entityNames", "delete_relations": "relations",
    "read_graph": None, "open_nodes": "names",
}


def verify_mcp_schema(value: Any) -> None:
    found: dict[str, set[str]] = {}
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            name = node.get("name")
            schema = node.get("inputSchema", node.get("input_schema"))
            if isinstance(name, str) and isinstance(schema, dict):
                properties = schema.get("properties", {})
                required = schema.get("required", [])
                if isinstance(properties, dict) and isinstance(required, list):
                    found[name.split(".")[-1]] = set(properties) & set(required)
            for child in node.values(): walk(child)
        elif isinstance(node, list):
            for child in node: walk(child)
    walk(value)
    bad = []
    for name, argument in REQUIRED_MCP_SIGNATURES.items():
        if name not in found or (argument is not None and argument not in found[name]): bad.append(name)
    if bad:
        raise InputError("backend_schema_mismatch", "Registered Memory MCP tool signatures are incompatible", {"tools": bad})


def backend_view(value: Any, ownership: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    entities, relations = _graph_payload(value)
    prefix = ownership["namespace"]
    owned = [e for e in entities if isinstance(e, dict) and str(e.get("name", "")).startswith(prefix)]
    if any(set(e) != {"name", "entityType", "observations"} or not isinstance(e.get("entityType"), str)
           or not isinstance(e.get("observations"), list) or not all(isinstance(x, str) for x in e["observations"]) for e in owned):
        raise InputError("backend_corruption", "Backend contains malformed owned entities")
    owned_names = {e.get("name") for e in owned}
    internal, foreign = [], []
    for relation in relations:
        if not isinstance(relation, dict): continue
        a, b = relation.get("from"), relation.get("to")
        if a in owned_names or b in owned_names:
            if set(relation) != {"from", "to", "relationType"} or not all(isinstance(relation.get(k), str) for k in ("from", "to", "relationType")):
                raise InputError("backend_corruption", "Backend contains malformed owned incident relations")
            (internal if a in owned_names and b in owned_names else foreign).append(relation)
    entity_keys = [e["name"] for e in owned]
    relation_keys = [(r["from"], r["to"], r["relationType"]) for r in internal + foreign]
    if len(entity_keys) != len(set(entity_keys)) or len(relation_keys) != len(set(relation_keys)):
        raise InputError("backend_corruption", "Backend contains duplicate owned or incident records")
    snapshot = {"schema_version": SCHEMA_VERSION, "canonical": False, "rebuildable": True,
        "source_digest": digest([]), "claims": [], "core_documents": [], "core_sections": [],
        "entities": sorted(owned, key=lambda x: x["name"]),
        "explicit_relations": sorted(internal, key=lambda x: (x["from"], x["to"], x["relationType"])),
        "structural_relations": [], "inferred_relations": [], "conflicts": {"ambiguous_claim_keys": []},
        "excluded_claims": [], "ownership": ownership}
    snapshot["snapshot_hash"] = digest(snapshot)
    inbound = sorted([r for r in foreign if r.get("to") in owned_names], key=canonical_bytes)
    outbound = sorted([r for r in foreign if r.get("from") in owned_names], key=canonical_bytes)
    return snapshot, inbound, outbound


def exact_remaining(current: dict[str, Any], target: dict[str, Any], inbound: list[dict[str, str]],
                    outbound: list[dict[str, str]], executable: str = "mcporter") -> list[dict[str, Any]]:
    delta = graph_diff(current, target)
    deleting = set(delta["delete_entities"])
    changed = deleting & {e["name"] for e in delta["create_entities"]}
    stale_incident = [r for r in inbound if r["from"] in deleting or r["to"] in deleting]
    foreign_delete = stale_incident + outbound
    foreign_restore = [r for r in stale_incident if r["from"] in changed or r["to"] in changed]
    batches: list[dict[str, Any]] = []
    def add(tool: str, key: str, items: list[Any]) -> None:
        batches.extend(mutation_batches(executable, tool, key, items))
    add("delete_relations", "relations", sorted(delta["delete_relations"] + foreign_delete, key=canonical_bytes))
    add("delete_entities", "entityNames", delta["delete_entities"])
    add("create_entities", "entities", delta["create_entities"])
    add("create_relations", "relations", sorted(delta["create_relations"] + foreign_restore, key=canonical_bytes))
    return batches


def fault_point(name: str) -> None:
    if os.environ.get("MEMORY_GRAPH_FAULT") == name:
        raise OSError(f"fault injection: {name}")


def cron_plan(root: Path, agent_id: str, workspace_id: str | None, state_root: str, timezone: str) -> dict[str, Any]:
    ownership = namespace_for(agent_id, root, workspace_id)
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InputError("invalid_timezone", "A registered IANA timezone is required; UTC is never inferred", {"timezone": timezone}) from exc
    if zone.key != timezone:
        raise InputError("invalid_timezone", "Timezone must be an explicit canonical IANA key")
    cron_hash = hashlib.sha256(canonical_bytes({"capability":"memory-graph", **ownership})).hexdigest()[:20]
    name = f"memory-graph-daily-{cron_hash}"
    identity = f"root={root}; agentId={agent_id}; stateRoot={state_root}"
    if workspace_id is not None: identity += f"; workspaceId={workspace_id}"
    message = ("Daily memory-graph reconciliation under the owner's standing authorization. "
        "Select the memory-graph Skill and use only this identity: " + identity + ". "
        "Compute the canonical source digest; if unchanged, make no graph mutations and stay silent. "
        "If changed, call trusted Gateway harness.run.prepare for memory-graph onboard with the exact identity, "
        "then call harness.run with the matching approvalIntentHash without asking again. Verify the exact owned "
        "namespace and representative retrieval. Report only failures or material graph changes. Never modify "
        "Markdown, another namespace, or publish externally.")
    cron_add = {"name": name, "description": f"Owned daily Memory Graph reconcile for {ownership['namespace']}",
        "agentId": agent_id, "enabled": True,
        "schedule": {"kind": "cron", "expr": "0 0 * * *", "tz": timezone},
        "sessionTarget": "isolated", "wakeMode": "now",
        "payload": {"kind": "agentTurn", "message": message}, "delivery": {"mode": "none"}}
    return {"name": name, "cron_add": cron_add, "match": {"name": name, "agentId": agent_id, "sessionTarget": "isolated"},
            "server_generated_id": True,
            "namespace": ownership["namespace"], "source_digest_noop": True, "overlap_prevented_by_namespace_lock": True,
            "failure_policy": "resume_on_next_daily_run"}


def onboard(root: Path, agent_id: str, workspace_id: str | None, state_root: Path,
            executable: str, timeout_seconds: float, secret_policy: str) -> dict[str, Any]:
    deadline = time.monotonic() + 30.0
    def bounded_timeout() -> float:
        remaining = deadline - time.monotonic()
        if remaining < 0.1:
            raise InputError("backend_unavailable", "Memory MCP onboarding exceeded its total time bound")
        return min(timeout_seconds, remaining)
    ownership = namespace_for(agent_id, root, workspace_id)
    if state_root.is_symlink():
        raise InputError("unsafe_state_path", "State root must not be a symlink")
    state_root = state_root.resolve()
    state_dir = state_root / ownership["namespace"].split(":")[-2]
    state_file, journal_file, lock_file = state_dir / "snapshot.json", state_dir / "journal.json", state_dir / "lock"
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700); os.chmod(state_dir, 0o700)
    lock_fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
    os.fchmod(lock_fd, 0o600)
    try:
        try: fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc: raise InputError("onboard_locked", "This namespace is already onboarding") from exc
        inspected = inspect_workspace(root, secret_policy)
        target = build_plan(inspected, False, ownership)
        prior = {}
        if journal_file.is_file():
            try: prior = json.loads(journal_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc: raise InputError("invalid_private_state", "Private journal is malformed") from exc
        transaction_id = prior.get("transaction_id", 0)
        if not isinstance(transaction_id, int) or transaction_id < 0: raise InputError("invalid_private_state", "Private transaction ID is invalid")
        transaction_id += 1
        journal = {"status": "prepared", "transaction_id": transaction_id, "ownership": ownership,
                   "source_digest": target["source_digest"], "snapshot_hash": target["snapshot_hash"],
                   "target_snapshot": target, "applied_batches": 0, "updated_unix": int(time.time())}
        atomic_private_json(journal_file, journal); fault_point("prepared")
        schema_result = mcp_run([executable, "list", "memory", "--schema", "--json"], bounded_timeout())
        verify_mcp_schema(schema_result); fault_point("schema_verified")
        graph = mcp_call(executable, "read_graph", {}, bounded_timeout())
        current, inbound, outbound = backend_view(graph, ownership); fault_point("backend_discovered")
        initial_inbound = list(inbound)
        applied = 0
        while True:
            batches = exact_remaining(current, target, inbound, outbound, executable)
            if not batches: break
            batch = batches[0]
            journal["status"] = "applying"; journal["next_tool"] = batch["tool"]
            journal["mutation_attempt"] = {"status": "dispatching", "tool": batch["tool"],
                "transaction_id": transaction_id, "namespace": ownership["namespace"],
                "arguments_hash": digest(batch["arguments"]), "reconciliation_required": True}
            atomic_private_json(journal_file, journal); fault_point("before_mutation")
            mcp_call(executable, batch["tool"], batch["arguments"], bounded_timeout())
            applied += 1; journal["applied_batches"] = applied
            fault_point("after_mutation")
            journal["mutation_attempt"]["status"] = "confirmed"
            journal["mutation_attempt"]["reconciliation_required"] = False
            atomic_private_json(journal_file, journal); fault_point("progress_recorded")
            graph = mcp_call(executable, "read_graph", {}, bounded_timeout())
            current, inbound, outbound = backend_view(graph, ownership)
        graph = mcp_call(executable, "read_graph", {}, bounded_timeout())
        current, final_inbound, final_outbound = backend_view(graph, ownership)
        expected_entities = sorted(target["entities"], key=canonical_bytes)
        actual_entities = sorted(current["entities"], key=canonical_bytes)
        expected_relations = sorted(target["explicit_relations"] + target["structural_relations"], key=canonical_bytes)
        actual_relations = sorted(current["explicit_relations"], key=canonical_bytes)
        if actual_entities != expected_entities or actual_relations != expected_relations or final_outbound:
            raise InputError("verification_failed", "Owned entities and exact incident relations do not match the target",
                {"expected_entities": len(expected_entities), "actual_entities": len(actual_entities),
                 "expected_relations": len(expected_relations), "actual_relations": len(actual_relations),
                 "foreign_inbound_relations": final_inbound, "foreign_outbound_relations": final_outbound})
        representative = target["entities"][0]["name"] if target["entities"] else None
        if representative:
            opened = mcp_call(executable, "open_nodes", {"names": [representative]}, bounded_timeout())
            opened_entities, _ = _graph_payload(opened)
            if [e for e in opened_entities if isinstance(e, dict) and e.get("name") == representative] != [target["entities"][0]]:
                raise InputError("verification_failed", "Representative owned entity content could not be retrieved exactly")
        journal["status"] = "verified"; journal["foreign_inbound_relations"] = final_inbound
        atomic_private_json(journal_file, journal); fault_point("verified")
        atomic_private_json(state_file, target); fault_point("snapshot_committed")
        journal["status"] = "complete"; journal.pop("target_snapshot", None); journal.pop("next_tool", None)
        atomic_private_json(journal_file, journal); fault_point("complete")
    except (InputError, OSError) as exc:
        effects = []
        if 'journal' in locals():
            journal["status"] = "backend_unavailable" if isinstance(exc, InputError) and exc.code == "backend_unavailable" else "partial_failure"
            journal["updated_unix"] = int(time.time())
            try: atomic_private_json(journal_file, journal)
            except OSError: pass
            attempt = journal.get("mutation_attempt")
            definitely_no_mutation = (isinstance(exc, InputError)
                and exc.details.get("mutation_definitely_not_performed") is True)
            if isinstance(attempt, dict) and attempt.get("status") == "dispatching" and not definitely_no_mutation:
                effects.append({"type":"mutation_may_have_occurred", "tool":attempt.get("tool"),
                    "transaction_id":transaction_id, "namespace":ownership["namespace"], "reconciliation_required":True})
            elif journal.get("applied_batches", 0):
                effects.append({"type":"mutate_owned_derived_graph", "namespace":ownership["namespace"], "batch_count":journal["applied_batches"]})
        if isinstance(exc, InputError): exc.details["effects"] = effects; raise
        raise InputError("io_error", "Recoverable onboarding state I/O failure", {"type":type(exc).__name__, "effects":effects}) from exc
    finally:
        os.close(lock_fd)
    representative = target["entities"][0]["name"] if target["entities"] else None
    return {"namespace": ownership["namespace"], "workspace_hash": ownership["workspace_hash"],
            "source_count": len(inspected["sources"]), "core_source_count": len(inspected["core_documents"]),
            "core_document_count": len(inspected["core_documents"]), "core_section_count": len(inspected["core_sections"]),
            "memory_claim_count": len(inspected["claims"]), "claim_count": len(inspected["claims"]),
            "entity_count": len(target["entities"]), "relation_count": len(expected_relations),
            "source_digest": target["source_digest"], "snapshot_hash": target["snapshot_hash"],
            "representative_entity": representative, "representative_retrieved": True,
            "verified": True, "applied_batches": applied, "transaction_id": transaction_id,
            "foreign_inbound_relations": final_inbound,
            "removed_foreign_inbound_relations": [r for r in initial_inbound if r not in final_inbound]}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="memory-graph")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("inspect", "plan"):
        c = sub.add_parser(name); c.add_argument("--root", default="."); c.add_argument("--secret-policy", choices=("reject", "redact"), default="reject")
        c.add_argument("--detail", action="store_true"); c.add_argument("--output"); c.add_argument("--output-root")
        if name == "plan":
            c.add_argument("--include-inferred", action="store_true"); c.add_argument("--agent-id", required=True); c.add_argument("--workspace-id")
    c = sub.add_parser("validate-plan"); c.add_argument("--plan", required=True); c.add_argument("--root", default=".")
    c = sub.add_parser("validate-snapshot"); c.add_argument("--snapshot", required=True); c.add_argument("--root", default=".")
    c = sub.add_parser("diff"); c.add_argument("--snapshot", required=True); c.add_argument("--root", default="."); c.add_argument("--secret-policy", choices=("reject", "redact"), default="reject"); c.add_argument("--include-inferred", action="store_true"); c.add_argument("--agent-id", required=True); c.add_argument("--workspace-id")
    c = sub.add_parser("export-mcp-batch"); c.add_argument("--input", required=True); c.add_argument("--root", default="."); c.add_argument("--batch-size", type=int, default=100); c.add_argument("--include-inferred", action="store_true")
    c = sub.add_parser("query-plan"); c.add_argument("--input", required=True); c.add_argument("--root", default="."); c.add_argument("--query")
    c.add_argument("--overlay"); c.add_argument("--include-inferred", action="store_true")
    c.add_argument("--entity-id"); c.add_argument("--entity-type"); c.add_argument("--relation"); c.add_argument("--direction", choices=("out","in","both"), default="both")
    c.add_argument("--statuses", default="current,active"); c.add_argument("--max-depth", type=int, default=1); c.add_argument("--max-entities", type=int, default=100); c.add_argument("--max-edges", type=int, default=200); c.add_argument("--explain", action="store_true")
    for name in ("validate-inference-candidates", "project-inference-overlay"):
        c = sub.add_parser(name); c.add_argument("--input", required=True); c.add_argument("--root", default=".")
        c.add_argument("--agent-id", required=True); c.add_argument("--workspace-id")
        if name == "project-inference-overlay": c.add_argument("--state-root")
    for name in ("ontology-validate", "review-queue", "cq-evaluate", "semantic-view"):
        c = sub.add_parser(name); c.add_argument("--input", required=True); c.add_argument("--root", default=".")
        c.add_argument("--agent-id", required=True); c.add_argument("--workspace-id")
        if name == "semantic-view": c.add_argument("--include-candidates", action="store_true")
    c = sub.add_parser("export-visualization"); c.add_argument("--input", required=True); c.add_argument("--root", default=".")
    c.add_argument("--overlay"); c.add_argument("--include-inferred", action="store_true")
    c = sub.add_parser("semantic-extractor-input"); c.add_argument("--root", default="."); c.add_argument("--agent-id", required=True); c.add_argument("--workspace-id"); c.add_argument("--limit", type=int, default=20); c.add_argument("--cursor")
    for name in ("semantic-validate-proposals", "semantic-review-queue"):
        c = sub.add_parser(name); c.add_argument("--input", required=True); c.add_argument("--root", default="."); c.add_argument("--agent-id", required=True); c.add_argument("--workspace-id")
    c = sub.add_parser("semantic-approve"); c.add_argument("--input", required=True); c.add_argument("--manifest", required=True); c.add_argument("--expected-reviewer-id", required=True); c.add_argument("--root", default=".")
    c = sub.add_parser("semantic-build"); c.add_argument("--input", required=True); c.add_argument("--root", default=".")
    c = sub.add_parser("semantic-migrate-v09"); c.add_argument("--input", required=True); c.add_argument("--root", default=".")
    c = sub.add_parser("semantic-reconcile"); c.add_argument("--input", required=True); c.add_argument("--current", required=True); c.add_argument("--root", default=".")
    c = sub.add_parser("semantic-reconcile-verify"); c.add_argument("--input", required=True); c.add_argument("--plan", required=True); c.add_argument("--current", required=True); c.add_argument("--root", default=".")
    c = sub.add_parser("semantic-export-html"); c.add_argument("--input", required=True); c.add_argument("--output", required=True); c.add_argument("--output-root", required=True); c.add_argument("--root", default="."); c.add_argument("--include-candidates",action="store_true")
    c = sub.add_parser("onboard"); c.add_argument("--root", default="."); c.add_argument("--agent-id", required=True); c.add_argument("--workspace-id"); c.add_argument("--state-root", required=True); c.add_argument("--mcporter", default="mcporter"); c.add_argument("--timeout-seconds", type=int, default=10); c.add_argument("--secret-policy", choices=("reject", "redact"), default="reject")
    c = sub.add_parser("cron-plan"); c.add_argument("--root", default="."); c.add_argument("--agent-id", required=True); c.add_argument("--workspace-id"); c.add_argument("--state-root", required=True); c.add_argument("--timezone", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = Path(args.root).resolve()
        if args.command == "inspect": data = inspect_workspace(root, args.secret_policy)
        elif args.command == "plan": data = build_plan(inspect_workspace(root, args.secret_policy), args.include_inferred, namespace_for(args.agent_id, root, args.workspace_id))
        elif args.command in {"validate-plan", "validate-snapshot"}: data = validate_snapshot(load_json(getattr(args, "plan", None) or args.snapshot, root))
        elif args.command == "diff": data = graph_diff(load_json(args.snapshot, root), build_plan(inspect_workspace(root, args.secret_policy), args.include_inferred, namespace_for(args.agent_id, root, args.workspace_id)))
        elif args.command == "export-mcp-batch": data = export_batches(load_json(args.input, root), args.include_inferred, args.batch_size)
        elif args.command == "onboard":
            if not 1 <= args.timeout_seconds <= 30:
                raise InputError("invalid_timeout", "timeout-seconds must be between 1 and 30")
            data = onboard(root, args.agent_id, args.workspace_id, Path(args.state_root), args.mcporter, args.timeout_seconds, args.secret_policy)
        elif args.command == "cron-plan": data = cron_plan(root, args.agent_id, args.workspace_id, args.state_root, args.timezone)
        elif args.command in {"validate-inference-candidates", "project-inference-overlay"}:
            bundle, _ = load_inference_bundle(args.input, root)
            validated = validate_inference_candidates(root, bundle, args.agent_id, args.workspace_id)
            if args.command == "validate-inference-candidates": data = validated
            else:
                data = project_inference_overlay(validated)
                if args.state_root:
                    data = {**data, "cache": cache_inference_overlay(Path(args.state_root), validated, data)}
        elif args.command in {"ontology-validate", "review-queue", "cq-evaluate", "semantic-view"}:
            bundle, _ = load_inference_bundle(args.input, root)
            api = {"error": InputError, "inspect": inspect_workspace, "namespace": namespace_for, "plan": build_plan,
                "semantic_types": SEMANTIC_TYPES, "hash_re": HASH_RE, "id_re": ID_RE, "secret_like": secret_like}
            validated = ontology.validate_bundle(root, bundle, args.agent_id, args.workspace_id, api)
            if args.command == "ontology-validate": data = validated
            elif args.command == "review-queue": data = ontology.review_queue(validated)
            elif args.command == "cq-evaluate": data = ontology.cq_evaluate(validated)
            else: data = ontology.semantic_view(validated, args.include_candidates)
        elif args.command == "export-visualization":
            snapshot = load_json(args.input, root)
            overlay = load_json(args.overlay, root) if args.overlay else None
            data = export_visualization(snapshot, overlay, args.include_inferred)
        elif args.command == "semantic-extractor-input":
            api={"error":InputError,"inspect":inspect_workspace,"namespace":namespace_for,"plan":build_plan}
            data=semantic_v10.extractor_input(root,args.agent_id,args.workspace_id,api,args.limit,args.cursor)
        elif args.command in {"semantic-validate-proposals","semantic-review-queue"}:
            api={"error":InputError,"inspect":inspect_workspace,"namespace":namespace_for,"plan":build_plan}
            validated=semantic_v10.validate_proposals(root,load_semantic_bundle(args.input,root),args.agent_id,args.workspace_id,api)
            data=validated if args.command=="semantic-validate-proposals" else semantic_v10.review_queue(validated)
        elif args.command == "semantic-approve":
            data=semantic_v10.approve(load_semantic_bundle(args.input,root),load_semantic_bundle(args.manifest,root),{"error":InputError},args.expected_reviewer_id)
        elif args.command == "semantic-build": data=semantic_v10.build_snapshot(load_semantic_bundle(args.input,root),{"error":InputError})
        elif args.command == "semantic-migrate-v09": data=semantic_v10.migrate_v09(load_semantic_bundle(args.input,root),{"error":InputError})
        elif args.command == "semantic-reconcile": data=semantic_v10.reconcile(load_semantic_bundle(args.input,root),load_semantic_bundle(args.current,root),{"error":InputError})
        elif args.command == "semantic-reconcile-verify": data=semantic_v10.verify_reconcile(load_semantic_bundle(args.input,root),load_semantic_bundle(args.plan,root),load_semantic_bundle(args.current,root),{"error":InputError})
        elif args.command == "semantic-export-html":
            output_root=Path(args.output_root).resolve(); target=safe_output_resolve(output_root,args.output)
            if target.is_symlink() or (target.exists() and not target.is_file()): raise InputError("invalid_output_path","Output must be a regular non-symlink file")
            data=semantic_v10.export_html(load_semantic_bundle(args.input,root),target,{"error":InputError},args.include_candidates)
        else:
            snapshot = load_json(args.input, root)
            if args.query:
                validate_snapshot(snapshot); terms = args.query.casefold().split()
                matches = [e for e in snapshot["entities"] if all(term in json.dumps(e, ensure_ascii=False).casefold() for term in terms)]
                data = {"query": args.query, "entities": sorted(matches, key=lambda x: x["name"]), "conflicts": snapshot["conflicts"], "canonical_grounding_required": True}
            else:
                overlay = load_json(args.overlay, root) if args.overlay else None
                data = semantic_query(snapshot, args.entity_id, args.entity_type, args.relation, args.direction,
                    args.statuses, args.max_depth, args.max_entities, args.max_edges, args.explain,
                    overlay, args.include_inferred)
        effects = []
        if args.command == "onboard":
            effects.append({"type": "write_private_state", "namespace": data["namespace"]})
            if data["applied_batches"]:
                effects.append({"type": "mutate_owned_derived_graph", "namespace": data["namespace"], "batch_count": data["applied_batches"]})
        if args.command == "project-inference-overlay" and args.state_root and not data["cache"]["cache_hit"]:
            effects.append({"type": "write_private_cache", "namespace": data["namespace"], "mode": "0600"})
        if args.command == "semantic-export-html":
            effects.append({"type":"write_file","path":target.relative_to(output_root).as_posix(),"sha256":data["sha256"]})
        if args.command in {"inspect", "plan"} and args.output:
            if not args.output_root:
                raise InputError("invalid_output_path", "--output requires --output-root")
            output_root = Path(args.output_root).resolve()
            if not output_root.is_dir():
                raise InputError("invalid_output_path", "Output root must be an existing directory")
            target = safe_resolve(output_root, args.output)
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise InputError("invalid_output_path", "Output must be a regular non-symlink file")
            target.write_bytes(canonical_bytes(data) + b"\n")
            effects.append({"type": "write_file", "path": target.relative_to(output_root).as_posix()})
        if args.command in {"inspect", "plan"} and not args.detail:
            if args.command == "inspect":
                data = {"source_digest": data["source_digest"], "source_count": len(data["sources"]), "core_source_count": len(data["core_documents"]), "core_document_count": len(data["core_documents"]), "core_section_count": len(data["core_sections"]), "memory_claim_count": len(data["claims"]), "claim_count": len(data["claims"]), "detail_available": True}
            else:
                data = {"snapshot_hash": data["snapshot_hash"], "source_digest": data["source_digest"], "core_source_count": len(data["core_documents"]), "core_document_count": len(data["core_documents"]), "core_section_count": len(data["core_sections"]), "memory_claim_count": len(data["claims"]), "claim_count": len(data["claims"]), "entity_count": len(data["entities"]), "explicit_relation_count": len(data["explicit_relations"]), "structural_relation_count": len(data["structural_relations"]), "inferred_relation_count": len(data["inferred_relations"]), "excluded_claim_count": len(data["excluded_claims"]), "ambiguous_claim_key_count": len(data["conflicts"]["ambiguous_claim_keys"]), "artifact_written": bool(args.output), "detail_available": True}
        output = {"ok": True, "schema_version": SCHEMA_VERSION, "command": args.command, "data": data, "effects": effects}
        print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    except (InputError, OSError, UnicodeError) as exc:
        if isinstance(exc, InputError): code, message, details = exc.code, exc.message, exc.details
        else: code, message, details = "io_error", "Unable to read input", {"type": type(exc).__name__}
        effects = details.pop("effects", []) if isinstance(details, dict) else []
        print(json.dumps({"ok": False, "schema_version": SCHEMA_VERSION, "command": getattr(args, "command", None), "error": {"code": code, "message": message, "details": details}, "effects": effects}, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
