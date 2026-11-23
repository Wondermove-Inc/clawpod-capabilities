# Choosing between `markdown` and `html`

The table below describes static HTML. For live snapshots, read [live-artifact](live-artifact/guide.md): inline scripts run through the injected SDK; external assets and network remain blocked.

Both types render in the chat room's artifacts panel (`components/v2/chat/artifacts-panel.tsx`, through `components/chat/artifact-document.tsx`), but through very different renderers. Pick by what the renderer can do, then design for it.

## How each type renders (verified)

| | `markdown` | `html` |
|---|---|---|
| Renderer | `react-markdown` + `remark-gfm` + `rehype-sanitize` inside `prose prose-sm dark:prose-invert` | `<iframe sandbox="" srcDoc={content}>` |
| Theme | Follows the portal's light/dark setting automatically | Portal theme does **not** reach the iframe; only the OS `prefers-color-scheme` applies |
| JavaScript | n/a | **Does not run** (sandbox without `allow-scripts`) |
| Storage / network | n/a | No `localStorage`, no same-origin, no fetch; `https:` and `data:` images load; fonts only from system, `data:`, or `cdn.jsdelivr.net` (inherited CSP) |
| Width | The panel opens 320 px wide; readers can drag it to 70% of the window or expand it to the whole room, and phones show it full screen. Text sits in a centered column at most 768 px wide, with 16 px side padding (32 px once the panel is 448 px or wider) | The frame fills the panel's width, with no padding |
| Height | Grows with content; panel scrolls | Fills the panel's height, at least `60dvh`; content scrolls inside the frame |
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

Do **not** choose static `html` for scripted interactivity: nothing scripted will run. CSS-only affordances (`<details>`, `:hover`, `:target`, CSS counters) are all you have.

## Designing for the surface

- Design a **single column at 320 px** first, the width the panel opens at. Readers widen the panel or expand it to the whole room, so in HTML cap the column near 768 px and center it, as the portal does for markdown. No sidebars, no multi-column heroes.
- HTML: at 320 px a tall hero fills the first screen by itself — open with the eyebrow, title, and one-sentence lede.
- HTML: both OS themes must be legible, and the page must also look coherent when the OS is light but the portal is dark (the frame has no border and sits on the portal's background, so an explicit page background is what keeps it looking intentional).
