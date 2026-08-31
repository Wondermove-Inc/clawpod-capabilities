# Working with OpenDesign

## The division of labor

| Who | Does |
|---|---|
| The agent | Authors the HTML (design craft, content, QA), names things, decides when to publish |
| OpenDesign daemon | Stores project files, mints sandboxed preview URLs, exports HTML/ZIP, imports Claude Design zips |
| The user | Opens the preview link; exports PDF via browser print when needed |

OpenDesign's own chat/agent loop (`/api/chat`) is deliberately not used: authoring stays with this agent so the same craft and QA gates apply everywhere.

## Authoring rules

- Self-contained HTML: inline CSS, no external scripts; assets uploaded alongside and referenced by relative name. The preview iframe is sandboxed (`allow-scripts allow-forms`, self/data/blob sources), so external CDNs will not load.
- Decks: one `section.slide` per slide, fixed slide geometry (e.g. 1920×1080), page numbers, one message per slide. Run the `claude-design` Harness layout gate (`projects.qa.layout` + its offline capture script) and fix findings before uploading — the capture recognizes `section.slide` directly.
- Name files as the user would (`q3-review.html`, not `output.html`); the file name appears in the preview URL.

## Worked calls

```
# create + upload + link
open-design projects.create --state-root R --name "Q3 실적 리뷰 덱" --kind deck
open-design files.put --state-root R --project-id P --path /workspace/q3-review.html
open-design preview.link --state-root R --project-id P --file q3-review.html
# → data.webUrl: https://<web host>/api/projects/P/preview/<scope>/q3-review.html  (사람용; agent-api 접두사 없음, API 토큰 없이 열림)
# → data.apiUrl: https://<web host>/agent-api/api/projects/...                    (에이전트 검증용)

# revision: edit locally, re-gate, re-upload the same name, re-mint the link
open-design files.put --state-root R --project-id P --path /workspace/q3-review.html
open-design preview.link --state-root R --project-id P --file q3-review.html

# file deliverables on request
open-design export.html    --state-root R --project-id P --file-name q3-review.html --out-path /workspace/out/q3-review.html
open-design export.archive --state-root R --project-id P --out-path /workspace/out/q3-review.zip
open-design import.claude-design --state-root R --path "/workspace/Claude Design export.zip"
```

## Export reality on the verified deployment (v0.20.3)

- Available server-side: standalone HTML, ZIP archive, export manifest.
- Not available: PDF (`/export/pdf` is desktop-runtime only → HTTP 501) and PPTX (`slideRenderer:false`). Offer: preview link + browser print for PDF, or `import.claude-design`/claude.ai for richer export paths.

## Delivery

Lead with the preview link and one or two sentences (what it is, what changed). The link opens without the API token for anyone who can reach the server network — inside the org that is the point; outside, export a file instead. When the room benefits from a durable card, publish the link plus a slide/QA summary through `artifact-design`.
