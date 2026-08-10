# Memory Graph v0.9 claim-grounded entity proposal contract

Status: implementation contract. Classification: **REFINE** the existing paired `memory-graph` Skill/Harness, never create a new capability. Baseline: v0.8 at `a69c9219a2ce44830d931f2a20ff5e390864dec2`. This contract authorizes local implementation and tests only. It does not authorize publication, installation, Gateway restart, canonical-memory mutation, credential use, live-graph mutation, or access outside the designated worktree and non-live fixtures.

## 1. Purpose and invariant

v0.9 corrects the v0.8 live-corpus bootstrap deadlock by adding a private, noncanonical, claim-grounded **Entity Proposal** layer. An eligible canonical claim may propose a `Person`, `Project`, `Decision`, or `Event`; only an explicitly and validly human-reviewed `approved` proposal may act as an assertion endpoint. Canonical semantic entities remain a separate, higher-trust explicit source. Entity proposals never become canonical facts, never mutate canonical Markdown, and never enter a live graph in this release.

The Harness remains deterministic, no-model, no-network, no-MCP, and read-only with respect to canonical files. Aliases are inert identity candidates and never merge, redirect, delete, or coalesce IDs. Chronology or co-mention never establishes causality; `caused` still requires direct causal evidence and explicit human approval.

## 2. Authority, sources, namespace, and bounds

Allowed canonical inputs are exactly direct regular non-symlink `memory/*.md` files. Root/core/context files and all nested memory paths are excluded. Reject arbitrary Markdown, evidence-file ingestion, symlinks, path escapes, secrets/config files, another workspace, and cross-agent/cross-workspace namespaces. Every operation recomputes the fresh source snapshot and digest and preserves source bytes, digest, mode, and mtime.

All derived objects use the exact owned namespace `memory-graph:v1:<owner-24-hex>:` and are private, disposable, and rebuildable. Inputs are UTF-8 JSON, maximum 1 MiB, with at most 256 entity proposals, 256 assertions, and 256 identity candidates. Views remain bounded to depth <=3, entities <=100, and edges <=200. Closed shapes reject every unknown key, value, type, or cardinality.

## 3. Bundle and entity proposal shape

The additive bundle schema is `memory-graph-assertions/v2`, semantic contract `0.9`. It retains v0.8 top-level fields and assertions and adds `entity_proposals`. Existing v0.8 bundles (`memory-graph-assertions/v1`, semantic contract `0.8`) remain accepted and migrate deterministically with an empty proposal list.

Each proposal has exactly:

```json
{
  "entity_proposal_id": "ep_<64-hex>",
  "namespace": "memory-graph:v1:<24-hex>:",
  "entity": {"entity_id":"project:memory-graph","type":"Project"},
  "source_claim_id": "cl_...",
  "source": {
    "path": "memory/projects.md",
    "line_start": 10,
    "line_end": 14,
    "source_content_hash": "<64-hex>",
    "claim_content_hash": "<64-hex>"
  },
  "extractor": {
    "extractor_id": "claim-entity-extractor",
    "extractor_version": "1.0.0",
    "config_hash": "<64-hex>"
  },
  "status": "approved",
  "review": {
    "reviewer_id": "human:reviewer",
    "reviewed_at": "2026-08-10T00:00:00Z",
    "review_reason": "claim_explicitly_identifies_entity"
  },
  "temporal": null
}
```

`entity.type` is exactly `Person`, `Project`, `Decision`, or `Event`. `entity_id` is a stable explicit typed identifier, not a name-derived alias. `temporal` must be null for Person/Project. For Decision/Event it is exactly one of an instant, interval, or unknown representation and preserves `precision` (`instant|day|month|year|unknown`) plus an explicit IANA timezone when time is known. Ambiguous partial dates retain their precision and never receive invented precision.

The source locator is exact: claim ID, safe relative path, 1-based inclusive line range, whole-source content hash, and claim content hash. The extractor identity/config are mandatory. Free-form copied evidence, names as aliases, email addresses, credentials, and arbitrary prose are forbidden.

