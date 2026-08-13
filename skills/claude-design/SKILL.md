---
name: claude-design
description: Operate Claude Design projects, design systems, exports, sharing, and Claude Code handoff through guarded MCP-first and browser workflows.
---

# Claude Design

Use the paired `claude-design` Harness for deterministic discovery, previews, and handoffs. Prefer the official Claude Design MCP when `/design-login` provisions it and its live schema is available. Use the logged-in browser only for web-only surfaces. Never bind private web endpoints.

Immediately after installation, state that the capability is installed but not connected. Explain that Claude Design uses the user's Claude account/workspace, shared Claude usage limits, existing Claude Code authentication when available, and optional protected `CLAUDE_CODE_OAUTH_TOKEN` injection without persistence. Ask once whether to connect now; this approval covers the bounded account-authentication and official MCP onboarding workflow, not later project mutations or external sharing. Do not ask the user to run CLI commands, enter an endpoint, edit MCP configuration, inspect schema, or perform retries. The agent handles every automatable step. The user handles only otherwise-unavailable sign-in, MFA, consent, or credential authorization. Access can be revoked with Claude Code MCP logout/removal and Claude account settings.

1. Run `system.version`, `onboarding.plan`, `onboarding.preflight`, `onboarding.status`, `auth.contract`, `auth.status`, then `mcp.inspect`. After connection approval, automatically reuse existing Claude Code authentication and idempotently register the official user-scope MCP as `claude-design` at `https://api.anthropic.com/v1/design/mcp`; never ask the user to copy or run the command. Verify with `claude mcp get claude-design` and `claude mcp list`, discover the live tool schema, run a bounded read-only smoke test, and report `CONNECTED`, `DEGRADED`, or `BLOCKED` with exact evidence. Do not claim readiness from configuration alone.
2. If existing authentication is absent, start the bounded login flow and ask the user only for the irreducible browser sign-in, MFA, or consent step. If an authorized setup token is available, inject it only as `CLAUDE_CODE_OAUTH_TOKEN` for the process and continue automatically. Never put tokens in argv, config, prompts, reports, or artifacts. `/design-login` and `/design-sync` are Claude Code slash commands, not shell commands; use `claude mcp login claude-design` when the installed CLI exposes a noninteractive MCP login path.
3. For project creation/iteration, preserve project ID and exact name. On timeout or browser loss, reopen the existing project and inspect state before retrying. Browser work uses `projects.*.handoff` and the desktop/browser capability, outside the Gateway Harness process.
4. Choose chat for broad generation, comments for contextual collaboration, and direct edit for exact layout/text changes. Confirm revision/readback after every mutation.
5. Preview sharing, destinations, sync, publish/default/admin, and other externally visible effects. Apply only the exact digest with explicit approval. New connectors, public publishing, organization administration, and partner handoff always require separate approval.
6. Exports support HTML bundle, PPTX, and PDF. Verify output path, MIME, byte count, and SHA-256. Warn that HTML is active content. Google Slides requires a connection.
7. For `/design-sync`, approve the repository and direction, inspect git status/diff before and after, and stop on unrelated changes. Never push, deploy, or publish without separate approval.
8. Destructive operations require exact project/system name and approval, then source-of-truth absence verification. Never clean up automatically after ambiguous partial effects.
9. Design-system publish, organization default, delete, role update, and enablement are organization-impacting. Permission propagation can take 15 minutes; refresh and verify. Audit logs are unsupported.
10. Reconcile ambiguity from project lists, ACL readback, exported artifact hashes, git diff, or organization settings. Do not blindly retry.

Read `references/operations.md` for command mapping and exact unsupported limits. Completion requires source-of-truth verification and a limits statement.