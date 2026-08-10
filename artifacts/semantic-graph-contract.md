# Memory Graph grounded semantic contract

Status: design only for the existing paired Memory Graph v0.5.0 capability. This contract refines, rather than replaces, the v0.5 claim/provenance graph. Canonical Markdown remains read-only and authoritative; the private namespaced graph remains noncanonical, disposable, and rebuildable.

## 1. Boundary and compatibility

- Preserve v0.5 source allowlist, namespace ownership, claim parsing, `MemoryClaim`/`ClaimKey` entities, structural relations, snapshot hashing, ordered reconciliation, journaling, byte caps, and canonical rehydration requirement.
- Add a separately versioned semantic projection inside the same owned namespace. Semantic objects never replace claims and never become answer evidence without `memory_search` plus `memory_get` rehydration.
- Autonomous projection accepts only explicit structured metadata. Prose extraction may produce proposals, but proposals are quarantined until deterministic validation or human-authored canonical metadata resolves them. No model confidence threshold alone authorizes insertion.
- Policy, persona, role, instruction, workflow, and preference prose is not projected as ordinary semantic facts unless a canonical claim explicitly supplies the semantic metadata and passes all rules below.

## 2. Bounded ontology

Exactly four semantic entity types are allowed:

| Type | Meaning | Required semantic metadata |
| --- | --- | --- |
| `Person` | A specific human | `entity_id`, `canonical_name` |
| `Project` | A bounded initiative, product, capability, or recurring program | `entity_id`, `canonical_name` |
| `Decision` | A choice or adopted direction, not a general fact | `entity_id`, `canonical_name`, `effective_at` or explicit `time_unknown:true` |
| `Event` | A bounded occurrence or state transition | `entity_id`, `canonical_name`, `occurred_at`/`interval` or explicit `time_unknown:true` |

Optional fields are `aliases`, `external_ids`, `valid_from`, `valid_to`, and type-specific display attributes. Unknown types, type coercion, and free-form attributes fail closed into quarantine. A claim may ground zero or more semantic entities, but every semantic entity must be grounded by at least one eligible canonical claim.

Entity graph names are `<namespace>semantic:<Type>:<entity_id>`. `entity_id` is an opaque stable ID matching `[a-z0-9][a-z0-9._:-]{0,127}`; it is not derived from display text. Observations contain canonical JSON only, never copied unbounded prose.

## 3. Relations

Exactly four content relation types are allowed:

| Relation | Domain -> range | Meaning and constraints |
| --- | --- | --- |
| `participates_in` | `Person -> Project|Event` | Explicit participation. Role may be an observation on the grounded edge record, never encoded in relation type. |
| `decided` | `Person -> Decision` | Explicit decision-maker, not attendee, reporter, or approver inferred from prose. |
| `caused` | `Decision|Event -> Event` | Direct causal assertion explicitly present in canonical metadata. Mere chronology, correlation, or “after” is insufficient. |
| `supersedes` | `Decision -> Decision` | Newer decision replaces an older decision. Must be acyclic and temporally non-regressive when both times are known. |

Every semantic relation has a deterministic `edge_id`, although Memory MCP stores the relation tuple. Compute `edge_id = sha256(namespace || from_entity_id || relation_type || to_entity_id || sorted(source_claim_ids))`. Duplicate tuples merge only when endpoints and relation type match; provenance sets union deterministically. Inverse, symmetric, transitive, and causal edges are never synthesized. Claim lifecycle supersession remains distinct from semantic `Decision -> Decision` supersession.

## 4. Canonical metadata and mandatory provenance

A semantic record must be supplied by a claim’s explicit metadata extension, conceptually:

```json
{
  "semantic": {
    "entities": [{"entity_id":"person:jang-jaewon","type":"Person","canonical_name":"Jang Jaewon","aliases":[]}],
    "relations": [{"from":"person:jang-jaewon","type":"decided","to":"decision:memory-graph-onboarding"}]
  }
}
```

For every projected entity and edge, persist a provenance record with all fields:

- `source_claim_id`, `claim_key`, claim `status`, claim `content_hash`
- relative canonical `path`, 1-based marker `line`, source file `source_content_hash`
- at least one evidence item with `evidence_id`, relative evidence `path`, and 64-hex `content_hash`
- `writer_version`, `extraction_version` when present
- semantic contract version and normalized semantic-record hash
- claim `created_at`, `updated_at`, confidence, and `captured_at` when present

