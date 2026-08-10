# Memory Graph v0.8 assertion ontology contract

Status: implementation contract. Classification: **REFINE** the existing paired `memory-graph` Skill/Harness. Baseline: v0.7.0 at `d7f215334864049c7fcbfd1f293171af32f0f4cc`. This contract authorizes local implementation and tests only. It does not authorize publication, installation, Gateway restart, canonical-memory mutation, credential use, or live-graph mutation.

## 1. Purpose and release gates

v0.8 adds a small, deterministic assertion ontology that makes semantic relations reviewable, provenance-bearing, temporally precise, and competency-question testable. It does not expand the four v0.7 domain entity types or four predicates.

The vertical slice is acceptable only when non-live fixtures contain at least 12 approved assertions spanning at least three predicates and all gates pass:

- **A, data:** at least 12 approved assertions and at least three represented predicates.
- **B, safety:** every shape/adversarial test passes, unsupported approved edges are zero, and every answer locator is rehydratable.
- **C, usefulness:** CQ1-CQ5 produce deterministic, bounded, semantic-first answers over the fixture.
- **D, extraction:** candidates remain review-only; causality and identity ambiguity never promote automatically.
- **E, expansion:** no new class, predicate, inference rule, or merge behavior is added without a new CQ and later approval.

## 2. Authority, namespace, and responsibility

Canonical Markdown remains read-only source of truth. Allowed files remain the portable core allowlist plus root `MEMORY.md`/`memory.md` and direct `memory/*.md`. The Harness may perform bounded reads and hashing only. It must reject symlinks, path escapes, arbitrary Markdown, evidence-file ingestion, secrets/config, and another workspace.

Derived ontology state is private, noncanonical, disposable, and scoped to the existing exact `memory-graph:v1:<owner-24-hex>:` namespace. v0.8 objects cannot cross agent/workspace namespaces. Canonical source bytes, digest, mode, and mtime must remain unchanged by every new command.

The agent may create candidate input from one eligible claim and known explicit endpoints. The Harness is the deterministic authority for parsing, shapes, hashes, status transitions, freshness, query plans, visualization data, and CQ evaluation. The Harness makes no model, HTTP, MCP, graph-backend, or other network call in v0.8 read-only paths.

## 3. Four-layer architecture

1. **Locator:** existing source, document, section, claim resources and structural relations. These are locators, not semantic facts.
2. **Domain:** exactly `Person`, `Project`, `Decision`, and `Event`; exactly `participates_in`, `decided`, `caused`, and `supersedes`.
3. **Assertion:** a first-class resource wrapping each semantic tuple with provenance, lifecycle, method, review, and temporal validity.
4. **Constraint/evaluation:** versioned closed shapes, deterministic validation reports, CQ fixtures/gates, and mandatory canonical locators.

Explicit assertions and v0.7 inference overlays remain disjoint. No OWL reasoning, transitive closure, inverse/symmetric expansion, confidence promotion, or implicit semantic edge is permitted.

## 4. Versioned assertion bundle

Input is strict JSON with no unknown keys:

```json
{
  "schema_version": "memory-graph-assertions/v1",
  "semantic_contract_version": "0.8",
  "namespace": "memory-graph:v1:<24-hex>:",
  "source_snapshot_hash": "<64-hex>",
  "source_digest": "<64-hex>",
  "assertions": [{
    "assertion_id": "as_<64-hex>",
    "subject": {"entity_id": "person:ada", "type": "Person"},
    "predicate": "decided",
    "object": {"entity_id": "decision:ship", "type": "Decision"},
    "source_claim_id": "claim-1",
    "source": {
      "path": "memory/project.md",
      "line_start": 10,
      "line_end": 14,
      "source_content_hash": "<64-hex>",
      "claim_content_hash": "<64-hex>",
      "evidence_excerpt_hash": "<64-hex>"
    },
    "method": "explicit",
    "asserted_at": "2026-08-10T00:00:00Z",
    "valid_time": null,
    "status": "approved",
    "review": null,
    "extractor": null,
    "confidence": null
  }]
}
```

