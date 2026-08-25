---
name: "claude-design"
description: "Use for Claude Design create/edit/QA/export and project/native export work; use Image Studio for stills, and compose with Desktop only for native OS dialogs."
---

# Claude Design

Default to the logged-in `https://claude.ai/design` UI through Browser. Use the paired `claude-design` Harness for deterministic planning, exact-digest approvals, browser/auth readiness contracts, export verification, and optional MCP diagnostics. MCP is acceleration only after a real read-only tool call succeeds. It is never required for installation, onboarding, or capability readiness. Compose with Desktop only when the workflow leaves the browser DOM for a native OS dialog, or when native-app visual inspection is required; never use Desktop instead of Browser for ordinary Claude Design DOM work.

Immediately after installation, state that the capability is installed and browser-first. Open Claude Design and verify the authenticated Design UI. Reuse the existing browser session. Ask the user only for sign-in, MFA, or provider consent when browser authentication is absent. Do not require MCP endpoint registration, Claude Code OAuth, setup tokens, or CLI work.

## Ground the deliverable

1. Before creating or editing, pin the source of truth: target version, canonical commit or document revision, required facts, output names, page/slide count, and prohibited stale markers. Record them in the tracked task.
2. If the source changes while the design is in progress, stop and re-ground before exporting. Before delivery, compare the rendered/exported content against the pinned source again. Project creation, prompt acceptance, or a successful generation message is not proof that the deck is current.

## Preflight Claude Design

3. Run `system.version`, `onboarding.plan`, `onboarding.preflight`, `onboarding.status`, `auth.contract`, and `auth.status`.
4. Before submitting a prompt or editing a project, verify all of the following from fresh evidence:
   - the browser profile is running and CDP-ready; starting the managed browser is allowed when it is stopped, but a browser timeout never authorizes a Gateway restart;
   - the authenticated Design UI is readable;
   - the exact project/file URL opens;
   - the canvas or thumbnail is actually served, not merely listed in the project index;
   - the download destination is writable and its pre-export file baseline is recorded.
5. Treat repeated `OmeletteService/GetFile`, thumbnail, or `claudeusercontent` 404s as provider file-serving failures. Reopen the same resource and retry once after a fresh project-list read. After two identical failures, stop blind retries. Preserve the original project and artifacts, then either create one clearly named recovery project with a newly grounded brief when the request authorizes creation, or ask for the alternative path. Never create multiple duplicate projects or resubmit the same prompt repeatedly.

## Enter and verify prompts

6. Before entering a prompt, inspect the target element from a fresh snapshot. Run `browser.input.plan` with its ref and editable semantics. Standard `input`/`textarea` fields use `fill`. Contenteditable textboxes use `type` only for prompts of 600 characters or fewer; longer prompts use one ref-scoped `evaluate` action that inserts a text node and dispatches input/change events. Never use repeated `type` calls as a long-input fallback.
7. Run `browser.input.verify` against the exact text read back from the same field before submitting. Length and SHA-256 are supporting evidence; only exact text equality passes. On a stale ref, take a fresh snapshot, redetect by role/name and editable semantics, retry once, and verify again. On timeout or ambiguity, inspect current field content and browser health before retrying.

## Edit and approve side effects

8. Choose chat for broad generation, comments for contextual collaboration, and direct edit for exact layout or text changes. Confirm revision/readback after every mutation.
9. Preview sharing, comments, handoff, sync, publish/default, admin enablement, and role changes. Apply only the matching exact digest with explicit approval. Public sharing, organization administration, connectors, and partner handoff require separate approval.

## QA and native export

10. Before export, verify browser/CDP liveness again, reopen the exact project/file, confirm the canvas renders, and rerun the pinned-version/stale-marker check across all slides. Record a screenshot or marker for every slide/page.
11. Export each format as an independent bounded operation. Record the download-directory baseline, initiate one native export, and verify that exactly one new file appears before starting the next format. A spinner, generation screen, or elapsed wait is not success.
12. For PowerPoint, select the required font option once, wait for a bounded interval, and inspect browser state plus the download directory. If no file appears, run the export diagnosis path and retry once from the same verified project state. Do not repeatedly click export or assume an invisible download.
13. Before native PDF export, run `projects.export.plan` with the active Design URL, exact UI filename, expected page count, and observed slide count. Continue only when the URL-decoded `file` parameter exactly matches a valid `.dc.html` basename and counts match. Use **Share → PDF → Print or Save as PDF**. Reject a one-page iframe/browser print for a multi-page deck. Use Browser through Chrome print preview while DOM/shadow-DOM targets remain available. If the flow opens the native GTK Save File dialog, compose with Desktop to enter the exact output path/name and activate Save, then return to Harness/file verification. Do not use Desktop to click ordinary Claude Design web controls.
14. After every tool error or timeout, keep the export task in the foreground: return to the same active Design file, inspect browser/dialog state, run `projects.export.diagnose`, and continue from the last verified step. Do not switch tasks or use fallback rendering merely because one call failed.
15. Verify every artifact independently: local existence, MIME, bytes, SHA-256, project ID, provenance, slide/page count, exact version markers, forbidden stale markers, and page-by-page visual QA for clipping, overlap, corruption, readability, and distinctness. Use deterministic artifact checks first; compose with Desktop only when visual QA requires rendering in a native viewer rather than Browser or file tooling. Label any genuinely necessary non-native renderer as `fallback-rendering`, never as native Claude Design export. HTML is active content.

## Continuity and completion

16. If a retry must happen later, create a retry Workboard card with the exact project/file, last verified state, retry step, and stop conditions. Add a cron wake-guard for the due time. On wake, explicitly run Workboard dispatch; never assume a scheduled card self-started. Report only meaningful state changes.
17. Completion requires all requested native files to pass verification and be delivered to the requested channel. A successful project creation, generation message, canvas QA, export click, local path, or transport message alone is not completion. Close superseded recovery cards after the final corrective card succeeds.
18. For code sync, approve repository and direction, inspect git status/diff before and after, and stop on unrelated changes. Never push, deploy, or publish without separate approval.
19. Destructive operations require exact displayed name and approval, followed by source-of-truth absence verification. Never retry ambiguous effects blindly.
20. Optional MCP: run `mcp.inspect` only for diagnostics. Enable MCP execution only after a real Claude Design tool smoke returns authorized data. `Connected` transport output is not authorization. Claude Code 2.1.229 has a verified provider defect where its OAuth `redirect_uri` is rejected, so MCP failure must not block browser readiness or trigger repeated OAuth attempts.
21. Design-system publish/default/delete, organization enablement, and role changes are organization-impacting. Permission propagation may take 15 minutes. Claude Design audit logs are unsupported.

Read `references/operations.md` for the command mapping, browser reconciliation sources, optional MCP defect notes, and unsupported limits. Completion requires source-of-truth verification and a limits statement.
