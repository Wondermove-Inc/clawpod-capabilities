# Memory Graph v0.10 Release Evidence

## Fresh-agent inert update and rollback example

A fresh agent must treat an update package as inert until package digest validation,
Gateway validation/trust, and a representative prepare path succeed. If any gate
fails, restore the exact pre-update paired Skill/Harness backup, verify its digest,
and do not reuse proposal IDs, approval manifests, journals, or semantic snapshots.
Entity renames create a new explicit identity and supersede the old proposal; they
never merge identities or rewrite canonical Markdown. These are examples only and
perform no install, graph mutation, publication, or canonical write.

Status: implementation candidate, not published or installed.

Registry-first classification: `refine`, starting from merged `origin/main` commit `efe7c7d`.

Implemented: bounded extractor input, strict proposal validation, deterministic review queue, explicit human approval manifest, approved semantic snapshot, owned-only reconciliation contract with resumable journal, and deterministic offline semantic-first SVG graph canvas with real node/edge datasets, relation labels, filters, pan/zoom, click details, and trust-state styling.

Adversarial coverage includes source boundary, provenance and stale hashes, malformed output, prompt-like data, secret redaction, inert identity/aliases, chronology-only cause rejection, inert candidates, retry-safe partial reconciliation, idempotency, stale owned deletion, foreign preservation, canonical immutability, HTML escaping/offline behavior, exact graph node/edge dataset parity, no external resource URLs, candidate/inferred non-approval, deterministic HTML bytes, and 20-claim bound.

Verification completed on 2026-08-10:

- `python3 -m unittest discover -s harnesses/memory-graph/tests -v`: 91 passed.
- `python3 -m unittest discover -s tests -v`: 25 passed.
- `python3 scripts/validate.py`: 34 capability entries validated.
- `python3 -m py_compile harnesses/memory-graph/memory_graph.py harnesses/memory-graph/ontology.py harnesses/memory-graph/semantic_v10.py`: passed.
- `git diff --check`: passed.
- `python3 scripts/sync_registry.py`: registry synchronized.

No publication, install, restart, credential use, live graph mutation, or canonical memory mutation was performed.
