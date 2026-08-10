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

Final scope-freeze verification completed on 2026-08-10:

- Refinement loops completed: 67 across 16 independent audit rounds.
- `python3 -m unittest discover -s harnesses/memory-graph/tests -q`: 137 passed.
- `python3 -m unittest discover -s tests -q`: 25 passed.
- `python3 scripts/validate.py`: 34 capability entries validated.
- `python3 -m compileall -q harnesses/memory-graph`: passed.
- Harness JSON parsing and `git diff --check`: passed.
- Deterministic release inventory repeated with digest `931e080096f20e4d06cc6720f829c185edbe483b6d25e86028f390eb3b056bf9`.
- Added-history secret-shaped scan found only deliberate synthetic redaction fixtures (`password=abcdefghijklmnop`); no real credential or secret was added.
- Registry synchronization and clean-worktree checks passed at candidate head `0b1173a2773229da6bcbfc88d84740e8d74ca039` before this evidence-only commit.

Final hardening includes exact byte/BOM/CRLF provenance, complete cursor-page assembly, extractor allowlisting, reviewer separation of duties, approval expiry/revocation/source-drift checks, lifecycle and contradiction matrices, exact backend receipts/readback, foreign namespace preservation, bounded query/hydration, atomic dirfd-anchored private output, inert offline HTML, deterministic release inventory, all 10 semantic command contracts, and fresh-agent workflows that grant no implicit approval or write authority.

Known limitation: Gateway `harness.run.prepare` cannot exercise this uninstalled working-tree Harness without prohibited install/trust mutation. Static manifest validation and command-contract inventory passed; representative Gateway prepare/run remains an installation-time gate.

No publication, push, PR, install, restart, credential use, live graph mutation, or canonical memory mutation was performed during candidate verification.
