---
name: "claude-design"
description: "Use for Claude Design create/edit/QA and link-first deck handoff: deliver the verified project link so the user exports PPTX/PDF themselves, and run native file export only when a file is explicitly requested. Use Image Studio for stills, and compose with Desktop only for native OS dialogs."
---

# Claude Design

Default to the logged-in `https://claude.ai/design` UI through Browser. Use the paired `claude-design` Harness (v0.4.1) for deterministic planning, exact-digest approvals, browser/auth readiness contracts, the layout quality gate, link-handoff verification, and — only when a file is explicitly requested — export verification. MCP is acceleration only after a real read-only tool call succeeds; it is never required. Compose with Desktop only when the workflow leaves the browser DOM for a native OS dialog, or when native-app visual inspection is required; never use Desktop instead of Browser for ordinary Claude Design DOM work.

Immediately after installation, state that the capability is installed and browser-first. Open Claude Design and verify the authenticated Design UI. Reuse the existing browser session. Ask the user only for sign-in, MFA, or provider consent when browser authentication is absent. Do not require MCP endpoint registration, Claude Code OAuth, setup tokens, or CLI work.

## The deliverable is the link, not the file

A finished deck is delivered as a **verified Claude Design link** (project URL + exact `.dc.html` file URL) with a short handoff card that tells the recipient how to export PPTX/PDF/HTML themselves. Exporting from their own account takes seconds and always reflects the latest version; agent-driven native export takes minutes of Browser/Desktop automation, cannot be delivered through room artifacts (which carry only markdown/html text), and is the single largest source of delay and failed delivery. Run the native export path in [native-export.md](references/native-export.md) only when the user explicitly asks for a file, and even then send the link card first.

## Ground the deliverable

1. Before creating or editing, pin the source of truth: target version, canonical commit or document revision, required facts, output names, slide count, and prohibited stale markers. Record them in the tracked task.
2. If the source changes while the design is in progress, stop and re-ground before exporting or handing over. Before delivery, compare the rendered content against the pinned source again. Project creation, prompt acceptance, or a successful generation message is not proof that the deck is current.

## Preflight Claude Design

3. Run `system.version`, `onboarding.plan`, `onboarding.preflight`, `onboarding.status`, `auth.contract`, and `auth.status`.
4. Before submitting a prompt or editing a project, verify from fresh evidence that the browser profile is running and CDP-ready (starting the managed browser is allowed when it is stopped; a browser timeout never authorizes a Gateway restart), the authenticated Design UI is readable, the exact project/file URL opens, and the canvas or thumbnail is actually served, not merely listed.
5. Stale URL waiting, repeated refresh, and duplicate prompt or project creation are prohibited. On a stale or 404 file route, use `projects.reenter.plan` → `projects.reenter.verify` → `projects.file_route.diagnose` for at most two bounded attempts after a fresh project-list read; treat repeated `OmeletteService/GetFile`, thumbnail, or `claudeusercontent` 404s as provider file-serving failures, retry once after a fresh project-list read. After two identical failures, stop blind retries. Preserve the original project. Never create multiple duplicate projects. Browser/CDP failures are never provider failures.

## Brief and prompt

6. Write the brief with the structure rules in [quality-gates.md](references/quality-gates.md) *before* prompting: one message per slide, a title that states the takeaway, a fixed layout family, a diagram grammar (one shape per concept type, one arrow style, a grid), text budgets, and a type scale. A vague prompt produces the misaligned, overflowing, unsystematic decks the quality gate will later reject; the cheapest fix is a precise brief.
7. Before entering a prompt, inspect the target element from a fresh snapshot and run `browser.input.plan`. Standard `input`/`textarea` fields use `fill`; contenteditable targets use `type` only through 600 characters, and one ref-scoped `evaluate` above that. Run `browser.input.verify` against the exact text read back; submit only on exact equality. On a stale ref, take a fresh snapshot, retry once, verify again.

## Edit and approve side effects

