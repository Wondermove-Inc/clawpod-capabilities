# Memory Graph v0.8.0 Local Release Evidence

## Status

- [VERIFIED] Local paired Skill + Harness refinement is complete on `feat/memory-graph-v08-ontology`.
- [VERIFIED] HEAD: `23ea411cb4470cb64943b60f5878062709317ba4`.
- [VERIFIED] Base: merged canonical registry `origin/main` at `d7f215334864049c7fcbfd1f293171af32f0f4cc`.
- [VERIFIED] Classification: `refine` the existing `memory-graph` capability, not a new capability.
- [VERIFIED] No push, PR, publication, installation, Gateway restart, canonical-memory mutation, or live graph mutation was performed.

## Architecture delivered

- Locator layer remains compatible with v0.7 schema-v5 snapshots.
- Domain layer remains bounded to `Person`, `Project`, `Decision`, and `Event` with `participates_in`, `decided`, `caused`, and `supersedes`.
- Assertion layer adds content-addressed assertion IDs, canonical provenance, extraction/review method, lifecycle status, temporal precision, confidence separation, and quarantine.
- Constraint/evaluation layer adds deterministic fail-closed shape validation, review queue, competency-question evaluation, and semantic-first views.
- Causality requires direct human approval; chronology alone cannot create `caused`.
- Identity candidates never auto-merge or project into the semantic graph.
- The Harness contains no model or network integration.

## Commits

1. `6c1ca23` — exact v0.8 assertion ontology contract.
2. `8f8dfd5` — paired Skill/Harness implementation, manifests, registry, fixtures, and tests.
3. `23ea411` — independent adversarial hardening.

## Verification

### Full Memory Graph suite

Command:

```text
python3 -m unittest discover -s harnesses/memory-graph/tests -p 'test*.py' -v
```

Result: **74/74 passed** in 14.577s.

Coverage includes v0.7 regressions plus v0.8 success, malformed and secret-like input, source immutability, stale provenance, identity ambiguity, causality approval, lifecycle separation, temporal precision, namespace isolation, no model/network surface, semantic-first CQ output, naive timestamps, supersession cycles, unknown identity endpoints, and schema-v5 compatibility.

### Repository registry and validator

Commands:

```text
python3 scripts/sync_registry.py
python3 scripts/validate.py
python3 -m unittest tests.test_registry_sync tests.test_validator -v
git diff --check
```

Results:

- Registry synchronized.
- **34 capability entries validated**.
- Registry/validator tests: **12/12 passed**.
- `git diff --check`: passed.
- Paired package versions and linked Harness version: **0.8.0**.

### Representative non-live ontology E2E

`test_success_cq_and_semantic_first_view` builds a disposable fixture graph from canonical-format test claims and at least 12 approved assertions, validates the assertion bundle, evaluates CQ1–CQ5, and emits a semantic-first view. It passed in the full suite.

Release gates proven in fixtures:

- approved assertions ≥ 12,
- unsupported approved edge = 0 for accepted fixture paths,
- locator/canonical hydration requests are retained,
- structural hairball edges are not the default semantic view,
- candidate and quarantined material remain separate from approved assertions.

### Source and safety boundaries

- Canonical/core/evidence source immutability is asserted in tests.
- Path traversal, symlink, stale hash, namespace, endpoint, status, temporal, identity, and secret-like failures fail closed or quarantine.
- v0.7 schema-v5 compatibility test passed.
- No credentials were used.

## Adversarial defects fixed

1. Null review on a causal assertion could raise instead of deterministically quarantining.
2. Timezone-naive temporal timestamps were accepted.
3. Reciprocal `supersedes` assertions could remain projected as a cycle.
4. Identity candidates did not fully reject unknown endpoints/source claims or invalid score/method/config fields.

All four have regression tests and passed after hardening.

## Artifacts

- Research: `/workspace/shared/wondermove/main/memory-graph/memory-graph-v0.8-ontology-research-2026-08-10.md`
  - SHA-256: `1a00bebf3f68b4eb86ac71b56711d90f60b7a5a5d1e2e25e05b9c47cfd7afd8e`
- Contract: `artifacts/memory-graph-v0.8-assertion-ontology-contract.md`
  - SHA-256: `55e86a019e96a89e572777e2d4a8ff2caab355c0fa46c2942813f907128ea58c`
- Release evidence: this file.

## Residual limits and required approvals

- The fixture proves the ontology contract, not usefulness on Forge's live canonical corpus.
- Live semantic value requires a bounded reviewed assertion seed from eligible canonical claims after installation.
- Publication requires separate approval for branch push and PR creation. Do not merge automatically.
- Installation and live graph regeneration require separate approval after merge.
- Current Gateway `harness.validate`, trust, and representative `prepare → run` must be repeated after installation against the installed manifest; repository tests are not a substitute for that post-install proof.
- OWL reasoning, automatic entity merge, link prediction, community summaries, cross-agent graphs, and canonical-memory mutation remain intentionally out of scope.

## WORKFLOW.md

- [VERIFIED] `WORKFLOW.md` was not changed. The existing registry-first and approval policies already governed this refinement; no reusable workspace-policy correction was required.
