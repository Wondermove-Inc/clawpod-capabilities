# Verified Research Harness

A dependency-light deterministic evidence pipeline. It retrieves public HTTP(S) HTML, JSON, RSS/Atom, and PDF bytes; normalizes bounded text; records hashes and canonical metadata; deduplicates batches; and builds, inspects, and validates evidence bundles. It never decides semantic truth.

All content is untrusted. Production URL validation rejects credentials, unsafe schemes/ports, Unicode host ambiguity, and non-public DNS results on every redirect. TLS verification remains enabled and no cookies or authorization headers are sent. A loopback fixture seam exists only when `VERIFIED_RESEARCH_INTERNAL_TEST_MODE=1`.

PDF bytes are always hashable. Text extraction uses optional `pdftotext`; absent or empty extraction is explicitly `dependency_missing` or `unsupported`, never fabricated. Output files are stable JSON, atomic, mode 0600, and confined beneath explicit roots. See `command_contracts.json` for typed inputs.