Missing or malformed provenance quarantines only the semantic record when the underlying v0.5 claim is otherwise valid. A path escape, secret-like payload, claim-marker mismatch, duplicate claim ID, or invalid canonical claim continues to fail the entire plan as in v0.5. Graph traversal returns provenance locators, not evidence text.

## 5. Identity and entity resolution

Resolution is deterministic and ordered:

1. Match exact `(type, entity_id)` in the owned projection.
2. Otherwise match a type-scoped exact external ID only when the metadata provides a recognized scheme and one existing entity owns it.
3. Otherwise create the explicit `(type, entity_id)`.
4. Names and aliases are display/search keys only. They never merge entities.

Normalize display lookup with Unicode NFKC, trim, collapse internal whitespace, and locale-independent casefold. Preserve original spelling. If a normalized name or alias maps to multiple IDs, return all candidates and mark lookup ambiguous. Cross-type identity, fuzzy matching, transliteration, honorific stripping, email local-part matching, and project-name prefix matching are forbidden autonomous resolvers.

An existing `entity_id` with a different type, incompatible external ID, or conflicting canonical name is quarantined as `identity_conflict`; do not mutate the prior semantic entity. Renaming requires the same explicit ID plus provenance and is represented as a changed entity during reconciliation.

## 6. Temporal and status model

- Parse timestamps only as RFC 3339 with an explicit offset; store normalized UTC plus the original value. Date-only values remain dates and are not fabricated as midnight. Intervals require `start <= end`.
- Claim status controls eligibility: `current`, `tentative`, and legacy `active` may project. `tentative` semantic records remain visibly tentative and are excluded from default “current” answers unless requested. `superseded`, `rejected`, `conflicted`, and `archived` claims do not project active semantic entities or edges.
- `valid_from`/`valid_to` express real-world validity. Claim `created_at`/`updated_at` express record time. Do not substitute one for the other.
- Multiple current/tentative claims grounding incompatible values, times, identities, or endpoints are quarantined as a conflict. Timestamp recency never selects a winner.
- Semantic `supersedes` requires explicit metadata, distinct Decision IDs, no cycle, and, when both effective times are known, successor time not earlier than predecessor time.

## 7. Ambiguity quarantine

Quarantine is deterministic inert snapshot data, not a graph fact. Each item contains `quarantine_id`, `reason_code`, normalized candidate record hash, source claim/provenance locator, candidate entity IDs, and safe remediation text. It must not contain secret-like rejected text.

Reason codes include `missing_provenance`, `unknown_type`, `unknown_relation`, `invalid_endpoint_type`, `unresolved_endpoint`, `ambiguous_alias`, `identity_conflict`, `temporal_conflict`, `multiple_current_assertions`, `causality_not_explicit`, and `supersession_cycle`.

A quarantined semantic record emits no semantic entity or edge. Unrelated valid records continue. Output ordering is by `(reason_code, source_claim_id, candidate_hash)`. Repeated identical input yields identical quarantine IDs and snapshot hash.

## 8. Incremental reconciliation and deletion

- Build the complete desired semantic projection from the current canonical snapshot, then diff against freshly read owned backend state. Never patch from file timestamps alone.
- Ownership remains exact namespace prefix. Semantic reconciliation may create/update/delete only `semantic:*` entities and relations whose endpoints are owned. Preserve v0.5 core/claim objects and foreign entities.
- Reference count each semantic entity by eligible grounding claim IDs. Removing, archiving, rejecting, or superseding one claim removes only its provenance contribution. Delete the entity only when no eligible grounding remains and no desired owned semantic relation references it.
- Remove stale relations before stale entities. Changed observations use v0.5 delete/recreate semantics with all incident owned relations recreated. Foreign inbound relations to a stale owned semantic entity are reported and removed before deletion, while the foreign entity is untouched.
- Quarantined replacements do not delete the last previously verified semantic fact in the same transaction. Mark it `stale_pending_resolution` in private state and require an explicit safe-removal policy or subsequent unambiguous canonical state. This prevents malformed updates from silently erasing usable locators.
- Retain crash-safe prepare/apply/verify journal semantics. Retry always rereads the backend and applies only remaining delta. Verification compares exact entity observations, relations, provenance counts, quarantine summary, and representative retrieval.

## 9. Query surface

Extend the direct-CLI-only `query-plan` contract, not the initial Gateway manifest, with bounded deterministic filters:

