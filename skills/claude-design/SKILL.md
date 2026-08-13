---
name: claude-design
description: Operate Claude Design projects, design systems, exports, sharing, and Claude Code handoff through guarded MCP-first and browser workflows.
---

# Claude Design

Use the paired `claude-design` Harness for deterministic discovery, previews, and handoffs. Prefer the official Claude Design MCP when `/design-login` provisions it and its live schema is available. Use the logged-in browser only for web-only surfaces. Never bind private web endpoints.

Immediately after installation, state that the capability is installed but not connected. Explain that Claude Design uses the user's Claude account/workspace, shared Claude usage limits, existing Claude Code authentication when available, and optional protected `CLAUDE_CODE_OAUTH_TOKEN` injection without persistence. Ask whether to start `/design-login`; do not open login, use credentials, create connector state, or invoke the account before explicit approval. The agent handles CLI/MCP checks and verification; the user handles sign-in, MFA, and consent. Access can be revoked with Claude Code MCP logout/removal and Claude account settings.

1. Run `system.version`, `onboarding.plan`, `onboarding.preflight`, `onboarding.status`, `auth.contract`, `auth.status`, then `mcp.inspect`. Do not claim MCP readiness if its install endpoint or tool schema is absent. `/design-login` and `/design-sync` are Claude Code slash commands, not shell commands.
2. Reuse existing Claude Code authentication. If a setup token is authorized, inject it only as `CLAUDE_CODE_OAUTH_TOKEN` for that process. Never put tokens in argv, config, reports, or artifacts.
3. For project creation/iteration, preserve project ID and exact name. On timeout or browser loss, reopen the existing project and inspect state before retrying. Browser work uses `projects.*.handoff` and the desktop/browser capability, outside the Gateway Harness process.
4. Choose chat for broad generation, comments for contextual collaboration, and direct edit for exact layout/text changes. Confirm revision/readback after every mutation.
5. Preview sharing, destinations, sync, publish/default/admin, and other externally visible effects. Apply only the exact digest with explicit approval. New connectors, public publishing, organization administration, and partner handoff always require separate approval.
6. Exports support HTML bundle, PPTX, and PDF. Verify output path, MIME, byte count, and SHA-256. Warn that HTML is active content. Google Slides requires a connection.
7. For `/design-sync`, approve the repository and direction, inspect git status/diff before and after, and stop on unrelated changes. Never push, deploy, or publish without separate approval.
8. Destructive operations require exact project/system name and approval, then source-of-truth absence verification. Never clean up automatically after ambiguous partial effects.
9. Design-system publish, organization default, delete, role update, and enablement are organization-impacting. Permission propagation can take 15 minutes; refresh and verify. Audit logs are unsupported.
10. Reconcile ambiguity from project lists, ACL readback, exported artifact hashes, git diff, or organization settings. Do not blindly retry.

Read `references/operations.md` for command mapping and exact unsupported limits. Completion requires source-of-truth verification and a limits statement.