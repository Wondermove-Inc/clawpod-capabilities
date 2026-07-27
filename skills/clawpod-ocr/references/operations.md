# Operations

For one local PNG/JPEG/PPM/PGM image with no custom export or remote review, use one `ocr.quick` invocation. It returns text, confidence, cache state, source digest, dimensions, engine/language, validation, and raw-preservation state while retaining a normal job/result for audit and later recovery.

Use `document.inspect → ocr.prepare → ocr.start → result.validate → result.export` for PDFs, multi-page work, explicit exports, layout tooling, or recovery. Use detached jobs for multi-page or uncertain-duration work and track completion without Gateway polling loops.

`job.resume` continues from persisted pages. `job.cancel` acts only on the exact owned PID/start identity/nonce. Never retry a job while its worker is alive.

For optional remote review use `review.export-low-confidence → review.prepare → review.start → correction.inspect → correction.apply`. Approval binds to the source and page-image digests, bytes, pages, threshold, endpoint, and model. Apply only named correction IDs or pages.

Formats: TXT/Markdown for reading, JSON for provenance, TSV/hOCR for structured downstream use, and searchable PDF only when `ocrmypdf` is available. Raw OCR remains canonical evidence; corrected output is separate.

## `report.create`

Create a comparison Word report only from completed jobs owned by the caller. Gateway input uses `jobIds` as a comma-separated string because array argument mapping is not assumed. IDs must be unique and individually valid; each report accepts 1 to 50 jobs and at most 256 MiB of aggregate source bytes. Required inputs are `jobIds`, `owner`, `outputRoot`, and a bounded relative `.docx` `output`. Optional inputs are `documentId`, `securityLabel`, and the QA confidence `threshold`.

The write-safe command refuses clobbering, rejects path traversal and symlinks, validates every source digest, and emits report SHA-256, bytes, document ID, generation timestamp, file count, review count, and raw-preservation state. It uses bundled standard-library OOXML and needs no network, credentials, LibreOffice, or Python package installation.
