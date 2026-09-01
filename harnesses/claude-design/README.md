# Claude Design Harness

Deterministic browser-first guardrails for Claude Design onboarding, auth/browser readiness, exact short/long prompt input, projects, sharing, the layout quality gate, link-first handoff, opt-in native exports, design systems, templates, code sync, destinations, and administration. Version 0.4.2 (calibrated on a real export) adds `projects.qa.layout` and `projects.link.verify`; the surface is now 66 commands.

Provider execution defaults to the logged-in `https://claude.ai/design` UI through the desktop/browser capability. The Harness plans actions, emits exact browser handoffs and reconciliation sources, gates effects with SHA-256 digests, and verifies exported artifacts. It never fakes provider success or inspects browser credentials.

## Deliverable: link first, files on request

`projects.link.verify` validates the exact project/file route (https://claude.ai/design URLs that reference the same project ID, a URL-decoded `file` parameter equal to the active `.dc.html` filename, observed slide count equal to the expected count, canvas served) and renders a Korean or English `handoff_card` with the project link, file link, slide count, grounded source version, and the three self-service export routes. Completion is the recipient opening the link. Native PPTX/PDF export (`projects.export.plan/diagnose/verify`) remains available for explicit file requests only; room artifacts cannot carry binaries.

## Quality gate

`projects.qa.layout --layout-json <capture> --expected-pages N` evaluates per-slide element geometry captured from the canvas (bbox, font size, scroll/client sizes, parent, shape kind) and fails closed with `QA_FAILED` on any critical finding: `TEXT_OVERFLOW`, `TEXT_OUTSIDE_SHAPE`, `OVERLAP`, `OFF_CANVAS`, `PAGE_COUNT_MISMATCH`. Warnings cover `MISALIGNED_EDGE` (almost-aligned siblings), `UNEVEN_SPACING`, `FONT_TOO_SMALL`, `TEXT_DENSITY`, `INCONSISTENT_SHAPES`, `TITLE_DRIFT`, `FONT_SIZE_SPRAWL`, `EMPTY_SLIDE`; `--strict` makes them blocking. Thresholds: `--min-font-px 14 --tolerance-px 4 --max-words 90 --overlap-ratio 0.15 --max-font-sizes 8`. Alignment and spacing rules compare only peer elements (same kind/tag/class, similar font size) outside diagrams and accept centered pairs; overflow is a defect only when the element clips; overlaps ignore DOM ancestors and inline children. `scripts/capture_layout.py` produces the layout JSON offline from a `.dc.html` export through headless Chromium (local binary or `--docker-image`). The response includes `revision_prompt`, one instruction naming every defect per slide, meant to be pasted into `projects.iterate` for a bounded revise loop.

## Start

Run `onboarding.plan`, `onboarding.preflight`, `onboarding.status`, `auth.contract`, and `auth.status`, then verify the authenticated Design UI with desktop/browser. Reuse an existing session. The user handles only missing sign-in, MFA, or provider consent. MCP endpoint registration, Claude Code OAuth, setup tokens, and user-run CLI commands are not onboarding requirements.

## Optional MCP

`mcp.inspect` is bounded diagnostics. MCP is usable only after a real read-only Claude Design tool smoke returns authorized data. Transport `Connected` does not prove authorization. Claude Code 2.1.229 has a verified interoperability defect where its OAuth `redirect_uri` is rejected by the provider. This defect does not degrade browser readiness and must not trigger repeated OAuth attempts.

## Safety and verification

Externally visible and organization effects use `*.preview` then `*.apply` with the exact effect digest and `--approve`. Deletes require exact name and approval. Browser actions must be reconciled against provider state. Native PDF export begins with `projects.export.plan`, which requires an exact active `.dc.html` URL/UI filename match and matching expected/observed counts, then uses Share → PDF → Print or Save as PDF. Reject one-page iframe prints for multi-page decks. After tool failures, keep the export foregrounded, return to the same file, inspect state, run `projects.export.diagnose`, and resume from the last verified step. `projects.export.verify` requires artifact metadata, explicit native or fallback provenance, exact PDF page count, and page-by-page visual QA. HTML is active content.

For prompt entry, use `browser.input.plan` with a fresh element ref and its observed tag/role/contenteditable state. Standard fields use `fill`; contenteditables use `type` through 600 characters and a single safe text-node `evaluate` insertion above that threshold. Run `browser.input.verify` on exact readback before submit. `browser.input.diagnose` distinguishes stale refs and action timeouts without treating a timeout as permission to restart the Gateway.

See `command_contracts.json`, the Skill operations reference, and `TEST.md`.

## File-route recovery

`projects.reenter.plan`, `projects.reenter.verify`, and `projects.file_route.diagnose` are pure JSON planning/evidence commands. They do not click Browser or execute provider work. A provider failure is gated on two bounded fresh-list attempts against the exact same generated-result thumbnail; Browser/CDP failure remains distinct.
