---
name: artifact-design
description: "Use when a reply's output is substantive and self-contained — a report, plan, spec, memo, comparison, dashboard, one-pager, diagram page, or reference sheet — and worth reopening, editing, or reusing. Designs it with real typographic hierarchy, palette, and layout, then publishes it as a ClawPod room artifact (markdown or html) through the save-then-artifact_refs message contract. Use Claude Design for multi-artboard canvases, Image Studio for raster images, Video Studio for video."
---

# Artifact Design

Turn a substantive answer into a designed, self-contained ClawPod room artifact and publish it the way the runtime actually accepts it. This is a prose-only Skill: it supplies the decision rule, the design method, and the verified publishing contract. It adds no command or renderer — the agent publishes through the same `curl` path it already uses for room replies.

Two things must both be true for the work to count as done:

1. The artifact is **designed** for the surface it will render on — a 320–670 px wide panel, HTML in a script-less sandboxed iframe, markdown in the portal's own themed renderer.
2. The artifact is **published as an artifact** — saved with `POST /internal/chat-rooms/:roomId/artifacts`, then attached to the room message as `artifact_refs`. Text markers, fenced blocks, file paths, and `[embed ref=...]` never become artifacts; they render as plain text.

## Prerequisites

- A `[Room: ...]` message to reply to, with a numeric `room_id`, and the runtime-provided `$GATEWAY_TOKEN` and `$AGENT_ID`. Artifacts are accepted only on **agent room messages**; the agent must be a participant of that room.
- Read [publishing-contract.md](references/publishing-contract.md) once per session before the first publish. It records the exact endpoints, limits, and error codes from the admin-api source.
- Never invent or hard-code a different base URL or token. `http://admin-api:3000` and `X-Gateway-Token` come from the room-reply instructions the runtime already gives you.

## Procedure

