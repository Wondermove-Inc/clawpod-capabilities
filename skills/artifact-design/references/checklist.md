# Pre-publish checklist

Run this before saving the artifact. Every item is checkable from the content or the payload; none relies on intent.

## Decision

- [ ] The output is substantial, self-contained, and likely to be reused, edited, downloaded, or reopened — otherwise it belongs in plain `content`.
- [ ] Treatment matches the request: utilitarian by default, editorial only when the user will keep or share the page.
- [ ] Type chosen from the renderer table in choosing-the-type.md: `markdown` for prose, runbooks, records, mermaid diagrams; `html` for designed layout, dense data, inline-SVG charts, a specific identity. Not `html` for interactivity.

## Design plan

- [ ] Subject, audience, and the page's single job are pinned.
- [ ] Palette named as 4–6 hex values; 2+ typographic roles with fallback stacks; a one-sentence layout concept for a ~480 px column.
- [ ] Nothing in the plan is the generic default (cream + serif + terracotta; near-black + acid green; purple-blue gradient hero; Inter/Space Grotesk by reflex; emoji markers; everything centered; rounded cards with accent rails) unless the user asked for it.
- [ ] Any existing project design system was applied before this Skill's own choices.

## HTML build (sandboxed iframe, no scripts)

- [ ] Complete document; **no `<script>`**; nothing depends on JavaScript, `localStorage`, or fetch.
- [ ] Fonts from system stacks, `data:`, or `cdn.jsdelivr.net` only — no Google Fonts link. Images from `https:` or `data:` only.
- [ ] Every color is a token on bare `:root`; the `prefers-color-scheme: dark` block only redefines tokens. **Scan for any color literal that exists only inside `@media`** — it will not apply in the other theme.
- [ ] `body` sets `background: var(--ground)` explicitly; `<meta name="color-scheme" content="light dark">` is present.
- [ ] Single column that works at 320 px and breathes to 670 px; the first screen (70 vh) opens with eyebrow, title, lede — not a tall hero.
- [ ] Wide content (tables, code, SVG) sits inside an `overflow-x: auto` container; nothing forces the page to scroll sideways.
- [ ] `<style>` is at the **end of `<body>`**; `<head>` holds only meta, title, and optional `<link>` fonts, so the 240-character preview is prose.
- [ ] Spacing comes from flex/grid `gap`; no selector pair silently cancels another; headings `text-wrap: balance`; digits in columns use `tabular-nums`.
- [ ] Focus visible; `prefers-reduced-motion` respected; all non-void elements closed; attributes double-quoted.
- [ ] Structural devices (numbers, eyebrows, dividers) encode something true; no decorative numbering.
- [ ] Copy is from the reader's side: active voice, labels say what things are, errors say what to do.

## Markdown build

- [ ] One H1 equal to `title`, then a one-sentence lede (these become the preview).
- [ ] No raw HTML for layout or color; no `data:` images; mermaid blocks fit a ~480 px column.
- [ ] Ticket-like tokens that are not portal tasks are in backticks (avoid `task-123` auto-links).

## Payload

- [ ] `identifier` matches `^[A-Za-z0-9][A-Za-z0-9_.-]*$`, 1–120 chars, slugged from the subject, reused for a revision of the same deliverable.
- [ ] `title` is a product-like name, 1–200 chars, no appended explainer.
- [ ] `type` is exactly `markdown` or `html`.
- [ ] `content` is 1–200,000 characters including data URIs; body built with Python/JSON, not shell interpolation.
- [ ] No `preview` field. `expectedVersion` omitted or `0` for a new identifier; the stored previous version for a revision.
- [ ] `from_agent_id` present on the save request; the agent is a participant of `room_id`.
- [ ] Message carries `artifact_refs` only (never with `artifacts`); at most 5; each `version` is the exact integer from the save response.

## After send

- [ ] Save returned `201` with `artifact.identifier` / `artifact.version`; send returned success.
- [ ] `content` of the message is one or two sentences about what the artifact is and what changed; the artifact is not duplicated into it.
- [ ] WebUI final output is exactly `NO_REPLY`.