8. Choose chat for broad generation, comments for contextual collaboration, and direct edit for exact layout or text changes. Confirm revision/readback per batch of related mutations, not after each one.
9. Preview sharing, comments, handoff, sync, publish/default, admin enablement, and role changes; apply the matching exact digest in the same turn — the digest chain is the consistency mechanism, never a pause for approval.

## Quality gate and revise loop

10. Every deck passes three gates before handoff — **content**, **structure**, **visual** — defined in [quality-gates.md](references/quality-gates.md). The visual gate is deterministic: capture per-slide element geometry either offline from the `.dc.html` export with `scripts/capture_layout.py` (headless Chromium, no login) or live from the canvas with the Browser `evaluate` snippet in that reference, save it as JSON, and run `projects.qa.layout --layout-json <file> --expected-pages N`. It flags text overflow, text escaping its shape, overlaps, off-canvas elements, near-misses in alignment, uneven spacing, fonts below the floor, text density, inconsistent diagram shapes, title drift across slides, and font-size sprawl.
11. If the gate fails, do not hand over and do not ask the user to accept defects. Feed the returned `revision_prompt` (plus the content/structure findings you recorded) into `projects.iterate` on the **same** project, re-capture, and re-run the gate. Run at most three revise rounds; if the deck still fails, hand over the link with the remaining findings listed honestly and offer a re-brief. Never "fix" a defect by exporting a different rendering.
12. Take one screenshot per slide after the gate passes and check the two things geometry cannot see: readability (contrast, line breaks in Korean text, orphaned characters) and meaning (charts labeled, diagrams read in one direction, numbers match the source).

## Hand over the link

13. Run `projects.link.verify` with the project ID, project URL, exact file URL, exact UI filename, expected pages, observed slide count from the fresh canvas read, `--canvas-served true`, the pinned source version, and `--language ko|en`. It fails closed on URL/filename mismatch, slide-count mismatch, or an unserved canvas, and returns a `handoff_card`.
14. Send the card in the room message (or as a markdown artifact through `artifact-design` when the room benefits from a reusable document). Completion is the recipient being able to open the link. If they cannot, run `projects.share.preview/apply` once with organization scope in the same turn — never export files as a workaround for access. Details: [link-handoff.md](references/link-handoff.md).
15. Report the gate results with the link: slides, gate summary (critical/warning counts, revise rounds used), grounded source version, and anything left open.

## File mode (only when explicitly requested)

16. When the user asks for PPTX/PDF/HTML files, first send the link card, then follow [native-export.md](references/native-export.md) exactly: independent bounded export per format, `projects.export.plan` before native PDF, Desktop only for the native GTK Save File dialog, `projects.export.verify` for MIME/bytes/SHA-256/page count, and honest `fallback-rendering` provenance when native export genuinely fails. State plainly where the file is and that room artifacts cannot carry it.

## Continuity and completion

17. If a retry must happen later, create a retry Workboard card with the exact project/file, last verified state, retry step, and stop conditions. Add a cron wake-guard for the due time. On wake, explicitly run Workboard dispatch; never assume a scheduled card self-started. Report only meaningful state changes.
18. Completion requires the quality gate to pass (or its remaining findings to be reported), `projects.link.verify` to succeed, and the link card to be delivered to the requested channel. Project creation, a generation message, a canvas screenshot, or an export click alone is not completion.
19. For code sync, pin repository and direction, inspect git status/diff before and after, and stop on unrelated changes. Push, deploy, publish, and destructive operations proceed with the exact displayed name and digest chained in the same turn, followed by source-of-truth absence verification.
20. Optional MCP: run `mcp.inspect` only for diagnostics. Enable MCP execution only after a real Claude Design tool smoke returns authorized data; `Connected` transport output is not authorization. Claude Code 2.1.229 has a verified provider defect (rejected OAuth `redirect_uri`), so MCP failure must not block browser readiness or trigger repeated OAuth attempts.
21. Design-system publish/default/delete, organization enablement, and role changes are organization-impacting; permission propagation may take 15 minutes. Claude Design audit logs are unsupported.

Read `references/operations.md` for the command mapping, browser reconciliation sources, optional MCP defect notes, and unsupported limits. Completion requires source-of-truth verification and a limits statement.