Allowed top-level and nested keys are exact. Limits: 1 MiB input, 256 assertions, UTF-8 JSON, arrays only where specified, integers for 1-based inclusive lines, and ISO-8601 timestamps with explicit timezone.

### 4.1 Content-addressed identity

Canonical JSON means UTF-8, sorted object keys, compact separators, and no non-finite numbers. The Harness recomputes:

`assertion_id = "as_" + sha256(namespace || subject.type || subject.entity_id || predicate || object.type || object.entity_id || source_claim_id || source.path || line_start || line_end || source_content_hash || claim_content_hash || evidence_excerpt_hash || method || extractor-identity-or-empty)`.

Lifecycle/review fields, confidence, and asserted/valid times do not change assertion identity. Identical semantic provenance is one assertion resource; repeated ingestion is idempotent. Same ID with different identity material fails the whole bundle. Conflicting assertions are preserved separately and never silently merged.

### 4.2 Endpoint shapes

- `Person --participates_in--> Project|Event`
- `Person --decided--> Decision`
- `Decision|Event --caused--> Event`
- `Decision|Event|Project --supersedes--> same type`

Endpoints must be exact, already validated explicit IDs in the current projection, in the same namespace. Self-relations are rejected. `supersedes` cycles are rejected. A `caused` assertion requires `method=human_approved`, an approved review, and `review_reason=direct_causal_statement`; chronology is never causal evidence.

### 4.3 Provenance and methods

`method` is exactly `explicit`, `extracted_candidate`, or `human_approved`.

- `explicit` originates in eligible canonical `semantic` metadata and may be `approved` without a separate reviewer.
- `extracted_candidate` requires `extractor` (`extractor_id`, `extractor_version`, `config_hash`) and finite `confidence` in `[0,1]`; it may only be `candidate`, `rejected`, or `quarantined`.
- `human_approved` requires `review` (`reviewer_id`, `reviewed_at`, `review_reason`) and may be `approved`, `rejected`, `superseded`, or `quarantined`.

Confidence is allowed only for extracted candidates, is used only to rank candidates, and is never a truth or approval threshold. Free-form evidence excerpts and rationales are forbidden; provenance carries hashes and bounded locators only.

### 4.4 Lifecycle

Statuses are exactly `candidate`, `approved`, `rejected`, `superseded`, and `quarantined`.

Allowed transitions are:

- `candidate -> approved` only through a supplied human review operation represented as `method=human_approved`;
- `candidate -> rejected|quarantined`;
- `approved -> superseded|quarantined`;
- `rejected -> candidate` only as a new assertion identity after source/extractor identity changes;
- `superseded` and `quarantined` are inert and cannot return to approved under the same assertion ID.

Only `approved` assertions project to `explicit_relations`. Stale source/snapshot/claim/evidence hashes make every affected assertion inert and report `stale_provenance`; no last-known approved assertion is served as fresh. Rejected, superseded, quarantined, and candidate assertions remain audit/review records and emit no semantic edge.

### 4.5 Temporal shape

`asserted_at` is required and separate from domain time and validity. `valid_time` is null or:

```json
{"start": "2026-08-01T00:00:00+09:00", "end": null, "precision": "day", "timezone": "Asia/Seoul"}
```

Precision is exactly `instant`, `day`, `month`, `year`, or `unknown`. A Decision/Event endpoint in canonical domain data must have exactly one of `occurred_at`, interval `[start_at,end_at]`, or `time_unknown=true`; the existing v0.7 semantic validator remains authoritative. Partial dates retain precision and timezone provenance. Ordering supports filtering only and never creates `caused`.

## 5. Identity candidates

