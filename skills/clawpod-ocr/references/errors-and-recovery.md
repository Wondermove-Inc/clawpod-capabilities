# Errors and recovery

- Prerequisite or language failure: install only with approval, run `engine.verify`, then `system.preflight`.
- Input/path/resource failure: correct the source or limits; do not retry unchanged.
- Interrupted job: inspect ownership and checkpoint, then resume only if no worker is alive.
- Cancellation: verify owned worker stopped and preserve completed pages.
- Cache mismatch: invalidate only the affected bounded entry and rerun.
- Ollama configured but unverified: inject approved auth and verify; never transfer pages yet.
- Model unavailable or vision-incompatible: select and verify another vision model.
- Approval digest mismatch: rerun `review.prepare`, show the new intent, obtain new approval.
- Timeout/malformed remote response: preserve local OCR and correction state; retry only when the request was not accepted or duplicated.
- Correction provenance mismatch: do not apply; regenerate proposals against the current raw result.

Always report completed pages, raw-result state, remote side effects, retry safety, and the exact recovery action.