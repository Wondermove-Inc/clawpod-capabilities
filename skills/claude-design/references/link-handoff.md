# Link-first handoff

## Why the link

| | Link handoff | Agent-driven native export |
|---|---|---|
| Time | seconds after the gate passes | minutes: per-format Browser export, download watch, Chrome print preview, GTK dialog via Desktop, file verification |
| Freshness | always the latest version | a snapshot that goes stale on the next edit |
| Delivery | text — fits any room message or markdown artifact | binary — room artifacts carry only markdown/html text, so there is no delivery path |
| Failure surface | link opens or it does not | download baseline, dialog focus, page-count mismatch, file-route 404 recovery |

## Procedure

1. Read the canvas fresh: active URL, exact UI filename, slide count, canvas served.
2. `projects.link.verify --project-id … --project-url … --file-url … --ui-filename … --expected-pages N --observed-slides N --canvas-served true --source-version "<pinned>" --language ko|en [--deliverable file]`
3. Send `data.handoff_card` verbatim in the room message. Add one line with the quality-gate summary.
4. Optional: publish the card plus the per-slide gate table as a markdown artifact through `artifact-design` when the room will reopen it.

## Access

The recipient must be able to open the link with their own Claude account. If they report it does not open: `projects.share.preview` with organization scope → approval → `projects.share.apply` with the unchanged digest → ask them to retry. Do not fall back to exporting files to solve an access problem; fix access.

## What the card contains

Title (from the UI filename), project URL, file URL, slide count, grounded source version, three export routes (Share → Export → PowerPoint; Share → PDF → Print or Save as PDF; Share → Export → HTML), and the access fallback sentence. The Harness renders it in Korean or English; do not hand-edit the URLs.

## Completion

The link opens for the recipient and the gate results were reported. Nothing else — no export, no file, no screenshot — substitutes for that.
