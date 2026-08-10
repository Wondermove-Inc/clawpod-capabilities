# Memory Graph v0.10 Semantic Refinement Contract

## Boundary

Canonical inputs are only direct regular, non-symlink root `memory/*.md` files. Selection is deterministic by `(path, line, claim_id)`, limited to 1–20. Every extractor row carries exact claim ID, path, line range, source SHA-256, and claim SHA-256. Endpoint catalogs contain only already validated explicit typed IDs and never authorize entity invention.

## Offline pipeline

The Harness does not call models, networks, Memory MCP, or canonical writers in the authoring commands. A supplied closed-shape extractor bundle is freshness-checked and converted to inert candidate Entity Proposals and Assertion proposals. Prompt injection remains claim data. Malformed, stale, secret-like, unsupported, or chronology-only causal proposals are quarantined.

Approval is never automatic. A closed manifest records `human:*` reviewer, non-empty reason, timezone-aware time, and approved/rejected lifecycle. `caused` additionally requires direct causal wording and a human reason containing `direct`. Alias and identity records remain inert.

## Snapshot and reconciliation

The approved snapshot contains approved private semantic entities and assertion relations only, plus separate inert candidates/quarantine; inference overlays are empty. Reconciliation accepts a strict Memory MCP view, computes only exact owned semantic create/update/delete operations, preserves foreign namespace records, and returns a deterministic transaction ID, dispatch cursor, retry-safe state, and verification target. The trusted caller performs bounded dispatch and must re-read/reconcile until idempotent. Canonical Markdown is immutable.

## HTML

Export is one deterministic UTF-8 HTML file with an actual SVG semantic graph canvas, entity nodes, assertion edges, relation labels, circular deterministic layout, pan/zoom, and node/edge click details. It has no external dependencies, resource URLs, or requests; JSON-escapes HTML-sensitive characters; and exposes search, semantic type, and claim-cluster filters. Canonical explicit, approved private proposal, and candidate/inert records use distinct labels and colors. Candidate edges are dashed and retain candidate status; inferred edges are excluded and neither can appear as approved.
