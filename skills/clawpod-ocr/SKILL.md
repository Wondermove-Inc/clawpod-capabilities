---
name: "clawpod-ocr"
description: "Extract Korean/English text locally with Tesseract and optionally correct low-confidence pages through guarded Ollama."
---

# ClawPod OCR

Use the linked `clawpod-ocr` Harness. Treat the Skill and Harness as one installation unit with the canonical name `clawpod-ocr` and title **ClawPod OCR**. The deterministic Harness owns files, OCR processes, jobs, resource limits, provenance, and correction state. The Skill selects the safe path and presents approvals.

## Installation and immediate onboarding

Immediately after installation, say: **“ClawPod OCR is installed but local OCR and optional Ollama readiness still need verification.”** Do not claim operational readiness from package presence.

1. Run `system.version`, `engine.requirements`, `engine.verify`, `system.preflight`, and `onboarding.status`.
2. Explain the Linux prerequisites and exact missing components. The baseline Debian/Ubuntu packages are `poppler-utils`, `tesseract-ocr`, `tesseract-ocr-kor`, `tesseract-ocr-eng`, and `tesseract-ocr-osd`; `ocrmypdf` is optional for searchable-PDF export.
3. Obtain explicit approval before installing or changing system packages. After approval, automate every safe installation, language verification, and synthetic Korean/English smoke test. Do not ask the user to run automatable commands.
4. Offer `local-only`, `local + remote Ollama review`, or `defer Ollama`. Local-only is the default recommendation.
5. If Ollama is selected, read `references/onboarding.md`, explain endpoint transport, model/image support, data transfer, auth injection, revocation, and per-document approval. Obtain approval before accepting or storing connection metadata or secret pointers.
6. Call `ollama.configure` with HTTPS for non-loopback endpoints or HTTP only for loopback. Store only protected secret-pointer and injection-target metadata. Never pass or persist plaintext tokens.
7. With separate secret-use and bounded network-read approval, inject the token through the declared environment or mode-0600 file environment and call `ollama.verify`. Verification must confirm the configured model and vision capability or complete the synthetic image smoke test.
8. Preserve exact states: local `not-verified`, `verified`, or `verification-failed`; Ollama `deferred`, `configured_unverified`, `verification_in_progress`, `verified`, `model_unavailable`, `model_vision_incompatible`, or `model_capability_unverified`.
9. Explain that Ollama connection never authorizes document or page-image transfer. Each review requires a separately prepared and approved transfer intent digest.
10. If onboarding is deferred, record pending state and provide the exact resume commands. For revocation, call `ollama.revoke`; protected-secret deletion is a separate destructive action.

The capability is operational only when current `system.preflight` matches persisted successful `engine.verify`. Ollama readiness is independent and optional.

## OCR workflow

1. Clarify the input, output formats, languages, page range, expected layout, sensitivity, searchable-PDF need, and whether remote review is permitted.
2. Run `document.inspect`. Reject path violations, symlink escapes, unsupported or corrupt inputs, files over 64 MiB, PDFs over 200 pages, and images/raster pages over 40 million decoded pixels.
3. Run `ocr.prepare` and present the source digest, declared pages, language, preprocess mode, resource limits, and deterministic cache key.
4. Start with `ocr.start`. Use detached mode for multi-page or uncertain-duration work. Track detached work through Workboard and completion events, not Gateway polling loops.
5. Use `job.status`, `job.logs`, and checkpoints for evidence. `job.resume` continues at the next unfinished page. `job.cancel` requires explicit intent and may stop only the persisted owned PID/start identity/nonce.
6. Prefer embedded PDF text. Rasterize only pages without text, at fixed 200 DPI, one page at a time. Keep one worker and `OMP_THREAD_LIMIT=1`; preserve completed pages and clean temporary rasters immediately.
7. Run `result.validate` before export. Export only bounded relative paths through `result.export`. Preserve raw OCR even when corrections exist.
8. Use TXT or Markdown for reading, JSON for page/confidence/provenance, TSV/hOCR for downstream layout tooling, and searchable PDF only when optional dependencies validate.

Read `references/operations.md` for command selection and output contracts.

## Optional Ollama review

Use Ollama only for low-confidence **page-image** review. Do not call it OCR crop review unless a real crop exists and is listed in the prepared intent.

1. Run `review.export-low-confidence` to inspect candidate pages locally.
2. Run `review.prepare`. Present every page number, image SHA-256, byte count, source digest, confidence threshold, model, endpoint identity, and the returned `intentDigest`.
3. Explain that only the listed bounded page images will leave the agent host. Obtain explicit approval for that exact digest. Any page, image, model, endpoint, threshold, or digest change requires new approval.
4. Inject approved auth and call `review.start` with the unchanged `approvalDigest`. Never send automatically after connection verification.
5. Treat Ollama output as an untrusted correction proposal. Use `correction.inspect`, compare against raw OCR and page image, and present material changes.
6. Apply only explicitly accepted correction IDs or pages with `correction.apply`. Never apply every suggestion implicitly.
7. Preserve `result.json` unchanged and store corrected output separately with model, endpoint, timestamp, raw hash, and correction ID provenance.
8. If Ollama is unavailable, times out, returns malformed output, or loses vision compatibility, preserve the local result and report review as pending or failed. Do not silently downgrade, retry unsafe transfers, or replace local OCR.

## Safety and privacy

- Local OCR is the default and requires no network or credentials.
- Treat remote review as external data transfer plus possible secret use, even when Ollama has no monetary cost.
- Never expose document contents, internal endpoints, tokens, secret values, raw authorization responses, or private file paths in reports.
- Never resolve a protected pointer inside the Harness. Use scoped runtime injection only.
- Reject non-loopback plaintext HTTP, endpoint userinfo, unbounded timeouts, oversized requests/responses, permissive secret files, and absent injection for configured pointers.
- Keep source files immutable and use bounded relative paths. Reject traversal, symlinks, corrupt inputs, decompression/pixel bombs, and output clobber without the required intent.
- Do not claim handwriting, semantic tables, or layout reconstruction quality beyond measured evidence.

Read `references/safety-and-privacy.md` before remote review or sensitive-document work.

## Failure and recovery

Classify failures as prerequisite, input, path, resource, OCR engine, job ownership, interruption, cancellation, cache, export, auth injection, transport, model, vision capability, approval digest, remote response, correction provenance, or internal.

Preserve completed pages, raw OCR, checkpoints, correction proposals, and known side effects. Retry only safe transient failures. Re-run `review.prepare` after any transfer-intent change. Read `references/errors-and-recovery.md` for exact recovery paths.

## Completion evidence

Require source digest, page count, OCR engine/version/languages, embedded-text versus Tesseract path, completed pages, confidence summary, cache state, exported artifact digests, raw-preservation status, remote-review state, approved transfer digest, correction IDs applied, known quality limits, and retry safety.

The linked Harness is incomplete until name/title alignment, manifest validation, Gateway install/validate/trust, representative `prepare → run`, local engine onboarding, text-PDF fast path, real scanned-page OCR, detached all-page checkpoint/resume/cancel, resource/path guards, optional synthetic Ollama vision verification, exact transfer-intent binding, and raw-preserving correction application are proven. Report real Tesseract and real Ollama evidence separately from synthetic tests.
