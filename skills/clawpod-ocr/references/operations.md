# Operations

For one local PNG/JPEG/PPM/PGM image with no custom export or remote review, use one `ocr.quick` invocation. It returns text, confidence, cache state, source digest, dimensions, engine/language, validation, and raw-preservation state while retaining a completed job/result.

Use `document.inspect → ocr.prepare → ocr.start → result.validate` for PDFs, multi-page work, layout tooling, or recovery. Use detached jobs for multi-page or uncertain-duration work.

## Enterprise comparison report

Use `report.create` after OCR completes. Pass `jobIds` as one comma-separated string of 1–50 unique job IDs, plus matching owner, bounded `outputRoot`, relative `.docx` output, optional `documentId`, and `securityLabel`. The command refuses malformed, duplicate, foreign, incomplete, missing-result, source-mismatched, oversized, escaping, symlinked, or existing outputs.

The report is reader-first: cover controls, executive information, review-needed highlights, file index, and one page-separated section per file. Each section shows a deterministic `읽기용 정리본` before source comparison, followed by separately derived corrected text when present and the original image in source evidence. Presentation normalization may insert boundaries without changing recognized tokens: common receipt labels are matched longest-first (including OCR-inserted spaces inside Korean labels), section anchors create grouped blocks, and each value ends at the next recognized label. Label/value rows render as two-column tables. Generic text keeps existing lines, with sentence-ending or bounded paragraph splits only for long one-line OCR. A single consolidated `RAW OCR (감사용 원문)` appendix follows all reader-facing sections with filename, source digest, and immutability statement. `result.json` is never changed. Use the bundled enterprise template as the visual baseline.

For optional remote review use `review.export-low-confidence → review.prepare → review.start → correction.inspect → correction.apply`. Approval binds exact source/page-image details. Raw OCR remains canonical evidence.