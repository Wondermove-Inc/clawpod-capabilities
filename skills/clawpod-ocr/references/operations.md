# Operations

For one local PNG/JPEG/PPM/PGM image with no custom export or remote review, use one `ocr.quick` invocation. It returns text, confidence, cache state, source digest, dimensions, engine/language, validation, and raw-preservation state while retaining a completed job/result.

Use `document.inspect → ocr.prepare → ocr.start → result.validate` for PDFs, multi-page work, layout tooling, or recovery. Use detached jobs for multi-page or uncertain-duration work.

## Enterprise comparison report

Use `report.create` after OCR completes. Pass `jobIds` as one comma-separated string of 1–50 unique job IDs, plus matching owner, bounded `outputRoot`, relative `.docx` output, optional `documentId`, and `securityLabel`. The command refuses malformed, duplicate, foreign, incomplete, missing-result, source-mismatched, oversized, escaping, symlinked, or existing outputs.

The report contains cover controls, executive QA summary, file index, one page-separated file section, source image where available, immutable raw OCR, metadata, review flag, and separate corrected text when present. It never changes raw OCR. Use the bundled enterprise template as the visual baseline.

For optional remote review use `review.export-low-confidence → review.prepare → review.start → correction.inspect → correction.apply`. Approval binds exact source/page-image details. Raw OCR remains canonical evidence.