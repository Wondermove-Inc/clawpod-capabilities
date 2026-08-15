# Desktop 3.0.0 evidence

Canonical verification commands:

```sh
pytest -q tests harnesses/desktop/tests
python3 scripts/validate.py
python3 scripts/sync_registry.py --check
```

The local adversarial suite covers invalid input, unavailable backend and AT-SPI, D-Bus diagnostic handoff, target ambiguity and image safety contracts, human-verification stop, risky preview/approval, safe paths, redaction, revision, and idempotency behavior. Live Gateway parser coverage is in `tests/test_gateway_harness_manifests.py`.
