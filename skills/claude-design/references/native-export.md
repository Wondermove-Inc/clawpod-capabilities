# Native file export (opt-in file mode)

Run this only when the user explicitly asked for PPTX, PDF, or HTML files, and only after the link card has been sent. This path is slow by construction (Browser export per format, download-directory watching, Chrome print preview, a native GTK Save File dialog through Desktop, and file verification), and room artifacts cannot carry the binary result — say where the file is on disk and how it will reach the user.

## Before export

- Verify browser/CDP liveness again, reopen the exact project/file, confirm the canvas renders, and rerun the pinned-version/stale-marker check across all slides. Record a screenshot or marker for every slide/page.
- Record the download-directory baseline so that exactly one new file per export can be verified.

## Per-format export

- Export each format as an independent bounded operation. Record the download-directory baseline, initiate one native export, and verify that exactly one new file appears before starting the next format. A spinner, generation screen, or elapsed wait is not success.
- For PowerPoint, select the required font option once, wait for a bounded interval, and inspect browser state plus the download directory. If no file appears, run the export diagnosis path and retry once from the same verified project state. Do not repeatedly click export or assume an invisible download.
- Before native PDF export, run `projects.export.plan` with the active Design URL, exact UI filename, expected page count, and observed slide count. Continue only when the URL-decoded `file` parameter exactly matches a valid `.dc.html` basename and counts match. Use **Share → PDF → Print or Save as PDF**. Reject a one-page iframe/browser print for a multi-page deck. Use Browser through Chrome print preview while DOM/shadow-DOM targets remain available. If the flow opens the native GTK Save File dialog, compose with Desktop to enter the exact output path/name and activate Save, then return to Harness/file verification. Do not use Desktop to click ordinary Claude Design web controls.
- After every tool error or timeout, keep the export task in the foreground: return to the same active Design file, inspect browser/dialog state, run `projects.export.diagnose`, and continue from the last verified step. Do not switch tasks or use fallback rendering merely because one call failed.

## Verify

- `projects.export.verify --project-id … --format … --output-path … --provenance native-claude-design --expected-pages N --qa-pages 1,2,…` for every file: local existence, MIME, bytes, SHA-256, project ID, provenance, exact page/slide count, and page-by-page visual QA for clipping, overlap, corruption, readability, and distinctness; compose with Desktop only when visual QA requires rendering in a native viewer rather than Browser or file tooling.
- After a stale-route recovery, continue from the last verification checkpoint into two full slide reviews and independent native PPTX/PDF verification with page-by-page reflow comparison (`--review-pass-1/2`, `--render-pages`, `--reflow-pages`). Do not treat route recovery as completion.
- Label any genuinely necessary non-native renderer as `fallback-rendering`, never as native Claude Design export. HTML is active content.

## Deliver

State the local path, size, SHA-256, and page count, and that the file must travel through a channel that accepts binaries; the link card already lets the user export the same file themselves in seconds.
