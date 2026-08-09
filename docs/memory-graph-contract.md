# Memory Graph Contract

## Classification and boundary

Registry-first searches for `memory graph`, `knowledge graph`, and `memory MCP` returned no candidates, so this paired capability is classified **CREATE**. The Skill selects and grounds the workflow; the CLI Harness performs deterministic read-only parsing and planning.

Recognized OpenClaw core workspace Markdown and canonical memory Markdown are the only source inputs. This graph, every snapshot, query result, diff, and export batch is noncanonical, disposable, and fully rebuildable. No command writes canonical Markdown. `onboard` is the sole mutating path: it verifies the live schema, invokes direct Memory MCP (never Gateway), and may mutate only its owned namespace.

## Per-agent ownership and authorization

`plan`, `diff`, and `onboard` require an explicit portable agent ID. The namespace is `memory-graph:v1:<24-hex>:` and binds that ID to a SHA-256 workspace identity. Supply a stable canonical workspace ID when available; otherwise the resolved workspace path is the identity. Every entity name and relation endpoint is prefixed with the namespace.

Standing owner authorization applies only to derived graph create/update/delete in that exact namespace. It excludes canonical Markdown, other workspaces or namespaces, cross-agent sharing, publication, and unrelated entities. Every run discovers the live backend with `read_graph`; lost local state therefore still reconciles stale owned records. Deletes are limited to namespace-prefixed entities. All inbound and outbound relations incident to owned nodes participate in safety analysis: foreign entities are never deleted, foreign inbound links to current owned nodes are preserved and reported, and links incident to stale owned nodes are removed and reported before stale-node deletion.

The current real writer generally supplies claims and provenance, not normalized semantic entities and edges. Consequently, default plans mostly contain `MemoryClaim` and `ClaimKey` entities plus `has_claim_key` provenance structure. People/project/capability/ownership and similar fact relations are emitted only when explicit metadata says so. Richer relations require a separate extraction/enrichment stage with canonical entity resolution and grounding to the Markdown source; claim prose alone is not promoted into semantic edges.

The fixed portable core allowlist is exactly `SOUL.md`, `IDENTITY.md`, `USER.md`, `AGENTS.md`, `ORGANIZATIONS.md`, and `WORKFLOW.md`. `BOOTSTRAP.md`, `HEARTBEAT.md`, and `TOOLS.md` are explicitly excluded. Source classes are persona, identity, user_profile, agent_policy, organization, and workflow. Root `MEMORY.md`/`memory.md` is memory_index; direct `memory/*.md` is memory_claim. Arbitrary Markdown and config/secret files are never scanned. Each present core file produces a document and its Markdown headings produce sections with relative path, exact 1-based line range, source content SHA-256, source class, and deterministic workspace-contract authority class. The graph records only structural agent/workspace relations (`has_identity`, `follows_persona`, `has_user_profile`, `follows_policy`, `belongs_to_organization_context`, and `follows_workflow`) plus `has_memory_claim`; it makes no semantic facts or content-level conflict decisions from prose. Authority/precedence is preserved as explicit source metadata, and all recognized sources bind the source digest.

## Claim syntax

The primary input is the OpenClaw writer format in `MEMORY.md`, `memory.md`, and dynamically named direct `memory/*.md` topic files. A claim section has a heading, paired ID and JSON HTML comments, and the five writer bullets:

```markdown
## Alpha — owner
<!-- openclaw-memory-claim:cl_owner_2 -->
<!-- openclaw-memory-claim-json:{"claim_id":"cl_owner_2","claim_key":"project.alpha.owner","status":"current","supersedes":["cl_owner_1"],"superseded_by":[],"evidence":[{"evidence_id":"ev_2","path":"memory/.evidence/example.md","content_hash":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}]} -->
- Status: current
- Claim: Mina owns Alpha.
- Confidence: 1
- Evidence: memory/.evidence/example.md (ev_2)
- Updated: 2026-08-09T00:00:00.000Z
```

