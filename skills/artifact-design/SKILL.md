---
name: artifact-design
description: "Use when a reply's output is substantive and self-contained — a report, plan, spec, memo, comparison, dashboard, one-pager, diagram page, or small interactive tool — and worth reopening, editing, or reusing. Designs it with real typographic hierarchy, palette, and layout, then publishes it as a ClawPod room artifact (markdown or html) through the message artifacts contract. Use Claude Design for multi-artboard canvases, Image Studio for raster images, Video Studio for video."
---

# Artifact Design

Turn a substantive answer into a designed, self-contained ClawPod room artifact and publish it correctly. This is a prose-only Skill: it supplies the decision rule, the design method, and the exact publishing contract. It does not add a command, a renderer, or a network surface — the agent publishes through the runtime's own message-send surface.

Two things must both be true for the work to count as done:

1. The artifact is **designed** — calibrated treatment, real hierarchy, a chosen palette, both color themes when it is HTML.
2. The artifact is **published as an artifact** — carried in the message's structured `artifacts` or `artifact_refs` field. Text markers, fenced blocks, file paths, and `[embed ref=...]` never become artifacts; they render as plain text.

## Prerequisites

- The current runtime exposes artifact fields on outbound messages (ClawPod admin-api `POST /internal/messages`, or the equivalent tool the agent's `tools_md` describes). Read [publishing-contract.md](references/publishing-contract.md) before the first publish.
- The reply is going to a **room message or agent message**. Artifacts are accepted only there.
- No credentials, endpoints, or room identifiers beyond what the runtime already provides. Never invent or hard-code an API base URL or token.

## Procedure

1. **Decide whether this output is an artifact.** Do not wait for the user to say "artifact". Publish one when the output is substantive, self-contained, and worth reopening, editing, downloading, or reusing later: reports, plans, specs, memos, comparisons, decision records, dashboards, one-pagers, reference sheets, diagram pages, small tools. Keep short answers, status lines, clarifying questions, and one-off command output in the message body.
2. **Read the request and calibrate the treatment** (not whether to design). Most artifacts want a utilitarian treatment: polished hierarchy, considered spacing, a proper palette, no giant hero. Reserve the editorial treatment — an opinionated visual identity with one real aesthetic risk — for landing pages, pitches, games, tools, and anything the user will keep or share. When unsure, a well-composed page is never wrong; an over-designed one sometimes is.
3. **Choose the type.** `html` for anything with layout, data tables, charts, diagrams, interaction, or theme-aware color. `markdown` only when the content is genuinely prose-first and its structure is fully expressed by headings, lists, and tables — see [markdown-craft.md](references/markdown-craft.md). Only these two types exist.
4. **Pin the subject and write the design plan** before any code: one concrete subject, its audience, the page's single job; then 4–6 named palette values, 2+ typographic roles, and a one-sentence layout concept. Derive every later color and type decision from that plan. For editorial work, revise any part of the plan that reads like the generic default before building. Full method: [design-fundamentals.md](references/design-fundamentals.md).
5. **Build the content.** For HTML start from [html-skeleton.md](references/html-skeleton.md): a complete, self-contained document, inline CSS and JS only, token-level theming with light and dark palettes, explicit `body` background, no external scripts. Real content throughout, never lorem. Keep the whole document within 200,000 characters including any data URIs.
6. **Name it like a product.** `title` is the artifact's name in the room and the panel: a short, specific noun phrase (typically two to four words, 1–200 chars), no appended explainer after a dash or colon. `identifier` is a stable slug matching `^[A-Za-z0-9][A-Za-z0-9_.-]*$` (1–120 chars); reuse the same identifier when revising the same deliverable so the server files it as the next version, and choose a new identifier for a distinct deliverable.
7. **Run the checklist** in [checklist.md](references/checklist.md): theme scan, cascade and overflow checks, copy pass, payload limits.
8. **Publish through the structured field.** Attach the artifact to the outgoing message exactly as [publishing-contract.md](references/publishing-contract.md) specifies — inline `artifacts` for content you authored in this turn, or save first and attach `artifact_refs` for file outputs. Never send both fields in one message. At most 5 artifacts per message. Do not author a `preview`; the server derives it.
9. **Write the message body from the user's side.** One or two sentences that say what the artifact is and what changed if it is a new version. Do not paste the artifact's content into the body as well.

## Publishing rules that fail closed

- `artifacts` and `artifact_refs` together in one message → the request is rejected. Pick one.
- `type` outside `markdown | html`, an identifier that fails the pattern, an empty or over-long title or content → rejected. Fix the payload; do not downgrade to a text marker.
- `artifact_refs` pointing at an identifier/version that does not exist in this room → rejected. Save first, then reference the returned `identifier` and `version`.
- Saving with `expectedVersion` that no longer matches → `409`. Re-read the current version, merge, and save again; never force a stale overwrite.
- If the runtime surface in this session does not expose artifact fields at all, say so plainly, deliver the content inline as ordinary text, and do not claim an artifact was published.

## Boundaries

- Publishing an artifact to the room is part of replying to that room; it authorizes nothing beyond that. External publication, credential use, or side effects in other systems keep their own approval rules.
- Use `claude-design` for multi-artboard canvases and visually editable design files, `clawpod-image-studio` for raster image generation or editing, `clawpod-video-studio` for video, and `enterprise-newsletter` for release-bound newsletter rendering. This Skill produces the single self-contained page or document that lives in the chat room.
- Honor an existing design system first: the user's stated direction, then the project's tokens or component styles, then this Skill's own choices.

## Verification

Before reporting completion, confirm all of the following from runtime evidence, not intent:

- The send response (or the room's message record) shows the artifact attached with the expected `identifier`, `type`, `title`, and — for a revision — an incremented `version`.
- For the pointer flow, the save response returned the `identifier`/`version` that the message then referenced.
- The HTML stylesheet has no color declared only inside a media or `[data-theme]` block; `body` sets a token background; no element overflows the page horizontally.
- Content length, artifact count, and identifier/title lengths are within the limits in the contract.

## Failure handling

- Validation error on send → read the error, correct the specific field, resend once. If it still fails, report the exact error and the payload shape (never secrets) and stop.
- `409` on save → re-read the latest version, rebase the change, save again with the fresh `expectedVersion`.
- Artifact renders with unreadable text in one theme → a color was defined only behind a media query or theme attribute; move it to the token set and republish under the same identifier.
- Content exceeds 200,000 characters → cut embedded data URIs first (replace raster images with Canvas, inline SVG, or a text reference), then split into at most 5 artifacts per message with distinct identifiers.
