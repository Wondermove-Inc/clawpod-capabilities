# Pre-publish checklist

Run this before attaching the artifact. Every item is checkable from the content or the payload; none relies on intent.

## Decision

- [ ] The output is substantive, self-contained, and worth reopening or reusing — otherwise it belongs in the message body.
- [ ] Treatment matches the request: utilitarian by default, editorial only when the user will keep or share the page.
- [ ] Type chosen deliberately: `html` for layout, data, color, interaction; `markdown` only for prose-first structure.

## Design plan

- [ ] Subject, audience, and the page's single job are pinned.
- [ ] Palette named as 4–6 hex values; 2+ typographic roles with fallback stacks; a one-sentence layout concept.
- [ ] Nothing in the plan is the generic default (cream + serif + terracotta; near-black + acid green; purple-blue gradient hero; Inter/Space Grotesk by reflex; emoji markers; everything centered; rounded cards with accent rails) unless the user asked for it.
- [ ] Any existing project design system was applied before this Skill's own choices.

## HTML build

- [ ] Complete document, inline CSS/JS only, no external scripts or remote assets; a Google Fonts link (if any) has a real fallback stack.
- [ ] Every color is defined as a token on bare `:root`; dark blocks only redefine tokens. **Scan the stylesheet for any color literal that exists only inside `@media` or `[data-theme]`** — that bug produces one theme's text on the other theme's ground.
- [ ] `body` sets `background: var(--ground)` explicitly.
- [ ] Wide content (tables, code, diagrams) sits inside an `overflow-x: auto` container; nothing forces the page to scroll sideways.
- [ ] Spacing comes from flex/grid `gap`, not stacked margins; no selector pair silently cancels another.
- [ ] Headings `text-wrap: balance`; running text near 65ch; digits in columns use `tabular-nums`.
- [ ] Focus is visible; `prefers-reduced-motion` is respected; all non-void elements are closed; attributes are double-quoted.
- [ ] Structural devices (numbers, eyebrows, dividers) encode something true; no decorative numbering.
- [ ] Copy is from the reader's side: active voice, controls say what happens, errors say what to do.
- [ ] The first visible text at the top of `<body>` reads as a sentence — it becomes the 240-character card preview.

## Payload

- [ ] `identifier` matches `^[A-Za-z0-9][A-Za-z0-9_.-]*$`, 1–120 chars, slugged from the subject, and reused for a revision of the same deliverable.
- [ ] `title` is a product-like name, 1–200 chars, no appended explainer.
- [ ] `type` is exactly `markdown` or `html`.
- [ ] `content` is 1–200,000 characters including data URIs.
- [ ] No `preview` field; no `version` on an inline publish.
- [ ] At most 5 artifacts in the message; `artifacts` **or** `artifact_refs`, never both.
- [ ] For `artifact_refs`: the save response's `identifier`/`version` are what the message references, in the same room.

## After send

- [ ] The send response or room record shows the artifact attached with the expected identifier and (for revisions) an incremented version.
- [ ] The message body is one or two sentences about what the artifact is and what changed — the artifact's content is not duplicated into the body.
