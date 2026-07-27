# ClawPod OCR

Bounded Linux OCR harness. It prefers `pdftotext`, otherwise rasterizes one PDF page at a time with `pdftoppm` and runs Tesseract with one worker and `OMP_THREAD_LIMIT=1`. Inputs are copied immutably into owner-scoped job state. Paths are relative and symlink escape is rejected. Raw OCR and source hashes remain in results; optional Ollama correction is diff-only and separately approved.

Real packages (Debian/Ubuntu): `poppler-utils tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng tesseract-ocr-osd`. Optional searchable PDF: `ocrmypdf` (plus its distribution dependencies). Run `onboarding.status`, `system.preflight`, and `engine.verify` after installation. Ollama is optional: configure only a protected `secret:<pointer>` metadata reference, then verify `/api/version` and `/api/tags` over loopback HTTP or HTTPS.

Limits: 64 MiB/file, 200 pages, 40 MP declared guard, one worker. Gateway commands are bounded; `ocr.start --detached` checkpoints and returns immediately, while `job.resume` performs a bounded slice.
