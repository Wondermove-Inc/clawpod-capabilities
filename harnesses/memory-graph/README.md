# Memory Graph Harness

Version 0.9 adds private claim-grounded Entity Proposals to the local read-only assertion ontology commands: `ontology-validate`, `review-queue`, `cq-evaluate`, and `semantic-view`. Fresh, explicitly human-approved proposals may bootstrap `Person`, `Project`, `Decision`, or `Event` assertion endpoints while canonical explicit entities remain higher trust. Closed shapes, content-addressed IDs, deterministic quarantine, inert aliases/identity candidates, temporal precision, direct human-approved causality, and v0.8 read-only migration are enforced. These paths do not call models, networks, MCP, or the live graph and never write canonical files. See `../../artifacts/memory-graph-v0.9-entity-proposal-contract.md`.

Memory Graph 0.9.0 deterministically parses only one agent's direct canonical `memory/*.md` topic files into a private, namespaced, disposable Memory MCP graph. Canonical Markdown is always read-only. It also validates and projects agent-proposed relations into a separate, noncanonical read-only inference overlay.

Only direct regular non-symlink `memory/*.md` files are inputs. Root files (including `MEMORY.md` and every core/context file), nested memory paths (including `.evidence/**` and `.registry/**`), arbitrary Markdown, secrets/configuration, symlinks, and other agents' workspaces are excluded. Legacy owned core document/section graph records are deleted as stale during reconciliation; foreign namespaces remain untouched.

Read [the full contract](../../docs/memory-graph-contract.md) before changing parsing, ownership, reconciliation, or cron behavior. The linked Skill owns immediate autonomous onboarding, standing authorization boundaries, and registration of the daily `0 0 * * *` isolated job in the agent/user's explicit registered IANA timezone.

## Commands

- `inspect`, `plan`, `validate-plan`, `validate-snapshot`, `validate-inference-candidates`, `project-inference-overlay`, `ontology-validate`, `review-queue`, `cq-evaluate`, `semantic-view`, and `cron-plan` are read-only. The inference projection command may optionally reconcile only its private mode-0600 cache under an explicit `state-root`.
- `onboard` is `writeSafe` and reconciles only the exact namespace derived from the explicit agent and workspace identity.
- Larger `diff`, `export-mcp-batch`, `query-plan`, and `export-visualization` surfaces remain direct CLI operations and are intentionally absent from the Gateway manifest. Query and visualization exclude inference by default and require both `--include-inferred` and a fresh `--overlay`; explicit and inferred relations remain separate in output.

Inference candidate JSON is bounded and strict. The Harness rebuilds the explicit projection, verifies namespace/snapshot/source/claim/path/line hashes, exact typed endpoints, stable IDs, confidence and extractor provenance, and quarantines invalid candidates without copying prose or secret-like values. It performs no model, network, MCP, or graph mutation in validation/projection paths. Cache entries are disposable and invalidated by every source, extractor, configuration, contract, or bundle change.

Every command emits one stable JSON object. Runtime state belongs in an explicit private state root outside canonical memory and is never part of this package.
