# ClawPod OCR

Bounded Linux OCR harness for Korean and English. Text PDFs use `pdftotext`; scanned PDFs are rasterized one declared page at a time, dimension-checked, OCRed, checkpointed, and immediately cleaned. `ocr.start --detached` launches an owned process and persists its PID, Linux start identity, and nonce. Status reconciles liveness, cancellation signals only the matching process, and resume starts at the next unfinished page.

Required Debian/Ubuntu packages: `poppler-utils tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng tesseract-ocr-osd`. Optional searchable PDF export requires `ocrmypdf`. Run `engine.requirements`, `engine.verify`, then `system.preflight`; verification requires Tesseract major 5 and actual `kor`, `eng`, and `osd` availability and persists the exact result.

Ollama is optional. HTTP is accepted only on loopback; all other endpoints require HTTPS. Configuration stores only a `secret:<pointer>` plus an injection target. The harness never resolves pointers. Inject a token separately through the declared environment variable or a file-path environment variable whose file is mode 0600. Verification checks the model and vision capability (or runs an image smoke test if capability metadata is absent). Approved review sends a bounded low-confidence **page image** through Ollama's `images` field. Raw OCR is immutable; corrections are diff-only and `correction.apply` requires explicit IDs or pages.

Limits: 64 MiB input, 200 PDF pages, 40 million decoded pixels per image/raster page, 8 MiB per reviewed page image, 2 MiB remote response, one worker, and 0.1–60 second command/backend timeout bounds. Relative output paths and symlink traversal are rejected. hOCR text is HTML-escaped; Markdown export uses explicit page headings.
