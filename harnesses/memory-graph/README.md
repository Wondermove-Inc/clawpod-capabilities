# Memory Graph Harness

Memory Graph 0.5.0 deterministically parses one agent's recognized core workspace Markdown and canonical memory into a private, namespaced, disposable Memory MCP graph. Canonical Markdown is always read-only.

The fixed core allowlist is exactly `SOUL.md`, `IDENTITY.md`, `USER.md`, `AGENTS.md`, `ORGANIZATIONS.md`, and `WORKFLOW.md`. Root `MEMORY.md`/`memory.md` and direct `memory/*.md` are the only additional inputs. Arbitrary Markdown, secrets, configuration, symlinks, and other agents' workspaces are excluded.

Read [the full contract](../../docs/memory-graph-contract.md) before changing parsing, ownership, reconciliation, or cron behavior. The linked Skill owns immediate autonomous onboarding, standing authorization boundaries, and registration of the daily `0 0 * * *` isolated job in the agent/user's explicit registered IANA timezone.

## Commands

- `inspect`, `plan`, `validate-plan`, `validate-snapshot`, and `cron-plan` are read-only.
- `onboard` is `writeSafe` and reconciles only the exact namespace derived from the explicit agent and workspace identity.
- Larger `diff`, `export-mcp-batch`, and `query-plan` surfaces remain direct CLI operations and are intentionally absent from the Gateway manifest.

Every command emits one stable JSON object. Runtime state belongs in an explicit private state root outside canonical memory and is never part of this package.