1. **Decide whether this output is an artifact.** Do not wait for the user to say "artifact". Publish one when the useful output is substantial, self-contained, and likely to be reused, edited, downloaded, or reopened: documents, plans, specs, reports, deliverable tables, comparisons, decision records, dashboards, one-pagers, reference sheets, diagram pages. Keep short answers, status updates, explanations, casual conversation, and anything ambiguous in plain `content`.
2. **Read the request and calibrate the treatment** (not whether to design). Most artifacts want a utilitarian treatment: polished hierarchy, considered spacing, a proper palette, no giant hero. Reserve the editorial treatment — an opinionated visual identity with one real aesthetic risk — for pitches, landing-style pages, and anything the user will keep or share. When unsure, a well-composed page is never wrong; an over-designed one sometimes is.
3. **Choose the type by what each renderer can do** — see [choosing-the-type.md](references/choosing-the-type.md). `markdown` follows the portal theme automatically, renders GFM tables, task lists, and ```mermaid diagrams, and is the right default for prose, runbooks, decision records, and most diagrams. `html` gives full typographic and color control but runs with **no JavaScript**, only OS-level dark mode, and a narrow fixed-height frame; choose it for designed layouts, data-dense tables, custom charts drawn as inline SVG, and anything with a specific visual identity. Only these two types exist.
4. **Pin the subject and write the design plan** before any code: one concrete subject, its audience, the page's single job; then 4–6 named palette values, 2+ typographic roles with fallback stacks, and a one-sentence layout concept for a ~480 px column. Derive every later decision from that plan. For editorial work, revise any part that reads like the generic default before building. Full method: [design-fundamentals.md](references/design-fundamentals.md).
5. **Build the content.** HTML starts from [html-skeleton.md](references/html-skeleton.md): a complete self-contained document, single-column mobile-first layout, tokens on `:root` plus a `prefers-color-scheme: dark` override, explicit `body` background, `<style>` placed at the **end of `<body>`** so the card preview shows prose instead of CSS, no `<script>` (it will not run), fonts from system stacks or `cdn.jsdelivr.net` only. Markdown follows [markdown-craft.md](references/markdown-craft.md). Real content throughout, never lorem. Stay within 200,000 characters including data URIs.
6. **Name it like a product.** `title` is the artifact's name on the card and panel: a short, specific noun phrase (typically two to four words, 1–200 chars), no appended explainer after a dash or colon. `identifier` is a stable slug matching `^[A-Za-z0-9][A-Za-z0-9_.-]*$` (1–120 chars), slugged from the subject; reuse it for revisions of the same deliverable and choose a new one for a distinct deliverable.
7. **Run the checklist** in [checklist.md](references/checklist.md): renderer constraints, theme scan, overflow, preview text, payload limits.
8. **Save, then attach.** Write the content to a workspace file, `POST` it to `/internal/chat-rooms/$ROOM_ID/artifacts` with `from_agent_id`, read `artifact.version` from the `201` response, and send the room message with `artifact_refs: [{identifier, version}]` and a one- or two-sentence `content`. Exact commands: [publishing-contract.md](references/publishing-contract.md). Worked payloads, including revisions and the interactive-request case: [examples.md](references/examples.md). Never send `artifacts` and `artifact_refs` in the same message; at most 5 refs per message. Do not author a `preview`.
9. **End the turn correctly.** After the curl send, the WebUI output is exactly `NO_REPLY`. Never describe or paste the artifact in the WebUI final text, and never claim it is ready there.

## Publishing rules that fail closed

- `artifacts` and `artifact_refs` together → `400`. Use `artifact_refs`.
- `type` outside `markdown | html`, identifier failing the pattern, empty or over-long title/content, more than 5 items → `400` validation error. Fix the payload; never fall back to a text marker.
- `artifact_refs` pointing at an identifier/version that does not exist **in this room** → `404`, and the whole message is rejected.
- Save with a non-zero `expectedVersion` that no longer matches → `409` with `latestVersion`. Re-read, merge, save again with the fresh version. Omit `expectedVersion` (or send `0`) for the first save of a new identifier.
- Saving content identical to the latest version (same type, title, content) returns the existing version without creating a new one — the response `version` is still the one to reference.
- Agent not a room participant → `403`. Webhook/tasks system senders cannot carry artifacts.
- If the room-reply curl path is not available in this session, say so plainly, deliver the content as ordinary text, and do not claim an artifact was published.

## Boundaries

- Publishing an artifact to a room is part of replying to that room; it authorizes nothing else. External publication, credential use, or side effects in other systems keep their own approval rules.
- Use `claude-design` for multi-artboard canvases and visually editable design files, `clawpod-image-studio` for raster image generation or editing, `clawpod-video-studio` for video, and `enterprise-newsletter` for release-bound newsletter rendering. This Skill produces the single self-contained page or document that lives in the chat room.
- Honor an existing design system first: the user's stated direction, then the project's tokens or component styles, then this Skill's own choices.

## Verification

Before ending the turn, confirm from runtime evidence, not intent:

- The save response was `201` and returned `artifact.identifier` and `artifact.version`; for a revision the version increased (or stayed equal because the content was unchanged).
- The message send succeeded with `artifact_refs` carrying exactly that identifier and version.
- HTML: no `<script>` relied on; every color is defined on `:root` and only redefined under `prefers-color-scheme: dark`; `body` sets a token background; nothing forces horizontal scroll at 320 px; `<style>` sits at the end of `<body>`.
- Lengths and counts are within the contract; the WebUI final output is `NO_REPLY`.

## Failure handling

- `400` on save or send → read the error text, correct the named field, resend once. If it fails again, report the exact error and payload shape (never the token) and stop.
- `404` on send → the ref does not match a saved version in this room. Re-read the save response; if lost, `GET /internal/chat-rooms/$ROOM_ID/artifacts/<identifier>?from_agent_id=$AGENT_ID` returns the current version.
- `409` on save → `GET` the current version, rebase the change, save again with `expectedVersion` = that version.
- Artifact text unreadable in one theme → a color exists only inside the dark media query, or `body` has no background; fix in tokens and republish under the same identifier.
- Card preview shows CSS → `<style>` is above the first prose; move it to the end of `<body>`.
- Interactive behaviour missing → the iframe is sandboxed without scripts; rebuild the behaviour as static content or CSS-only (`<details>`, `:target`, `:hover`), or switch to markdown.
- Content over 200,000 characters → remove embedded raster data URIs first (use inline SVG or an `https:` image URL), then split by section into at most five artifacts with distinct identifiers.
