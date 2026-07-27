---
name: "clawpod-ocr"
description: "Extract Korean/English text locally, create enterprise comparison DOCX reports, and optionally use guarded Ollama review."
---

# ClawPod OCR

Use the linked `clawpod-ocr` Harness. Treat the Skill and Harness as one installation unit with the canonical name `clawpod-ocr` and title **ClawPod OCR**. The Harness owns files, OCR processes, jobs, limits, provenance, comparison reports, and correction state.

## Route first

Use the **fast local image path** when the input is one PNG/JPEG/PPM/PGM image, the user needs immediate text, no special layout or remote review is requested, and local onboarding is already verified. Use the standard workflow for PDFs, multi-page inputs, detached work, exports, recovery, or Ollama review.

## Fast local image path

1. Call `ocr.quick` once through Harness `prepare → run` with bounded input root, relative image path, language, owner, and timeout.
2. Reuse verified engine state. Do not repeat onboarding for every image.
3. Return text immediately, but preserve the completed job/result so it can feed `report.create`.
4. Skip Workboard for a same-turn one-shot image. Use the comparison report when the user requests a file or when OCR is the final deliverable.
5. On rejection or failure, report the reason and switch to the standard path only when safe.

## Installation and onboarding

After installation, verify `system.version`, `engine.requirements`, `engine.verify`, `system.preflight`, and `onboarding.status`. Baseline packages are `poppler-utils`, `tesseract-ocr`, `tesseract-ocr-kor`, `tesseract-ocr-eng`, and `tesseract-ocr-osd`; `ocrmypdf` is optional. Obtain approval before package changes. Recommend local-only by default. Ollama remains optional and requires separate endpoint, secret-use, network, and per-document transfer approval. Never persist plaintext tokens.

## Standard OCR workflow

1. Clarify input, languages, sensitivity, output, layout, and review needs.
2. Run `document.inspect`, rejecting traversal, symlinks, corrupt inputs, files over 64 MiB, PDFs over 200 pages, and pages over 40 million decoded pixels.
3. Run `ocr.prepare`, then `ocr.start`; use detached mode for multi-page or uncertain-duration work.
4. Track detached work with jobs, checkpoints, Workboard, and completion events rather than polling loops.
5. Prefer embedded PDF text; rasterize only pages without text at 200 DPI, one page at a time, one worker, `OMP_THREAD_LIMIT=1`.
6. Run `result.validate` and preserve raw OCR.
7. Normally finish completed OCR with `report.create`. Pass one or more completed job IDs as a bounded comma-separated `jobIds` string, owner, bounded output root, relative `.docx` output, document ID, and security label.
8. Use TXT/Markdown/JSON/TSV/hOCR/searchable PDF only when specifically useful; the enterprise comparison DOCX is the default final document for visual source-versus-result review.

## Enterprise comparison DOCX

`report.create` is local, credential-free, deterministic, and non-clobbering. It accepts 1–50 completed owned jobs and enforces a 256 MiB aggregate source limit, source integrity, ownership, completion, output containment, and symlink safety.

The document must include:

- Enterprise cover with title, document ID, generation time, and security label.
- Executive QA summary and file index.
- One numbered, page-separated section per source file.
- Original image and immutable raw OCR together for direct comparison.
- Filename, confidence, language, engine, source SHA-256, dimensions/pages, cache, validation, raw-preservation, and review-required status.
- A separately labeled corrected/normalized section only when `result.corrected.json` exists.
- Consistent professional styles, header, footer, and page-number fields.

For non-image jobs without retained raster imagery, state that the source preview is unavailable while retaining digest provenance. Never alter `result.json`. Never overwrite an existing report.

The package includes the reusable enterprise template at `templates/enterprise-comparison-template.docx` with its source HTML. Read `references/operations.md` for exact command contracts and `references/errors-and-recovery.md` for report recovery.

## Optional Ollama review

Use Ollama only for low-confidence page-image review. Run `review.prepare`, present page/image digests and sizes, source digest, threshold, model, endpoint identity, and `intentDigest`, then obtain approval for the exact unchanged transfer. Treat model output as untrusted, apply only accepted correction IDs/pages, preserve raw OCR, and store corrected output separately. Read `references/safety-and-privacy.md` before remote review.

## Safety and completion

- Local OCR and DOCX report generation use no network or credentials.
- Keep source files immutable and paths bounded.
- Never expose private paths, tokens, endpoints, or secret values.
- Retry only safe transient failures and preserve completed pages/results.
- Do not claim handwriting, semantic tables, or layout reconstruction beyond evidence.

Completion evidence for comparison reports requires document ID, file count, report SHA-256/size, per-file source digests and confidence, raw-preservation state, corrected-section presence, DOCX package validation, and known preview limitations. The linked Skill/Harness is complete only after version alignment, Gateway validation/trust, a real `prepare → run report.create`, readable Word/PDF verification, template validation, and representative one-file and multi-file tests.
