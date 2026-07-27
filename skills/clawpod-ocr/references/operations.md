# Operations

For one local PNG/JPEG/PPM/PGM image with no custom export or remote review, use one `ocr.quick` invocation. It returns text, confidence, cache state, source digest, dimensions, engine/language, validation, and raw-preservation state while retaining a normal job/result for audit and later recovery.

Use `document.inspect → ocr.prepare → ocr.start → result.validate → result.export` for PDFs, multi-page work, explicit exports, layout tooling, or recovery. Use detached jobs for multi-page or uncertain-duration work and track completion without Gateway polling loops.

`job.resume` continues from persisted pages. `job.cancel` acts only on the exact owned PID/start identity/nonce. Never retry a job while its worker is alive.

For optional remote review use `review.export-low-confidence → review.prepare → review.start → correction.inspect → correction.apply`. Approval binds to the source and page-image digests, bytes, pages, threshold, endpoint, and model. Apply only named correction IDs or pages.

Formats: TXT/Markdown for reading, JSON for provenance, TSV/hOCR for structured downstream use, and searchable PDF only when `ocrmypdf` is available. Raw OCR remains canonical evidence; corrected output is separate.