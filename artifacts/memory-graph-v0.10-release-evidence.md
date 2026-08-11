# Memory Graph v0.10 Release Evidence

## v0.10.3 canonical claim prose mapping fix

The `semantic-extractor-input` mapper now reads canonical prose from the planner's `claim` field instead of the obsolete `value` field. Exact nonempty prose is emitted as `claim_text`; the existing whole-value `[REDACTED]` secret handling and strict non-string failure behavior are preserved. Regression coverage uses canonical `claim`-shaped fixtures and proves exact prose, nonempty output, secret removal, and no type coercion. Gateway was not modified.

Status: v0.10.3 implementation candidate, not published, installed, trusted, restarted, or dispatched. No semantic/MCP or canonical-memory writes were performed.

Verification completed on 2026-08-11:

- `python3 -m unittest discover -s harnesses/memory-graph/tests -p 'test_*.py' -v`: 144 passed.
- `python3 -m unittest discover -s tests -p 'test_*.py' -v`: 25 passed.
- `python3 scripts/validate.py`: 34 capability entries validated.
- `python3 scripts/sync_registry.py --check`: paired Skill/Harness v0.10.3 metadata and package digests synchronized.
- Compileall, JSON parsing, and `git diff --check`: passed.
- Deterministic release inventory digest: `8a7bd2180c825028078ea79c96ab002f077ad6d500d5da68f0479a8e50221ed1`.
- Semantic command-contract inventory digest: `a7f34c33790cf6c77064266d3c5dac12fe258e6c3f0c62a32cee13a764d15405`.

## v0.10.2 Gateway relative-output integration fix

Workboard: `6fde1a44-35fe-490e-92b1-efc97cf3cd5c`. Classification: `refine`; the canonical registry already contained the paired Memory Graph Skill/Harness v0.10.0 and no separate capability was created.

The optional `semantic-extractor-input` private-output lane now maps `output` as a validated string without `pathRole`, preventing Gateway from canonicalizing its required relative filename before Harness execution. `outputRoot` remains the sole approved output path with `valueType: path` and `pathRole: output`. Harness containment and private-write behavior are unchanged, and canonical memory Markdown remains read-only. Gateway was not modified.

Status: v0.10.2 implementation candidate, not published, installed, trusted, or dispatched.

Verification completed on 2026-08-11:

- `python3 -m unittest discover -s harnesses/memory-graph/tests -p 'test_*.py' -q`: 143 passed.
- `python3 -m unittest discover -s tests -p 'test_*.py' -q`: 25 passed.
- Skill quick validation, `python3 scripts/validate.py` (34 capability entries), compileall, JSON parsing, and `git diff --check`: passed.
- Registry synchronization/check: passed for paired Skill/Harness v0.10.2 metadata and package digests.
- Deterministic release inventory digest: `1dcc4776f28affd6a1a080fc7d27c1b106acc314a2a31ffffdf5477d16679f37`.
- Semantic command-contract inventory digest: `a7f34c33790cf6c77064266d3c5dac12fe258e6c3f0c62a32cee13a764d15405`.

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