## 4. Content-addressed stable identity and idempotency

Canonical JSON is UTF-8 with sorted keys, compact separators, and no non-finite numbers.

`entity_proposal_id = "ep_" + sha256(namespace || entity.type || entity.entity_id || source_claim_id || source.path || line_start || line_end || source_content_hash || claim_content_hash || extractor_id || extractor_version || config_hash || canonical-temporal-or-null)`.

Lifecycle and review fields do not affect identity. Reordered or repeated identical inputs normalize byte-identically and deduplicate idempotently. The same ID with different identity material is a bundle-level conflict. Multiple proposals for one typed entity remain separate provenance resources; conflicting type/identity proposals are quarantined and never silently resolved.

## 5. Lifecycle, approval, and endpoint eligibility

Proposal statuses are exactly `candidate`, `approved`, `rejected`, `superseded`, and `quarantined`.

- `candidate` requires `review:null` and is inert.
- `approved` requires a complete human review with reviewer ID, timezone-aware review timestamp, and allowed review reason.
- `rejected`, `superseded`, and `quarantined` are inert.
- Candidate approval is represented in supplied reviewed data; the read-only Harness does not mutate approval state.
- An approved proposal with stale/invalid provenance or review is quarantined and cannot bootstrap an endpoint.
- Inert states never return to approved under the same proposal identity.

An assertion endpoint is eligible when it matches either (a) a validated explicit canonical semantic entity, marked `entity_source=canonical_explicit`, or (b) a fresh, valid, approved private proposal, marked `entity_source=approved_private_proposal`. Canonical explicit entities take precedence without deleting or merging private proposals. Assertion output must preserve endpoint source class and proposal IDs used. Candidate aliases and identity candidates never qualify as endpoints.

## 6. Assertions, causality, identity, and temporal rules

v0.8 assertion shapes and predicates remain unchanged:

- `Person --participates_in--> Project|Event`
- `Person --decided--> Decision`
- `Decision|Event --caused--> Event`
- `Decision|Event|Project --supersedes--> same type`

Assertions may now resolve endpoints from approved private proposals. They retain exact source claim ID/path/line/source hash/claim hash/evidence hash, assertion content-addressing, lifecycle, extractor/review provenance, and closed shapes. Unsupported or dangling approved edges remain inert and count toward the unsupported-approved-edge gate.

`caused` requires `method=human_approved`, an approved human review, `review_reason=direct_causal_statement`, and direct causal wording in the exact source claim. Mere chronology, order, co-occurrence, or shared participants is insufficient and must quarantine deterministically.

Aliases, similar labels, names, blocking features, and identity scores are emitted only to the inert identity review queue. The Harness never auto-merges, emits `same_as`, redirects, rewrites assertions, or selects a winning identity.

## 7. Validation and deterministic quarantine

Bundle-level failures emit no normalized objects: malformed/oversized JSON, unknown schema/top-level key, wrong namespace/snapshot/digest, path escape, symlink source, secret-like metadata, cross-workspace source, duplicate ID with different material, or invalid top-level bounds.

Proposal-level failures quarantine only the affected proposal with stable reason codes, including `entity_proposal_id_mismatch`, `invalid_entity_type`, `invalid_entity_id`, `stale_provenance`, `source_hash_mismatch`, `claim_hash_mismatch`, `ineligible_claim`, `invalid_extractor`, `invalid_lifecycle`, `missing_review`, `invalid_review`, `invalid_temporal_shape`, `path_escape`, `symlink_source`, `cross_namespace_entity`, `secret_like_entity_proposal`, `duplicate_entity_proposal`, and `conflicting_entity_proposal`. Ordering is `(reason_code, source_claim_id, entity_proposal_id)`. Diagnostics never echo secret-like input or rejected prose.

