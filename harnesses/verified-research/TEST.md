# Test contract

Run:

```text
python3 -m pytest -q harnesses/verified-research/tests/test_verified_research.py
python3 -m pytest -q
python3 harnesses/verified-research/scripts/generate_schemas.py
python3 scripts/sync_registry.py --check
python3 scripts/validate.py
python3 -m py_compile harnesses/verified-research/verified_research.py harnesses/verified-research/scripts/generate_schemas.py
git diff --check
```

The focused suite covers exact-byte snapshot tampering, metadata and date candidates, claim structure, quote/line integrity, Gateway root-path versus relative-child string contracts, CLI execution with absolute roots and nested relative child names, incomplete root/name pairs, path and overwrite safety, input/output bounds, optional PDF backend limits, SSRF and redirect rejection, compressed and oversized HTTP responses, offline imports, partial-failure exits, sanitized internal errors, and deterministic output excluding `requestId`. No Node subtests exist in this repository.
