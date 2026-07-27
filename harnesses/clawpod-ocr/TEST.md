# Tests

```sh
python3 -W error::ResourceWarning -m unittest -v harnesses/clawpod-ocr/test_clawpod_ocr.py
python3 scripts/validate.py
python3 scripts/sync_registry.py --check
python3 -m unittest discover -s tests -v
```

Synthetic tests cover real detached worker completion and ownership, liveness reconciliation, cancellation identity safety, all-page 200 DPI PDF checkpoint/resume and raster cleanup, fail-closed image dimensions and pixel ceilings, exact Tesseract/language onboarding states and enforced OCR gating, escaped/path-safe exports, cache-hit job provenance and page-image materialization, exact digest-bound review approval, image-bearing Ollama requests, protected environment and mode-0600 file auth injection, malformed and vision-incompatible model behavior, explicit correction selection/provenance, immutable raw results, and clean loopback server shutdown. They install nothing and use no credentials, real Ollama, or copyrighted documents.
