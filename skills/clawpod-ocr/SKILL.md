---
name: "clawpod-ocr"
description: "Extract Korean/English text locally, create enterprise comparison DOCX reports, and optionally use guarded Ollama review."
---

# ClawPod OCR

Use the linked `clawpod-ocr` Harness. Treat the Skill and Harness as one installation unit with the canonical name `clawpod-ocr` and title **ClawPod OCR**. The Harness owns files, OCR processes, jobs, limits, provenance, and correction state.

## Route first

Use the **fast local image path** when all are true:

- The input is one PNG, JPEG, PPM, or PGM image.
- The user wants immediate text extraction or a concise transcription.
- No custom export, layout tooling, searchable PDF, detached processing, or remote review is requested.
- Current local onboarding is already verified.

Use the standard workflow for PDFs, multi-page inputs, uncertain-duration work, explicit exports, layout-sensitive output, recovery, or Ollama review.

## Fast local image path

1. Reuse the installed and already verified local engine state. Do not repeat installation onboarding or `engine.verify` for every image; `ocr.quick` performs the current engine check.
2. Call `ocr.quick` once through the normal Harness `prepare → run` path with the bounded input root, relative image path, `kor+eng` unless another language was requested, owner, and timeout.
3. `ocr.quick` must inspect limits, run or reuse cached Tesseract OCR, preserve a job/result, validate the copied source digest, and return text, confidence, cache state, source digest, dimensions, engine, language, and raw-preservation state in one response.
4. Report the extracted text immediately. `ocr.quick` also leaves a completed job that can feed `report.create`. Skip Workboard for a one-shot single image that completes in the same turn.
5. If `ocr.quick` rejects the input or fails, report the exact reason and switch to the standard workflow only when retry is safe. Never use it for PDFs or multi-page work.

## Installation and immediate onboarding

Immediately after installation, say: **“ClawPod OCR is installed but local OCR and optional Ollama readiness still need verification.”** Do not claim operational readiness from package presence.

1. Run `system.version`, `engine.requirements`, `engine.verify`, `system.preflight`, and `onboarding.status` once for installation or when readiness becomes stale.
2. The Debian/Ubuntu baseline is `poppler-utils`, `tesseract-ocr`, `tesseract-ocr-kor`, `tesseract-ocr-eng`, and `tesseract-ocr-osd`; `ocrmypdf` is optional.
3. Obtain explicit approval before installing or changing system packages. After approval, automate safe installation, language verification, and Korean/English smoke tests.
4. Offer `local-only`, `local + remote Ollama review`, or `defer Ollama`. Recommend local-only by default.
5. For Ollama onboarding, read `references/onboarding.md`. Explain endpoint transport, vision support, data transfer, protected auth injection, revocation, and per-document approval before configuring anything.
6. Store only protected secret-pointer and injection-target metadata. Never pass or persist plaintext tokens.
7. Ollama connection never authorizes document transfer. Every review requires a separately prepared and approved transfer-intent digest.

The capability is locally operational only when current `system.preflight` matches persisted successful `engine.verify`. Ollama readiness is independent and optional.

## Standard OCR workflow

1. Clarify input, outputs, languages, page range, layout needs, sensitivity, searchable-PDF need, and whether remote review is permitted.
2. Run `document.inspect`. Reject path violations, symlink escapes, corrupt or unsupported inputs, files over 64 MiB, PDFs over 200 pages, and images/raster pages over 40 million decoded pixels.
3. Run `ocr.prepare` and record source digest, pages, language, preprocessing, limits, and cache key.
4. Run `ocr.start`. Use detached mode for multi-page or uncertain-duration work. Track detached work through Workboard and completion events, not Gateway polling loops.
5. Use `job.status`, `job.logs`, checkpoints, `job.resume`, and `job.cancel` for lifecycle and recovery evidence.
6. Prefer embedded PDF text. Rasterize only pages without text at 200 DPI, one page at a time, one worker, and `OMP_THREAD_LIMIT=1`.
7. Run `result.validate` before export. Preserve raw OCR even when corrections exist.
8. Normally finish completed OCR with `report.create`: pass one or more completed job IDs as one bounded comma-separated `jobIds` string, an owner, bounded output root, and relative `.docx` output. Use one job for direct image/text comparison or multiple jobs for a consolidated enterprise report. Never overwrite an existing report.
9. Use TXT or Markdown for reading, JSON for confidence/provenance, TSV/hOCR for layout tooling, and searchable PDF only when dependencies validate.

## Comparison DOCX

`report.create` is local, credential-free, and deterministic. It validates ownership and completion for every job, source integrity, output containment, symlink safety, a 50-file limit, and a 256 MiB aggregate source limit. The report includes document identity, generation time, security label, executive QA counts, file index, per-file page breaks, source image, confidence/language/engine/digest/dimensions/pages/cache/validation/raw-preservation metadata, and review-required state. Raw OCR is explicitly immutable. If `result.corrected.json` exists, corrected or normalized text appears in a separate labeled section.

Read `references/operations.md` for detailed command and output contracts.

## Optional Ollama review

Use Ollama only for low-confidence page-image review.

1. Run `review.export-low-confidence`, then `review.prepare`.
2. Present every page number, image SHA-256, byte count, source digest, threshold, model, endpoint identity, and `intentDigest`.
3. Explain exactly which images will leave the host and obtain approval for the unchanged digest.
4. Inject approved auth and call `review.start` with the unchanged `approvalDigest`.
5. Treat output as an untrusted correction proposal. Inspect material changes and apply only explicitly accepted correction IDs or pages.
6. Preserve `result.json` unchanged and store corrected output separately with provenance.
7. On timeout, malformed output, or capability loss, preserve the local result and do not retry unsafe transfers automatically.

Read `references/safety-and-privacy.md` before remote review or sensitive-document work.

## Safety and recovery

- Local OCR is the default and requires no network or credentials.
- Keep source files immutable and paths bounded. Reject traversal, symlinks, corrupt inputs, pixel bombs, and unapproved clobbering.
- Never expose document contents, internal endpoints, tokens, secret values, or private paths in reports.
- Classify failures as prerequisite, input, path, resource, engine, ownership, interruption, cancellation, cache, export, auth, transport, model, approval digest, correction provenance, or internal.
- Preserve completed pages, raw OCR, checkpoints, and correction proposals. Retry only safe transient failures.
- Do not claim handwriting, semantic tables, or layout reconstruction quality beyond measured evidence.

Read `references/errors-and-recovery.md` for detailed recovery paths.

## Completion evidence

For `ocr.quick`, require source digest, dimensions, engine/language, confidence, cache state, validation, raw preservation, and known ambiguity. For the standard path, also require page count, completed pages, checkpoints, export digests, remote-review state, approval digest, correction IDs, and retry safety.

The linked Harness is complete only after name/title/version alignment, Gateway validation and trust, representative `prepare → run`, local onboarding, a timed real `ocr.quick` image run, scanned-page OCR, detached checkpoint/recovery, resource/path guards, exact remote transfer-intent binding, and raw-preserving correction behavior are proven.