Identity review input uses schema `memory-graph-identity-candidates/v1`, exact namespace/snapshot/digest, and known endpoint IDs. A candidate contains `candidate_id`, left/right exact typed IDs, non-secret blocking feature codes, score in `[0,1]`, method/version/config hashes, and source claim locators. It cannot contain names, emails, copied prose, or credentials.

The output is always a separate `identity_candidates` review queue. The Harness never merges entities, emits `same_as`, deletes an ID, creates a redirect, or projects a semantic relation. Ambiguous same-name/alias-like cases remain separate. Cross-workspace/cross-agent candidates fail closed. Merge/redirect execution is explicitly out of scope for v0.8.

## 6. Closed shape validation

`ontology-validate` applies `memory-graph-ontology-shapes/v1`. Every object is checked against an exact key set, type, cardinality, lexical form, endpoint combination, namespace, source eligibility, freshness, lifecycle, temporal shape, and secret policy. Unknown classes, predicates, keys, methods, statuses, precision values, or transition forms fail closed.

Bundle-level errors produce no normalized assertions: malformed/oversized JSON, unknown schema/keys, namespace/snapshot/digest mismatch, duplicate ID with different content, path escape/symlink, secret-like metadata, or invalid top-level shape.

Assertion-level errors quarantine only that assertion while valid siblings may proceed. Stable codes include `unknown_predicate`, `invalid_endpoint_type`, `dangling_endpoint`, `cross_namespace_endpoint`, `self_relation`, `supersession_cycle`, `invalid_lifecycle`, `missing_review`, `invalid_confidence`, `invalid_temporal_shape`, `causality_requires_human_approval`, `causality_not_direct`, `stale_provenance`, `source_hash_mismatch`, `claim_hash_mismatch`, `evidence_hash_mismatch`, `ineligible_claim`, `path_escape`, `symlink_source`, `id_mismatch`, `conflicting_assertions`, and `secret_like_assertion`.

Validation reports are deterministic and safe:

```json
{
  "conforms": false,
  "shape_version": "memory-graph-ontology-shapes/v1",
  "accepted_assertions": [],
  "quarantine": [{"assertion_id":"as_...","reason_code":"stale_provenance","locator":{"path":"memory/x.md","line_start":1,"line_end":2}}],
  "report_hash": "<64-hex>"
}
```

No rejected prose or secret value appears in diagnostics. Ordering is `(reason_code, source_claim_id, assertion_id)`. Same bytes and canonical sources produce byte-identical normalized output and hashes.

## 7. Commands and safety classes

All new commands are local, bounded, and `readOnly` in the Harness manifest:

1. `ontology-validate --input PATH --agent-id ID [--root ROOT] [--workspace-id ID]` validates assertion/identity bundles against a fresh v0.7-compatible explicit projection and emits shapes/report hashes.
2. `review-queue --input PATH --agent-id ID ...` returns inert candidate and quarantine records, sorted deterministically; it performs no approval mutation.
3. `cq-evaluate --input PATH --questions PATH --agent-id ID ...` validates fixtures, runs CQ1-CQ5, and emits per-CQ pass/fail, exact paths, locator completeness, counts, and release gates.
4. `semantic-view --input PATH --agent-id ID ... [--include-candidates] [--include-inferred]` emits semantic-first nodes/edges, timeline/path/ego views, legends, and hydration locators.

Existing commands and schemas remain compatible. `query-plan` retains default exclusion of inferred/candidate content and gains assertion envelopes and `why_this_edge` for approved semantics. New command schemas use only the Gateway-supported JSON Schema subset already used by v0.7.

## 8. CQ contracts

- **CQ1:** given Decision ID, return approved `decided` assertion(s), deciding Person, related Project paths if explicitly connected, and canonical locators.
- **CQ2:** given Event ID, return only human-approved direct `caused` paths and locators; chronology-only data returns no answer.
- **CQ3:** given entity/claim target, return explicit `supersedes` chain, ordered without cycles, with assertion lifecycle/provenance.
- **CQ4:** given Person ID plus optional time/status filters, return explicitly connected Project/Event results preserving time precision.
- **CQ5:** for every returned semantic hop, require source path, lines, source/claim/evidence hashes, assertion ID/status/method, and `rehydration_required=true`.

