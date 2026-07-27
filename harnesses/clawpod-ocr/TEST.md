# Tests

```sh
python3 -W error::ResourceWarning -m unittest -v harnesses/clawpod-ocr/test_clawpod_ocr.py
python3 scripts/validate.py
python3 scripts/sync_registry.py --check
python3 -m unittest discover -s tests -v
```

Synthetic tests cover the one-call `ocr.quick` image path, inline validation, cache rebinding, and PDF rejection; real detached worker completion and ownership; liveness reconciliation; cancellation identity safety; all-page 200 DPI PDF checkpoint/resume and raster cleanup; fail-closed image dimensions and pixel ceilings; exact Tesseract/language onboarding states and enforced OCR gating; escaped/path-safe exports; cache-hit job provenance and page-image materialization; exact digest-bound review approval; image-bearing Ollama requests; protected environment and mode-0600 file auth injection; malformed and vision-incompatible model behavior; explicit correction selection/provenance; immutable raw results; and clean loopback server shutdown. They install nothing and use no credentials, real Ollama, or copyrighted documents.

## v0.3.1 report evidence

- Unit coverage validates single-file and consolidated multi-file DOCX packages, embedded media, enterprise metadata, raw/corrected distinction, immutable `result.json`, malformed/duplicate/foreign/incomplete jobs, bounded paths, symlinks, and clobber refusal.
- Inspect a generated artifact with `unzip -t report.docx` and verify `[Content_Types].xml`, `word/document.xml`, `word/_rels/document.xml.rels`, headers/footers, styles, and `word/media/*`.
- The renderer is deterministic standard-library OOXML (`zipfile` and XML), so LibreOffice availability is not a runtime prerequisite. A real installed LibreOffice can be used for an optional open/resave interoperability smoke test.
