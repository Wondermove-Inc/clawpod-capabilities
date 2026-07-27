# Onboarding

Run the live Harness commands; never infer readiness from installation.

For Debian/Ubuntu, the required baseline is `poppler-utils tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng tesseract-ocr-osd`. Request explicit approval before system-package mutation. Verify Tesseract major 5 and actual `kor`, `eng`, and `osd` availability, then persist the successful local state and re-run preflight.

Offer local-only, local plus Ollama, or deferred Ollama. For remote Ollama, accept only loopback HTTP or non-loopback HTTPS. Store endpoint/model as bounded metadata and credentials only as protected pointer plus injection target. The Harness receives separately injected plaintext only for the approved process and never stores it. Verify `/api/version`, `/api/tags`, model existence, and vision capability or a synthetic one-pixel image smoke test.

State clearly that connection does not authorize page-image transfer. Every document review needs `review.prepare`, human-visible transfer details, and exact digest approval. Revoking the local binding, revoking a server token, and deleting the protected secret are separate actions.