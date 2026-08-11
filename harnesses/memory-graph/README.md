# Memory Graph Harness

Version 0.10.4 extends the metadata-only private JSON output contract to every semantic stage whose full result feeds another stage: extractor input, validation, review queue, approval, build, reconcile, and reconcile verification. Paired `output`/`outputRoot` arguments create a new normalized relative `.json` file atomically at mode 0600 beneath an existing approved non-symlink root; stdout contains only path, exact bytes, SHA-256, and mode. Collisions, mismatches, traversal, escapes, malformed extensions, and symlink roots, parents, or targets fail closed. Omitting both arguments preserves full stdout. Gateway, semantic authority boundaries, canonical memory, MCP dispatch, and no-network behavior are unchanged.

Version 0.9 adds private claim-grounded Entity Proposals to the local read-only assertion ontology commands: `ontology-validate`, `review-queue`, `cq-evaluate`, and `semantic-view`. Fresh, explicitly human-approved proposals may bootstrap `Person`, `Project`, `Decision`, or `Event` assertion endpoints while canonical explicit entities remain higher trust. Closed shapes, content-addressed IDs, deterministic quarantine, inert aliases/identity candidates, temporal precision, direct human-approved causality, and v0.8 read-only migration are enforced. These paths do not call models, networks, MCP, or the live graph and never write canonical files. See `../../artifacts/memory-graph-v0.9-entity-proposal-contract.md`.

Memory Graph 0.9.0 deterministically parses only one agent's direct canonical `memory/*.md` topic files into a private, namespaced, disposable Memory MCP graph. Canonical Markdown is always read-only. It also validates and projects agent-proposed relations into a separate, noncanonical read-only inference overlay.

Only direct regular non-symlink `memory/*.md` files are inputs. Root files (including `MEMORY.md` and every core/context file), nested memory paths (including `.evidence/**` and `.registry/**`), arbitrary Markdown, secrets/configuration, symlinks, and other agents' workspaces are excluded. Legacy owned core document/section graph records are deleted as stale during reconciliation; foreign namespaces remain untouched.

Read [the full contract](../../docs/memory-graph-contract.md) before changing parsing, ownership, reconciliation, or cron behavior. The linked Skill owns immediate autonomous onboarding, standing authorization boundaries, and registration of the daily `0 0 * * *` isolated job in the agent/user's explicit registered IANA timezone.

## Commands

- `inspect`, `plan`, `validate-plan`, `validate-snapshot`, `validate-inference-candidates`, `ontology-validate`, `review-queue`, `cq-evaluate`, `semantic-view`, and `cron-plan` are read-only. Semantic pipeline commands are `writeSafe` because their optional paired output contract writes only new private JSON; without those arguments their prior full-stdout behavior remains read-only. Inference projection may optionally reconcile only its private mode-0600 cache under an explicit `state-root`.
- `onboard` is `writeSafe` and reconciles only the exact namespace derived from the explicit agent and workspace identity.
- Larger `diff`, `export-mcp-batch`, `query-plan`, and `export-visualization` surfaces remain direct CLI operations and are intentionally absent from the Gateway manifest. Query and visualization exclude inference by default and require both `--include-inferred` and a fresh `--overlay`; explicit and inferred relations remain separate in output.

Inference candidate JSON is bounded and strict. The Harness rebuilds the explicit projection, verifies namespace/snapshot/source/claim/path/line hashes, exact typed endpoints, stable IDs, confidence and extractor provenance, and quarantines invalid candidates without copying prose or secret-like values. It performs no model, network, MCP, or graph mutation in validation/projection paths. Cache entries are disposable and invalidated by every source, extractor, configuration, contract, or bundle change.

Every command emits one stable JSON object. Runtime state belongs in an explicit private state root outside canonical memory and is never part of this package.

## v0.10 semantic refinement

Version 0.10 adds a deterministic offline authoring lane: `semantic-extractor-input` selects at most 20 claims from direct regular non-symlink `memory/*.md` files; `semantic-validate-proposals` validates supplied extractor output without model or network access; `semantic-review-queue` and `semantic-approve` keep candidates inert until an exact human review manifest exists; `semantic-build` emits an approved-only snapshot; `semantic-reconcile` validates the supplied Memory MCP view and creates an owned-only, retry-safe operation journal; and `semantic-export-html` writes an escaped, deterministic offline SVG graph canvas with actual entity nodes and assertion edges, relation labels, search/type/claim-cluster filters, pan/zoom, and click details. Canonical explicit, approved private proposal, and candidate/inert records have distinct labels and colors; candidates never masquerade as approved. Aliases, identity candidates, inference overlays, and unapproved candidates never enter reconciliation. `caused` requires direct causal wording and an explicit human approval reason.

The reconcile result is the bounded dispatch contract for the trusted caller. This offline command does not contact Memory MCP itself. The caller must dispatch the exact journaled operations through its schema-validated Memory MCP surface, persist progress after each operation, re-read the backend, and rerun until `idempotent:true`. Canonical Markdown and foreign namespaces are outside its mutation set.

## Deterministic release and rollback

Run `python3 release_inventory.py` from this directory before packaging. Its one JSON object lists every release artifact, byte length, SHA-256 digest, version, and the closed update/rollback rule. Validate every digest before replacing the complete set. Never mix release files. Rollback restores the prior complete inventory, then reruns validation and read-only smoke tests. The command is inert: it does not install, publish, contact a backend, or mutate state.

## Fresh-agent inert semantic example

This example is a data-flow illustration, not an approval. It never authorizes a reviewer, a file write, or Memory MCP dispatch. A fresh agent must prepare each exact Harness command through the trusted runtime and keep all candidates inert until a separately authenticated human review exists.

1. Run `semantic-extractor-input` with the explicit `root`, `agentId`, and `workspaceId`; page until `next_cursor` is null. For trusted private transfer between semantic stages, supply both an existing allowlisted private `outputRoot` outside canonical memory and a fresh relative `.json` `output`; verify stdout path, bytes, SHA-256, and mode before consuming the file.
2. Give only those bounded pages to the external extractor, then pass its JSON to `semantic-validate-proposals` and `semantic-review-queue`. Stop here for review. Neither command approves or writes.
3. After an authenticated human supplies an exact manifest, pass the trusted channel identity separately as `expectedReviewerId` to `semantic-approve`, then run `semantic-build`.
4. Give the snapshot plus a freshly read backend view to `semantic-reconcile`. Its returned operations are an inert plan: never dispatch them automatically. Obtain exact write approval, dispatch only through the schema-validated Memory MCP surface, re-read the backend, and run `semantic-reconcile-verify`.
5. `semantic-export-html` writes a review artifact under its separate contract. Private JSON stage outputs never confer approval or dispatch authority.

Run `python3 semantic_contract_inventory.py` to obtain the deterministic, machine-verifiable command-to-handler, safety, output, effects, error-envelope, and redaction inventory for every manifest `semantic-*` command.
