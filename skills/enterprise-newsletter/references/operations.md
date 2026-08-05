# Harness operations and recovery

Invoke `./enterprise_newsletter.py <command>` and consume the single JSON object on stdout. Outputs use numeric `schemaVersion: 1`.

- `status`: report local renderer/profile readiness.
- `schema [--output-root ROOT --output NAME]`: inspect or atomically write the JSON schema.
- `validate --input-root ROOT --input NAME`: validate without writing.
- `render --input-root ROOT --input NAME --output-root PRIVATE_ROOT --html NAME --text NAME`: write deterministic HTML and text after computed content-parity checks; existing or identical targets are rejected.
- `inspect --input-root ROOT --input NAME`: inspect a rendered HTML or text file.
- `release.prepare --input-root ROOT --input NAME --recipients JSON --approved-content-digest HEX --output-root PRIVATE_ROOT --manifest NAME`: write a manifest containing only digests and counts.
- `release.verify --input-root ROOT --input NAME --recipients JSON --manifest-root PRIVATE_ROOT --manifest NAME`: recompute and verify both bindings.

Roots must be absolute existing directories owned by the current user and inaccessible to group/other users. Relative leaf names cannot traverse directories. Symlinks, non-regular inputs, output clobbering, and symlinked roots are rejected. Create roots with mode `0700`. Outputs are atomic regular files with mode `0600`.

Recipient input is a JSON array of email strings. It is normalized, deduplicated, sorted for hashing, and never persisted or returned raw. If validation, evidence, parity, approval, or digest verification fails, correct the input and repeat review; do not bypass the failure.
