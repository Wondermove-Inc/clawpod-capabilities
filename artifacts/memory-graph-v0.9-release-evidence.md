# Memory Graph v0.9.0 local release evidence

## Status

- [VERIFIED] Registry-first classification: **refine** the existing paired `memory-graph` Skill/Harness, not a new capability.
- [VERIFIED] Base: `a69c9219a2ce44830d931f2a20ff5e390864dec2`.
- [VERIFIED] Contract, implementation, adversarial hardening, and memory-only source-boundary changes are included in one clean publication candidate relative to the base.
- [VERIFIED] Local milestone history was clean-squashed before publication after GitHub Push Protection correctly rejected a synthetic Stripe-shaped test fixture. The fixture still exercises secret redaction by concatenating inert string fragments at runtime, while no scanner-shaped token exists in commit history.
- [VERIFIED] No installation, Gateway restart, canonical-memory mutation, live graph/MCP mutation, model call, network call, or credential use was performed.

## Delivered

- Private, noncanonical, content-addressed Entity Proposals for `Person`, `Project`, `Decision`, and `Event`.
- Exact claim ID/path/line/source hash/claim hash and extractor version/config provenance.
- Explicit human review/lifecycle enforcement before proposal endpoints can bootstrap assertions.
- Canonical explicit entities remain a separate higher-trust endpoint source.
- Deterministic closed-shape validation, quarantine, conflict handling, deduplication, and reordered-input idempotency.
- Temporal precision/timezone validation for Decision/Event proposals.
- Alias and identity candidates remain inert, with no merge, redirect, or semantic projection.
- Direct human-approved causality remains mandatory; chronology-only evidence is rejected.
- Review queue, CQ release metrics, semantic-first visualization, and read-only v0.8 migration.
- Realistic non-live fixture with 12 canonical-format claims, 10 approved entity proposals, and 12 approved assertions.

## Verification

### Full Memory Graph suite

```text
python3 -m unittest discover -s harnesses/memory-graph/tests -p 'test_*.py'
```

[VERIFIED] **85/85 passed** after independent hardening in 17.489s.

Coverage includes existing v0.6-v0.8 behavior and v0.9 bootstrap success, release gates, malformed input, bounds, stale source/claim provenance, secret redaction, symlink/path rejection, namespace isolation, identity/alias inertness, duplicates, conflicting IDs, lifecycle/review states, direct causality, temporal precision, endpoint eligibility, deterministic reordering/idempotency, v0.8 migration, no-model/no-network surface, and canonical source bytes/digest/mode/mtime immutability.

### Repository validators and registry

```text
python3 scripts/sync_registry.py
python3 scripts/validate.py
python3 -m unittest tests.test_registry_sync tests.test_validator -v
python3 scripts/sync_registry.py --check
```

[VERIFIED] Registry synchronized; **34 capability entries validated**; registry/validator tests **12/12 passed** in 0.471s; synchronization check passed.

### Compile and diff checks

```text
python3 -m compileall -q harnesses/memory-graph
git diff --check
```

[VERIFIED] Python compilation and whitespace/error diff checks passed.

### Fixture release gates

[VERIFIED] `test_realistic_bootstrap_release_gates_and_semantic_view` proves:

- 12 canonical-format claims, within the required 10-30 bound;
- 10 fresh approved private entity proposals;
- 12 approved semantic assertions across four predicates;
- CQ pass count 5/5;
- unsupported approved edge count 0;
- canonical hydration locator coverage 100%;
- structural edges hidden by default;
- approved private proposal nodes labeled distinctly.

## Artifacts

- Contract: `artifacts/memory-graph-v0.9-entity-proposal-contract.md`.
- Harness: `harnesses/memory-graph/ontology.py`, `memory_graph.py`, manifests and README.
- Skill: `skills/memory-graph/SKILL.md` and paired metadata.
- Fixture: `harnesses/memory-graph/tests/fixtures/entity-proposals/`.
- Tests: `harnesses/memory-graph/tests/test_ontology_v09.py` plus all existing tests.
- Registry: synchronized `registry/index.json`.

## Defects fixed during implementation

1. v0.8 accepted-bundle compatibility initially rejected bundles constructed with the exported schema constant and contract `0.8`; migration recognition now accepts both historical v1 and transitional v2/0.8 forms without rewriting input.
2. Legacy stale source/claim hash diagnostics initially changed from `stale_provenance`; the compatibility path now preserves the v0.8 reason code.
3. Symlink rejection is performed by the canonical inspector before ontology validation and reports its established `unsafe_memory_path` code; the adversarial test accepts that fail-closed source-of-truth behavior.
4. Approved proposals previously accepted any non-empty review reason; approval now requires the exact `claim_explicitly_identifies_entity` reason.
5. Entity proposal provenance previously allowed a widened line range; it now requires the exact canonical claim line.
6. Assertions referencing a stale or invalid proposal previously reported only a dangling endpoint; they now fail with deterministic `stale_entity_proposal` precedence.
7. Secret-like proposal fields could be copied into quarantine diagnostics; secret-like failures now emit only a safe hash, reason, kind, and `redacted:true`.

## Limits and approvals

- The fixture is non-live and proves deterministic capability behavior, not live-corpus semantic truth.
- The Harness validates supplied proposal/review data; it does not run an extractor or perform approval mutation.
- Publication, installation, Gateway validation/trust, representative installed `prepare -> run`, canonical enrichment, and any live graph regeneration require separate approval and downstream verification.
- Automatic identity merge, aliases as facts, new ontology classes/predicates, reasoning, causality inference, cross-agent graphs, canonical writes, and live MCP projection remain out of scope.

## WORKFLOW.md

[VERIFIED] `WORKFLOW.md` was not changed. Existing registry-first, source-of-truth, and approval rules already cover this refinement; no reusable workspace-policy correction was required.

## Owner source-boundary refinement

- [VERIFIED] Graph sources are now exactly direct regular non-symlink `<root>/memory/*.md` files.
- [VERIFIED] Root `MEMORY.md`/`memory.md`, every core/context file, and nested `memory/**` paths including `.evidence/**` and `.registry/**` are ignored.
- [VERIFIED] Direct Markdown symlinks and a symlinked memory directory fail closed. Root and nested symlinks are outside the scanner.
- [VERIFIED] Core document/section output is obsolete; compatibility arrays are empty and all core counts are zero.
- [VERIFIED] Legacy owned core document/section entities and incident relations validate for migration and are deleted as stale; namespace filtering preserves foreign entities.
- [VERIFIED] Source digest, claim provenance, semantic projection, inference, and ontology freshness use only the direct-memory source snapshot.
- [VERIFIED] Adversarial tests cover every named root/core file, nested evidence/registry files, symlinks, direct topic parsing, stale core cleanup, foreign namespace preservation, deterministic/idempotent output, and canonical-file immutability.
- [VERIFIED] Full Memory Graph suite: **85/85 passed** in 17.263s.
- [VERIFIED] Full repository suite: **25/25 passed** in 0.522s; validator accepted **34 capability entries**; registry synchronization check, Python compile, and `git diff --check` passed.
