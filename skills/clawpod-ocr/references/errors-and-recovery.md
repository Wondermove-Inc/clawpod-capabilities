# Errors and recovery

Classify failures before retrying. Re-run engine verification for prerequisite drift; correct bounded input paths for traversal or symlink failures; reduce files/pages for resource limits; resume interrupted jobs from checkpoints; and never signal an unowned worker.

## Comparison report failures

- Empty, malformed, or duplicate `jobIds`: correct the bounded comma-separated list and prepare again.
- Foreign or incomplete job: use the matching owner or wait/resume OCR completion.
- Missing or source-mismatched result: stop; preserve evidence and regenerate OCR only when safe.
- More than 50 jobs or over 256 MiB aggregate source data: split into multiple reports.
- Existing, escaping, or symlinked output: choose a new bounded relative `.docx` path. Reports never clobber.
- Missing image preview for PDF/text jobs: the report may still use digest provenance and explicitly mark the preview unavailable.
- Invalid DOCX/package validation: preserve OCR jobs/results, remove only failed temporary output, and retry after fixing the artifact defect.

Remote review failures never replace local OCR. Re-run `review.prepare` after any intent change, and never retry external transfer without matching approval.