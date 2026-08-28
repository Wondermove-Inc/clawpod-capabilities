# Choosing between `markdown` and `html`

Both types render inside the same side panel (`generic-artifact-panel.tsx`), but through very different renderers. Pick by what the renderer can do, then design for it.

## How each type renders (verified)

| | `markdown` | `html` |
|---|---|---|
| Renderer | `react-markdown` + `remark-gfm` + `rehype-sanitize` inside `prose prose-sm dark:prose-invert` | `<iframe sandbox="" srcDoc={content}>` |
| Theme | Follows the portal's light/dark setting automatically | Portal theme does **not** reach the iframe; only the OS `prefers-color-scheme` applies |
| JavaScript | n/a | **Does not run** (sandbox without `allow-scripts`) |
| Storage / network | n/a | No `localStorage`, no same-origin, no fetch; `https:` and `data:` images load; fonts only from system, `data:`, or `cdn.jsdelivr.net` (inherited CSP) |
| Width | Panel width: 320 px – 60 vw (default 480); workspace mode column ≤ 670 px | Same, minus frame borders |
| Height | Grows with content; panel scrolls | Fixed `70vh`; content scrolls inside the frame |
| Tables | GFM tables | Anything you style |
| Diagrams | ```` ```mermaid ```` blocks render to SVG (strict security level) | Inline SVG you author; no mermaid |
| Raw HTML in content | Stripped by sanitizer (`<script>`, `on*`, `javascript:` blocked; only default-schema tags/attrs survive) | Full document |
| Images | `https:` URLs via `![alt](url)`; `data:` URIs are dropped | `https:` and `data:` |
| Task refs | `task-123` / `#back-45` patterns are auto-linked to the task board — avoid accidental matches | none |
| Code blocks | Copy button added automatically | Style your own |
| Copy / download | Copy markdown or plain text; download `.md` | Copy HTML or plain text; download `.html` |

## Decision

Choose **`markdown`** when:

- The content is prose-first: memos, decision records, runbooks, meeting notes, reference sheets, plans with a few tables.
- A diagram is the point and mermaid can draw it (flowchart, sequence, state, ER, Gantt, class, git graph, pie). It will match the portal theme for free.
- You want the document to look native to the portal and be editable by the reader after download.

Choose **`html`** when:

- The layout needs more than one column, cards, or a designed hierarchy that markdown cannot express.
- Data is dense enough to need custom table styling, alignment, or state encoding (pills, severity stripes).
- A chart or diagram must be precise and mermaid cannot draw it — author it as inline SVG.
- A specific visual identity was requested.

Do **not** choose `html` for interactivity: nothing scripted will run. CSS-only affordances (`<details>`, `:hover`, `:target`, CSS counters) are all you have.

## Designing for the surface

- Design a **single column at ~480 px** first; let it breathe up to 670 px. No sidebars, no multi-column heroes.
- HTML: the frame is 70 vh tall, so the first screen is short — open with the eyebrow, title, and one-sentence lede, not a tall hero.
- HTML: both OS themes must be legible, and the page must also look coherent when the OS is light but the portal is dark (the frame has its own border, so an explicit page background is what keeps it looking intentional).