Bounds remain depth <=3, entities <=100, edges <=200. Evaluation fixtures are non-live repository test data and must never be copied into canonical memory or projected to MCP.

Release metrics emitted by `cq-evaluate`: approved count, represented predicates, unsupported-approved-edge count, locator-completeness ratio, CQ pass count, no-answer correctness, and gate A/B status. Deterministic fixtures must reach approved >=12, predicates >=3, unsupported=0, locator completeness=1.0, and CQ1-CQ5 pass.

## 9. Semantic-first query and visualization

Default output hides structural relations and includes only approved semantic assertion edges. Structural context may be requested separately and remains labeled `Structural locator`. Candidates and v0.7 inferred overlays require separate opt-ins and remain separate arrays.

Every approved edge contains `assertion_id`, tuple, method, status, temporal fields, `why_this_edge`, and canonical locator. Visual edges use solid `Approved explicit`; candidates use dashed `Candidate, noncanonical`; inferred overlays use dashed `Inferred, noncanonical`. Labels, not color alone, distinguish classes. Edge thickness may reflect evidence count only, never confidence. Views are bounded `path`, `ego`, or `timeline`; no whole-graph hairball or community summary is emitted.

## 10. Compatibility, migration, and rollback

v0.7 canonical semantic records continue to parse unchanged. During fresh plan construction, each eligible v0.7 explicit relation is deterministically wrapped as `method=explicit,status=approved` using its existing source/evidence provenance. Existing `explicit_relations`, `structural_relations`, and `inferred_relations` arrays remain present and disjoint. New assertion resources are additive; existing query consumers that ignore unknown response fields continue to work.

Inference overlays remain schema `memory-graph-inference-candidates/v1`, noncanonical, opt-in, and separate. They cannot be promoted by v0.8 validation. Snapshot schema advances additively and must validate legacy v0.7 fixtures.

Rollback is code/config rollback plus deletion of private derived v0.8 test/cache state only. Because canonical Markdown and live MCP are not mutated by this vertical slice, rollback requires no canonical migration. A v0.7 binary must still read canonical sources and rebuild its previous snapshot. Never delete a broader state root or foreign namespace.

## 11. Required tests

- valid fixture with >=12 approved assertions and CQ1-CQ5 success;
- malformed/oversized/unknown-key input and wrong IDs/types/predicates;
- stale snapshot/source/claim/evidence provenance becomes inert;
- chronology does not imply causality and non-human `caused` is quarantined;
- ambiguous identity stays candidate-only with no merge/redirect/semantic edge;
- all allowed and forbidden lifecycle transitions;
- repeated/reordered input is byte-deterministic and idempotent;
- canonical digest, bytes, mode, and mtime unchanged;
- symlink/path escape and namespace crossing fail closed;
- secret-like content is rejected without echo;
- explicit/assertion/inferred separation and query default exclusion;
- temporal precision/timezone preservation;
- semantic-first visual labels and canonical hydration locators;
- no model/network/backend call in new paths;
- all v0.7 tests and repository validation remain green.

## 12. Non-goals

No new domain types or predicates; no OWL reasoner; no automatic entity merge; no executable redirect; no causality from chronology/co-mention; no community detection, embeddings, link prediction, autonomous KG completion, large taxonomy import, cross-agent/global graph, canonical-memory write, live MCP projection, model/network call, publication, installation, cron mutation, Gateway restart, or production change.

## 13. Completion evidence

Implementation-card completion requires a local commit containing paired Skill/Harness, manifests, registry metadata, docs, fixtures, and tests. Report exact test commands and commit. Validation/install/release evidence remains for downstream cards and separate approval.