Required metadata fields are `claim_id`, `claim_key`, `status`, and non-empty `evidence`; all five bullets are required. The marker ID, metadata status, and metadata update timestamp must agree with their rendered counterparts. Statuses are `current`, `tentative`, `superseded`, `rejected`, `conflicted`, and `archived`; legacy portable blocks may use `active`. `supersedes` and `superseded_by` accept IDs or arrays. Either direction may be present independently because the central writer does not always rewrite an older claim when a newer claim supersedes it; all referenced IDs must exist and self-supersession fails closed. `entity.name` defaults to the collision-proof `claim:<claim_id>`; `entity.type` defaults to `MemoryClaim`. Explicit metadata names remain supported only when unique across claim entities and derived ClaimKey entities; collisions fail closed before insertion. Explicit `relations` require `to` and `type` and both endpoints must exist in the current plan.

The parser preserves the claim ID/key, status, both supersession directions, structured evidence metadata (including its content hash), rendered claim text, confidence, relative source path, 1-based marker line, and a SHA-256 `content_hash` over normalized claim content (`hash` remains as a compatibility alias). Fenced `memory-claim` JSON remains an optional portable/legacy input and uses `claim_key` (or legacy `key`).

## Resolution and graph semantics

- `current`, `tentative`, and legacy `active` claims are eligible.
- `archived`, `superseded`, `rejected`, `conflicted`, and claims linked out of the current position by supersession are excluded.
- Duplicate claim IDs always fail. Every eligible claim is preserved as a distinct entity, including multiple current/tentative tips with the same key; no key-based selection or overwrite occurs.
- Each eligible `claim_key` produces one `ClaimKey` entity named `claim-key:<claim_key>`. Every claim entity has an always-emitted `has_claim_key` link in `structural_relations`. These links are derived schema/provenance, not inferred facts or source-authored fact relations.
- Multiple eligible tips for a key are reported deterministically in `conflicts.ambiguous_claim_keys` as `{claim_key, claim_ids}` groups. Plan, diff, export, and query surfaces preserve this warning; canonical Markdown must be consulted to resolve it.
- Explicit source relations are emitted only in `explicit_relations`.
- Optional namespace-derived relations are emitted only in `inferred_relations` and only with `--include-inferred`; they are never presented as provenance-backed facts.
- Missing relation endpoints and unknown superseded IDs fail closed.
- Entity names, claims, evidence, relations, sources, and output object keys are deterministically ordered.

## Commands and failure behavior

All commands emit one stable JSON object on stdout and use exit `0` for success or `2` for input/validation/I/O failure. Diagnostics never echo rejected secret text. Gateway-exposed `inspect`, `plan`, and `cron-plan` return bounded summaries. Potentially large `diff`, `export-mcp-batch`, and `query-plan` remain direct CLI-only surfaces. Direct CLI callers may opt into full live JSON with `--detail`, or write a complete artifact with paired `--output-root DIR --output RELATIVE_PATH`; only that explicit file mode reports a write effect.

| Command | Result |
| --- | --- |
| `inspect` | Bounded claim/source count and digest summary |
| `plan` | Bounded graph counts and snapshot hash summary |
| `validate-plan` | Snapshot structure/invariant/hash validation |
| `diff` | Ordered stale delete then create plan against a fresh rebuild |
| `export-mcp-batch` | `create_entities`, `create_relations`, `delete_relations`, and `delete_entities` argument batches; no calls |
| `validate-snapshot` | Alias-purpose validation for stored graph snapshots |
| `query-plan` | Optional deterministic locator filter; requires subsequent canonical grounding |
| `onboard` | Schema-verify, resume/reconcile the owned namespace, read it back, verify it, and persist private state |