- `entity`: exact `entity_id`, external ID, or normalized display key, with required type when display lookup is non-unique
- `relation`: one or more of the four relation types, optional direction (`out`, `in`, `both`)
- `time`: `as_of`, `from`, `to`, with explicit inclusion of unknown-time records
- `status`: default `current`; opt in to `tentative`, historical, quarantined, or `stale_pending_resolution`
- traversal: maximum depth 3, maximum 100 entities, 200 edges, stable lexical ordering, cycle-safe
- `explain:true`: return every hop’s source claim IDs, path/line/content hashes, ambiguity flags, and canonical hydration requests

No natural-language inference runs inside query. Results must state `canonical:false`, `locator_only:true`, namespace, source/snapshot hashes, truncation, and conflicts. The caller must rehydrate every material claim from canonical Markdown before answering. Simple single-fact lookup still routes to Memory Search.

## 10. Snapshot, migration, and rollback

- Introduce a new snapshot schema version while retaining a reader/validator for v0.5. New fields: semantic contract version, semantic entities, semantic relations with provenance, quarantine, and semantic counts. Hash all fields except `snapshot_hash` using the existing canonical JSON digest rules.
- Migration is additive and two-phase: (1) parse v0.5 and build/validate a semantic candidate with no mutation; (2) reconcile semantic-owned objects only after candidate validation. Existing claim/core graph remains byte-for-byte semantically equivalent.
- First migration must write a mode-0600 pre-migration snapshot and transaction journal outside canonical memory. A dry-run reports creates/deletes/quarantine and refuses unknown schema versions.
- Rollback deletes only semantic projection objects created by the target contract version, restores the prior private snapshot pointer, and leaves v0.5 objects, canonical Markdown, cron, foreign data, and unrelated namespaces untouched. If mutation outcome is ambiguous, rollback first reconciles actual backend state.
- Downgrade readers ignore semantic fields only after validating the newer snapshot and explicit operator selection; they must not overwrite a newer state pointer accidentally.

## 11. Adversarial acceptance tests

1. Same Person ID and spelling across two claims merges provenance deterministically; removing one claim retains the entity.
2. Same normalized name with two explicit Person IDs returns ambiguity and never merges.
3. Same ID changes Person to Project, record is quarantined and prior verified entity is not overwritten.
4. Missing evidence hash or source line quarantines semantic metadata while preserving the valid v0.5 claim.
5. Prose says “A happened after B”; no `caused` edge is emitted. Explicit valid metadata emits it.
6. `caused` with Person source, `decided` with Project source, or unknown relation fails into typed quarantine.
7. Two current claims assert incompatible endpoints for one semantic record; neither new edge is active and conflict is reported.
8. Tentative record is stored as tentative, absent from default-current query, present only with status opt-in.
9. Supersession chain is accepted; self-edge, cycle, and backwards effective time are quarantined.
10. Date-only values remain dates; offset timestamps normalize to the same UTC instant without changing original text.
11. Archive/delete one grounding claim removes its provenance only; last grounding removal plans relation deletion before entity deletion.
12. Malformed replacement cannot erase the last verified semantic locator; it becomes `stale_pending_resolution`.
13. Foreign entity and unrelated namespace survive migration, reconciliation, rollback, and stale-owned deletion.
14. Crash/timeout after each mutation boundary resumes from backend truth with no duplicate observations or relations.
15. Reordered source files, JSON keys, aliases, evidence, and metadata produce the same semantic IDs, order, and snapshot hash.
16. Alias collision, Unicode confusables, transliteration variants, and casefold collisions never cause autonomous merge.
17. Secret-like semantic names/attributes are rejected or redacted under the existing selected policy and never appear in quarantine diagnostics.
18. Query depth/count bounds, cycle handling, truncation flag, provenance paths, and hydration requests are deterministic.
19. Migration dry-run is inert; migration plus rollback restores the exact v0.5 backend projection and prior private state pointer.
20. Registry/package validation confirms the paired Skill/Harness retain aligned canonical name/title, a version bump, accurate write-safe classification, and no unsupported Gateway schema keywords.

## 12. Implementation gates

Implementation is not ready for release until parser/schema tests, all v0.5 regressions, adversarial tests above, repository validation, per-command Gateway prepare tests, fake-backend crash recovery, and a representative private namespace migration/rollback pass. Publication, installation, live backend mutation, and canonical writer-format changes remain separately approval-gated.
