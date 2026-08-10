# Memory Graph v0.7.0 release evidence

Status: local release candidate. Classification: **REFINE** the existing paired Memory Graph capability. This evidence does not authorize publication, installation, restart, or live graph mutation.

## Scope

v0.7.0 adds a read-only semantic inference overlay for canonical memory claims that lack explicit semantic metadata. The agent proposes bounded candidate JSON; the Harness performs deterministic validation, freshness checking, quarantine, projection, caching, querying, and visualization. The Harness performs no model, network, or live Memory MCP call on these candidate paths.

Canonical core/context files, `MEMORY.md`/`memory.md`, direct `memory/*.md`, and evidence remain read-only. Inference output is private, noncanonical, disposable derived state and can only populate `inferred_relations`. Canonical semantic metadata remains the sole source of `explicit_relations`.

## Candidate contract

- exact namespace, source snapshot hash, source digest, extractor name/version/config hash
- exact existing explicit semantic endpoint IDs and types only
- canonical claim ID, direct memory path, line range, source hash, and claim hash
- bounded ontology and endpoint rules inherited from v0.6
- finite confidence in `[0,1]`, preserved only for ranking/display
- stable candidate, edge, and quarantine identifiers
- stale, malformed, secret-like, symlinked, escaped, or ambiguous candidates fail closed

## Implementation

- Design contract: `6e6ee7fa32fef84160bcfa997f71817219fb1363`
- Implementation: `21c9c3dc924b35584308f6f8bca371bf784fd54a`
- Adversarial hardening: `d2489f0`

Adversarial review fixed:

1. symlinked candidate-input bypass,
2. symlinked cache state-root escape,
3. stale cache relations not being reconciled/deleted,
4. inaccurate `readOnly` classification for cache-writing projection,
5. endpoint-domain validation precedence for deterministic quarantine.

## Verification

- focused and adversarial test suite: **61/61 passed**
- Python compilation: passed
- repository validator: **34 capability entries passed**
- registry synchronization check: passed
- `git diff --check`: passed
- representative local non-live inference E2E: passed
- paired Skill/Harness version and registry digest alignment: passed
- current Gateway command-schema subset: covered by manifest regression tests
- canonical/core/memory/evidence source immutability: verified by before/after digest tests

No installation, Gateway restart, canonical-memory mutation, publication, credential use, model API call, or live Memory MCP mutation occurred.

## Migration and rollback

v0.6 snapshots remain readable. v0.7 inference is opt-in and separated from explicit relations. Existing onboard/reconciliation behavior remains unchanged unless a validated candidate bundle is supplied. Rollback is package-level: restore the paired v0.6 Skill/Harness and discard the private v0.7 cache/overlay. Canonical sources require no rollback because they are never modified.

## Remaining limits

- The Harness does not generate candidate JSON; an agent must create it from eligible canonical claim prose.
- Candidates may reference only already existing explicit semantic entities. v0.7 does not infer or create new semantic entities or resolve aliases.
- Inferred relations are noncanonical locators and must be rehydrated through `memory_search`/`memory_get` before answering.
- Confidence does not promote an inferred relation into an explicit fact.
- Real live-graph behavior is intentionally untested until separate installation and mutation approval.