Input paths are constrained to `--root`. `MEMORY.md`, `memory.md`, the `memory` directory, and direct `memory/*.md` topics must be regular non-symlink paths resolved beneath that root; any symlink at those locations fails closed. A missing/invalid snapshot, malformed JSON/metadata, duplicate claim ID or entity name, dangling relation, path escape, or bad hash fails closed. Diff export accepts exactly the documented fields and validates schema version, SHA-256 hashes, conflict shape, unique ordered names/relations, exact entity/relation keys, and old/new endpoints before producing any batch. Duplicate current claim keys are reported as ambiguity rather than rejected. Secret-like text is rejected by default. `--secret-policy redact` replaces the detected value with `[REDACTED]` before any derived output.

## Snapshot and diff invariants

Snapshots declare `canonical:false` and `rebuildable:true`; `snapshot_hash` covers all other snapshot fields. A diff validates the old snapshot, rebuilds the new one from Markdown, and emits relation deletes before entity deletes, followed by entity and relation creates. Changed entities are delete/recreate operations, and every old incident explicit/structural relation is deleted and every new incident relation is recreated even when the relation tuple itself is unchanged; unchanged entities are named separately. Export batches preserve this safe order but remain inert data.

## Memory MCP compatibility

Exports match the standard Memory MCP payload shapes: `{entities:[{name,entityType,observations}]}`, `{relations:[{from,to,relationType}]}`, and `{entityNames:[...]}`. Structural relations are always exported alongside explicit relations; inferred relations are excluded unless explicitly requested. Conflict metadata remains outside MCP batches.

Every mutation batch preserves input order and is capped by both 100 items (or the lower requested export batch size) and 48 KiB of serialized UTF-8 argv payload, including executable/tool/JSON argument overhead. A single entity, relation, or entity name that cannot fit is rejected before any mutation with `mutation_item_too_large` and exact byte/cap details. A pre-spawn `E2BIG` is definitely non-mutating; `ENOENT` reports that the backend executable is unavailable. Timeout, nonzero exit, and other failures after spawn remain ambiguous and require backend reconciliation.

Autonomous `onboard` remains `writeSafe`. The agent calls trusted Gateway `harness.run.prepare`; although preparation marks it approval-required, OpenClaw 2026.4.11 `harness.run` accepts the matching `approvalIntentHash` without a separate user token. The standing owner authorization in the Skill covers only exact-namespace derived-graph mutations and daily reconciliation. It strictly parses `mcporter list memory --schema --json`, bounds each direct call to 30 seconds or less and caps stdout/stderr while the child is running, and holds an exclusive per-namespace lock. A monotonic transaction journal uses `prepared`, `applying`, `verified`, and `complete` phases; snapshot and journal files are mode `0600`, atomically replaced, and file/directory-fsynced. Before every mutation it durably records a dispatch attempt containing tool, transaction ID, namespace, and argument hash. Timeout, disconnect, nonzero exit, or parse failure after dispatch reports `mutation_may_have_occurred` with `reconciliation_required:true`. Every retry re-reads exact backend state and computes only the remaining delta, including after a commit-plus-error response. Verification compares exact names, entity types, observations, owned internal relations, duplicates, foreign inbound links, and representative retrieval. Backend/schema failure records recoverable private state and leaves Markdown untouched. Plan/export remain inert.

After the first verified onboarding, the Skill—not the Harness—uses the first-class Gateway and cron surfaces. `cron-plan` derives an exact deterministic job name from capability plus agent/workspace namespace and returns a schema-valid `cron.add` object. The Gateway generates its ID. The job targets the installing agent in an isolated session with daily cron schedule `0 0 * * *`, explicit registered IANA timezone, and an `agentTurn` message that selects this Skill and performs digest no-op or trusted prepare→run reconciliation. Setup and removal list by exact name, agent ID, and session metadata, then operate only on captured matching server IDs. Missing timezone fails closed without a silent UTC fallback.

Canonical input is limited to 256 regular non-symlink files and 8 MiB total. Empty first-run graphs are valid. Source digest binds ordered source paths and hashes; snapshot hash binds the namespaced snapshot. Secret-like input is rejected without echo by default or deterministically redacted when selected.
