---
name: claude-design
description: Create, edit, present, export, and verify slides, documents, UI mockups, wireframes, prototypes, design systems, templates, and visual artifacts with Claude Design; use its logged-in browser by default and optional smoke-verified MCP.
---

# Claude Design

Default to the logged-in `https://claude.ai/design` UI through the desktop/browser capability. Use the paired `claude-design` Harness for deterministic planning, exact-digest approvals, browser/auth readiness contracts, export verification, and optional MCP diagnostics. MCP is acceleration only after a real read-only tool call succeeds. It is never required for installation, onboarding, or capability readiness.

Immediately after installation, state that the capability is installed and browser-first. Open Claude Design and verify the authenticated Design UI. Reuse the existing browser session. Ask the user only for sign-in, MFA, or provider consent when browser authentication is absent. Do not require MCP endpoint registration, Claude Code OAuth, setup tokens, or CLI work.

1. Run `system.version`, `onboarding.plan`, `onboarding.preflight`, `onboarding.status`, `auth.contract`, and `auth.status`. Then open Claude Design with the desktop/browser capability and verify the Design UI is readable. Browser authentication, not MCP transport state, determines provider readiness.
2. Use the browser for projects, design systems, templates, sharing, administration, destinations, presentation, and exports. Preserve IDs and exact names. After browser loss or timeout, reopen the existing resource and inspect before retrying.
3. Choose chat for broad generation, comments for contextual collaboration, and direct edit for exact layout or text changes. Confirm revision/readback after every mutation.
4. Preview sharing, comments, handoff, sync, publish/default, admin enablement, and role changes. Apply only the matching exact digest with explicit approval. Public sharing, organization administration, connectors, and partner handoff require separate approval.
5. Export HTML, PPTX, or PDF in the browser, then run `projects.export.verify` and verify path, MIME, byte count, and SHA-256. Treat HTML as active content.
6. For code sync, approve repository and direction, inspect git status/diff before and after, and stop on unrelated changes. Never push, deploy, or publish without separate approval.
7. Destructive operations require exact displayed name and approval, followed by source-of-truth absence verification. Never retry ambiguous effects blindly.
8. Optional MCP: run `mcp.inspect` only for diagnostics. Enable MCP execution only after a real Claude Design tool smoke returns authorized data. `Connected` transport output is not authorization. Claude Code 2.1.229 has a verified provider defect where its OAuth `redirect_uri` is rejected, so MCP failure must not block browser readiness or trigger repeated OAuth attempts.
9. Design-system publish/default/delete, organization enablement, and role changes are organization-impacting. Permission propagation may take 15 minutes. Claude Design audit logs are unsupported.

Read `references/operations.md` for the 56-command mapping, browser reconciliation sources, optional MCP defect notes, and unsupported limits. Completion requires source-of-truth verification and a limits statement.
