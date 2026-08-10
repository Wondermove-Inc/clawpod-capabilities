# Memory Graph Harness

Version 0.8 adds local read-only assertion ontology commands: `ontology-validate`, `review-queue`, `cq-evaluate`, and `semantic-view`. They validate provenance-bearing approved assertions with closed shapes, keep identity and extraction candidates inert, require human-approved direct causality, preserve temporal precision, and emit semantic-first locator-only output. They do not call models, networks, MCP, or the live graph. See `../../artifacts/memory-graph-v0.8-assertion-ontology-contract.md`.

Memory Graph 0.8.0 deterministically parses one agent's recognized core workspace Markdown and canonical memory into a private, namespaced, disposable Memory MCP graph. Canonical Markdown is always read-only. It also validates and projects agent-proposed relations into a separate, noncanonical read-only inference overlay.

The fixed core allowlist is exactly `SOUL.md`, `IDENTITY.md`, `USER.md`, `AGENTS.md`, `ORGANIZATIONS.md`, and `WORKFLOW.md`. Root `MEMORY.md`/`memory.md` and direct `memory/*.md` are the only additional inputs. Arbitrary Markdown, secrets, configuration, symlinks, and other agents' workspaces are excluded.

Read [the full contract](../../docs/memory-graph-contract.md) before changing parsing, ownership, reconciliation, or cron behavior. The linked Skill owns immediate autonomous onboarding, standing authorization boundaries, and registration of the daily `0 0 * * *` isolated job in the agent/user's explicit registered IANA timezone.

## Commands

- `inspect`, `plan`, `validate-plan`, `validate-snapshot`, `validate-inference-candidates`, `project-inference-overlay`, `ontology-validate`, `review-queue`, `cq-evaluate`, `semantic-view`, and `cron-plan` are read-only. The inference projection command may optionally reconcile only its private mode-0600 cache under an explicit `state-root`.
- `onboard` is `writeSafe` and reconciles only the exact namespace derived from the explicit agent and workspace identity.
- Larger `diff`, `export-mcp-batch`, `query-plan`, and `export-visualization` surfaces remain direct CLI operations and are intentionally absent from the Gateway manifest. Query and visualization exclude inference by default and require both `--include-inferred` and a fresh `--overlay`; explicit and inferred relations remain separate in output.

Inference candidate JSON is bounded and strict. The Harness rebuilds the explicit projection, verifies namespace/snapshot/source/claim/path/line hashes, exact typed endpoints, stable IDs, confidence and extractor provenance, and quarantines invalid candidates without copying prose or secret-like values. It performs no model, network, MCP, or graph mutation in validation/projection paths. Cache entries are disposable and invalidated by every source, extractor, configuration, contract, or bundle change.

Every command emits one stable JSON object. Runtime state belongs in an explicit private state root outside canonical memory and is never part of this package.
