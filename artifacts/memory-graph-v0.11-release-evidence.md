# Memory Graph v0.11 release evidence

Version: 0.11.0

The paired Skill and Harness implement a practical causal graph over `Person`, `Project`, `Decision`, `Cause`, `Effect`, and `Event` without requiring canonical-memory annotations. The Harness deterministically pages and seals source records; an external agent authors untrusted candidates from ordinary natural-language claims; the Harness then validates exact provenance, lifecycle, endpoints, and direct relation evidence. Causal and impact relations require direct wording, and chronology alone is rejected. Review pages are bounded to 20. Decision queries return locator-only results; hydration revalidates canonical source and claim hashes.

Real direct-corpus verification on 2026-08-11 processed 213 claims in 11 pages (`20,20,20,20,20,20,20,20,20,20,13`). Lifecycle totals were 152 current, 4 tentative, 55 superseded, and 2 archived. Exactly 154 claims were proposal-eligible; 57 were lifecycle-ineligible and 2 current claims were excluded by plan conflicts. The sentence-anchored precision driver authored 72 exact-span-grounded proposals. Harness validation retained 48 endpoint entities and 24 assertions: 18 `decided`, 5 `motivated_by`, and 1 `caused`. The prior seven present-policy additions remain sound; the two new assertions are the dotted WORKFLOW.md Korean policy and the complete 213-character immediate post-install onboarding policy. All 24 were individually inspected and preserve their language-valid non-overlapping evidence order. It rejected 8 fragmentary Decision subjects, 4 incomplete actors, 2 negated rationales, 4 blocked-status impact matches, and deterministically suppressed 1 duplicate stopped-Plugin decision paraphrase. The richer detailed Plugin stop and its same-claim rationale remain with exact evidence; the shorter direction paraphrase is not a second semantic Decision. The adopted rumor policy and shared-storage decision remain supported. Every retained assertion was inspected for a complete actor/action or causal proposition and ordered non-overlapping spans. The corpus reports honest zeros for `affected`, `participates_in`, and `supersedes`. All proposals remain inert and require human review. The committed JSON contains no claim prose and provides per-assertion proposition class, endpoint types, cue, span lengths, evidence hash, and rejected-by-reason diagnostics.

Compatibility retained from v0.10 includes explicit human approval, causal-review binding, lifecycle behavior, exact provenance, optional collision-safe private 0600 JSON outputs, owned-only reconciliation, foreign dependency protection, resumable verification, canonical-memory immutability, no network/model invocation, and no live MCP dispatch.

Local release validation:

- `python3 -m unittest discover -s harnesses/memory-graph/tests -p 'test_*.py' -q`
- `python3 scripts/sync_registry.py --check`
- `python3 scripts/validate.py`
- `python3 -m unittest tests.test_registry_sync tests.test_registry_sync_workflow -v`
- deterministic `semantic_contract_inventory.py` and `release_inventory.py` comparisons
- real-corpus complete-page seal and natural-language candidate validation smoke
- `git diff --check`

No install, push, PR, live MCP mutation, or canonical memory write is part of this release.
