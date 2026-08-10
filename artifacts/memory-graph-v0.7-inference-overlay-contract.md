# Memory Graph v0.7 read-only inference overlay contract

Status: design only. Classification: **REFINE** the existing paired `memory-graph` v0.6 Skill/Harness; do not create a second capability. This change does not authorize publication, installation, restart, canonical writes, or live graph mutation.

## 1. Authority and immutability boundary

Canonical inputs remain the only authority and are strictly read-only: the six v0.6 core/context files (`SOUL.md`, `IDENTITY.md`, `USER.md`, `AGENTS.md`, `ORGANIZATIONS.md`, `WORKFLOW.md`), root `MEMORY.md`/`memory.md`, direct `memory/*.md`, and claim evidence. The Harness opens them only for bounded reads and hashing; it never edits, annotates, normalizes, relocates, or writes beside them. Evidence text is not an inference input. Core/context prose remains structural context and is never promoted to inferred semantic facts.

All inference is noncanonical, private, disposable derived state under the existing exact agent/workspace namespace. It is excluded from claim/evidence records and can be deleted and rebuilt without information loss. Canonical `semantic` metadata remains the sole source of `explicit_relations`. Candidate output from prose can produce only `inferred_relations`; it never changes explicit entities, explicit relations, structural relations, claims, evidence, or canonical files.

## 2. Responsibility split

1. The **agent** reads an eligible canonical claim and the bounded list of already validated explicit semantic entities. It may use model judgment to propose candidate relations from claim prose and emits candidate JSON only.
2. The **Harness** performs no model/API/network call. It deterministically parses, validates, freshness-checks, quarantines, projects, caches, queries, and renders candidates. It never repairs or expands a candidate and never resolves names or aliases.
3. A candidate may reference only exact existing `(type, entity_id)` values from the same freshly built explicit projection. The agent cannot propose new semantic entities, alias merges, transitive/inverse relations, or endpoints inferred from display names.
4. The v0.6 ontology and endpoint rules remain unchanged. `caused` requires direct causal wording in the cited claim span; chronology alone is invalid. Confidence never converts an inference into an explicit fact.

## 3. Candidate bundle schema

The Harness accepts one canonical JSON object with no unknown keys:

```json
{
  "schema_version": "memory-graph-inference-candidates/v1",
  "semantic_contract_version": "0.7",
  "namespace": "memory-graph:v1:<24-hex>:",
  "source_snapshot_hash": "<64-hex>",
  "source_digest": "<64-hex>",
  "extractor": {
    "name": "agent-semantic-inference",
    "version": "<immutable prompt/model/config version>",
    "config_hash": "<64-hex>"
  },
  "candidates": [{
    "candidate_id": "ic_<64-hex>",
    "source_claim_id": "<canonical claim id>",
    "source": {
      "path": "memory/<direct-topic>.md",
      "line_start": 12,
      "line_end": 17,
      "source_content_hash": "<64-hex>",
      "claim_content_hash": "<64-hex>"
    },
    "from": {"entity_id": "<explicit id>", "type": "Person"},
    "relation_type": "participates_in",
    "to": {"entity_id": "<explicit id>", "type": "Project"},
    "confidence": 0.84,
    "basis": "direct_statement"
  }]
}
```

Allowed `relation_type` values and endpoint types are exactly v0.6: `participates_in`, `decided`, `caused`, and `supersedes`. `basis` is one of `direct_statement` or `direct_causal_statement`; it is classification, not copied prose. Confidence is a finite JSON number in `[0,1]`, preserved for display/ranking and never used as an autonomous truth threshold. Candidate source must be one eligible `current`, `tentative`, or legacy `active` memory claim. Paths must be normalized root-relative direct canonical memory paths; symlinks, escapes, core/context paths, evidence paths, arbitrary Markdown, and secret/config paths fail closed.

Stable IDs use canonical JSON (UTF-8, sorted keys, no insignificant whitespace):

- `candidate_id = "ic_" + sha256(namespace || source_claim_id || claim_content_hash || from.type || from.entity_id || relation_type || to.type || to.entity_id || extractor.name || extractor.version || extractor.config_hash)`.
- After validation, `inferred_edge_id = "ie_" + sha256(namespace || candidate_id)`.
- `quarantine_id = "iq_" + sha256(namespace || candidate_id-or-safe-input-hash || reason_code)`.

The Harness recomputes all IDs and rejects mismatches. Reordered candidate arrays produce identical output ordering and hashes. Duplicate identical candidates collapse; contradictory candidates remain separate quarantined records rather than winner selection.

## 4. Freshness, provenance, cache, and reproducibility

Before projection, the Harness rebuilds the current read-only v0.6 snapshot and requires exact equality of namespace, `source_snapshot_hash`, and `source_digest`. It re-reads the cited regular file, verifies `source_content_hash`, verifies the claim marker and 1-based inclusive line range, recomputes `claim_content_hash`, checks claim eligibility, and verifies both endpoints in the current explicit projection. Evidence hashes remain canonical provenance carried by the claim, but evidence files are never sent to the extractor or copied into candidate/cache output.

Every inferred relation records candidate ID, inferred edge ID, source claim ID, safe path/line locator, source and claim hashes, confidence, basis, extractor name/version/config hash, semantic contract version, namespace, and source snapshot hash. Query results remain locators requiring `memory_search`/`memory_get` rehydration.