Assertion quarantine adds deterministic distinction between `dangling_endpoint`, `unapproved_entity_proposal`, `stale_entity_proposal`, `conflicting_entity_identity`, and existing v0.8 codes. Same bytes plus same canonical sources produce byte-identical normalized output, quarantine, and hashes.

## 8. Commands and outputs

Existing read-only commands remain and accept v2 additively:

1. `ontology-validate`: validates/migrates proposals, assertions, and identity candidates against fresh canonical sources; returns normalized approved endpoint catalog, accepted assertions, deterministic quarantine, migration metadata, shape/report hashes, and source-class labels.
2. `review-queue`: returns sorted inert entity candidates, assertion candidates, identity candidates, and quarantine; performs no approval mutation.
3. `cq-evaluate`: evaluates CQ1-CQ5 using canonical explicit plus approved private endpoints and emits release-gate metrics.
4. `semantic-view`: semantic-first path/ego/timeline output; approved assertions are solid `Approved explicit`, approved private endpoint nodes are visibly labeled `Approved private entity proposal`, candidates remain dashed/inert, and structural edges stay hidden by default.

`query-plan` remains compatible and excludes candidates/inferred data by default. Material semantic hops carry assertion ID, endpoint source class, proposal locator(s), canonical hydration locator, and `rehydration_required=true`.

## 9. Migration and compatibility

A v0.8 v1 bundle migrates in memory to v0.9 with `entity_proposals:[]`, unchanged assertion IDs, unchanged acceptance/quarantine semantics, and explicit migration metadata. No source or input file is rewritten. v0.7 explicit canonical entities remain higher trust and v0.7 inference overlays remain disjoint, opt-in, and noncanonical. Existing consumers that ignore additive fields continue to work.

Rollback is code/config rollback plus deletion of private derived v0.9 test/cache state only. Canonical Markdown, live MCP, foreign namespace data, and broader state roots are never changed or deleted.

## 10. Competency questions and release gates

CQ1-CQ5 retain the v0.8 meanings and must work when endpoints originate from approved private proposals:

1. Decision -> deciding Person and explicitly connected Project paths.
2. Event -> only human-approved direct causal paths; chronology-only returns no answer.
3. Explicit supersedes chain without cycles.
4. Person -> explicitly connected Project/Event with temporal precision preserved.
5. Every semantic hop has complete canonical claim hydration locators and proposal provenance where applicable.

The realistic non-live fixture contains 10-30 canonical-format claims, approved entity proposals for all required endpoint types, at least 12 approved assertions across at least three predicates, and CQ1-CQ5 all passing. Release gates are exactly: approved semantic assertions >=12, CQ pass count 5/5, unsupported approved edge count 0, and canonical hydration locator coverage 100%.

## 11. Required tests

Test valid private endpoint bootstrap and canonical-explicit precedence; malformed and oversized input; unknown keys; stale snapshot/source/claim provenance; secret-like input without echo; symlink and path escape; namespace crossing; identity ambiguity and alias inertness; duplicate/reordered idempotency; conflicting proposals; every lifecycle state; invalid/missing review; Decision/Event temporal precision and timezone; chronology-only and non-human causality rejection; unsupported/dangling endpoint quarantine; approved assertion resolution; source-class labels; deterministic quarantine/report hashes; v0.8 compatibility/migration; source bytes/digest/mode/mtime immutability; no model/network/MCP/live graph calls; bounded counts/views; >=12 assertions and CQ 5/5; and full existing Memory Graph plus repository validator suites.

## 12. Completion evidence and non-goals

Implementation must update the paired Skill, Harness implementation/manifests, registry metadata, docs, realistic fixtures, tests, and release evidence. Run registry sync and compile/diff checks. Commit the contract separately before implementation and report exact commits, commands, test counts, defects, and limits.

Non-goals: publication, installation, Gateway restart, cron mutation, canonical-memory mutation, live graph/MCP projection, model or network access, automatic extraction execution, automatic approval, alias merge, `same_as`, redirects, new domain classes/predicates, ontology reasoning, causality inference, cross-agent/global graph, or production change.