Cache key: `sha256(namespace || source_snapshot_hash || extractor.name || extractor.version || extractor.config_hash || candidate_bundle_hash || semantic_contract_version)`. Cache values contain only validated projection and safe quarantine metadata, use mode `0600`, live outside canonical memory, and are scoped to the exact namespace. Any source digest/snapshot, claim/file hash, endpoint projection, contract, extractor, config, or candidate-bundle change is a cache miss; stale entries are inert and removable. Same canonical bytes plus same candidate bundle and versions must yield byte-identical projection, quarantine order, and overlay hash. Time, file mtime, host path, process ID, model latency, and network state are not hashed inputs.

## 5. Secret safety and namespace isolation

Apply the existing secret scanner before diagnostics, persistence, hashing fields exposed in output, or projection. Default `reject` quarantines with only reason, IDs, hashes, and locator; it never echoes rejected text. Optional deterministic redaction may replace a detected value with `[REDACTED]` only in derived display data, never alter canonical bytes, and cannot make an otherwise unsafe endpoint resolvable. Free-form rationales, excerpts, prompts, model responses, credentials, evidence text, emails used as identity, and arbitrary attributes are forbidden in candidate/cache/quarantine output.

The supplied namespace must equal the namespace derived by the Harness from the explicit agent ID and workspace identity. Endpoints must already exist under that namespace. Cross-namespace endpoints, candidate reuse, cache reuse, reads, writes, or graph edges fail closed. Even a future apply path may mutate only exact owned `inferred:*` overlay objects; this design phase provides validation/projection only and performs no backend mutation.

## 6. Projection, query, and visualization

The snapshot keeps three disjoint arrays:

- `explicit_relations`: canonical semantic metadata only, provenance-backed.
- `structural_relations`: deterministic document/claim structure only.
- `inferred_relations`: accepted candidate overlays only, always marked `inferred:true`, `canonical:false`, `locator_only:true`.

No relation may appear in both explicit and inferred arrays. If an identical explicit tuple exists, suppress the inferred tuple as `shadowed_by_explicit` while retaining a safe audit/quarantine record. Default query and MCP export exclude inferred relations. Callers must opt in with `include_inferred:true`; responses return separate arrays, never a merged unlabeled edge list. Ranking may use confidence only within inferred results. Traversal retains v0.6 depth/entity/edge bounds and never allows inferred hops to make an explicit answer.

Visualization uses solid lines and an `Explicit` legend for explicit relations, dashed lines plus confidence and an `Inferred, noncanonical` legend for inferred relations. Color alone is insufficient. Mixed paths label every hop and the path as inferred if any hop is inferred. Quarantine is a separate diagnostic panel and never a graph edge.

## 7. Quarantine and failure semantics

Bundle-level failures produce no projection or cache update: malformed/oversized JSON, unknown schema/keys, namespace mismatch, stale snapshot/source digest, path escape/symlink, secret-like bundle metadata, invalid extractor identity, or duplicate candidate IDs with differing content.

Candidate-level failures are inert and allow unrelated valid candidates to proceed. Stable reason codes include `stale_source`, `claim_hash_mismatch`, `line_mismatch`, `ineligible_claim`, `unknown_relation`, `invalid_endpoint_type`, `unresolved_explicit_endpoint`, `cross_namespace_endpoint`, `id_mismatch`, `invalid_confidence`, `causality_not_direct`, `self_relation`, `supersession_cycle`, `contradictory_candidates`, `shadowed_by_explicit`, and `secret_like_candidate`. A quarantined candidate emits no edge. Diagnostics contain no candidate prose or secret value. Ordering is `(reason_code, source_claim_id, candidate_id)`.

Validator/backend I/O errors are fail-closed, retryable only after verifying no canonical or live graph mutation occurred. Because v0.7 validation/projection is read-only, partial output is discarded atomically. Existing last-known cache may be reported as stale but is never silently served as fresh.

## 8. Implementation contract and acceptance gates

Implement in the existing paired capability with read-only direct-CLI surfaces first:

1. `validate-inference-candidates --input ...` returns normalized accepted candidates, safe quarantine, freshness facts, and deterministic hashes.
2. `project-inference-overlay --input ...` returns the disjoint `inferred_relations` overlay and overlay hash, with no MCP/backend calls.
3. Extend `query-plan` and visualization export with explicit `include_inferred`, separated arrays, labels, and hydration locators.
4. Add private cache only after deterministic projection tests pass. Do not add any model provider, API key, HTTP client, canonical writer, or live mutation path to the Harness.

Required tests: canonical/core/evidence digest and mtime unchanged; model/network calls impossible; valid deterministic projection; stale file/claim/snapshot rejection; exact namespace isolation; explicit/inferred separation and shadowing; confidence preserved but not truth-gating; extractor/config invalidation; byte-identical rebuild; secret non-disclosure; symlink/path escape; malformed/oversized bundle; wrong IDs/endpoints/types; causality and supersession failures; quarantine isolation/order; query default exclusion and visual non-color labels; all v0.6 regressions. Run repository validation and representative Gateway prepare for each new input-schema shape before any release proposal.

Next implementation is complete only when these read-only surfaces and tests pass. Publication, installation, cron changes, backend overlay reconciliation, and live graph mutation require separate design and explicit approval.
