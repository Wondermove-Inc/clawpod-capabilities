# Desktop 3.0.0 evidence

Canonical verification commands:

```sh
pytest -q tests harnesses/desktop/tests
python3 scripts/validate.py
python3 scripts/sync_registry.py --check
```

The local adversarial suite covers invalid input, unavailable backend and AT-SPI, D-Bus diagnostic handoff, target ambiguity and image safety contracts, human-verification stop, risky preview/approval, safe paths, redaction, revision, and idempotency behavior. Live Gateway parser coverage is in `tests/test_gateway_harness_manifests.py`.

The expanded adversarial gate is `harnesses/desktop/tests/test_adversarial.py`. It adds bounded timeout, backend crash/stale target, AT-SPI loss, backend-output secret exfiltration, coordinate gating, CAPTCHA preemption, dry-run side-effect, and ten-workflow app-matrix coverage. `tests/test_desktop_gateway_prepare.py` prepares every one of the 67 command schemas through the installed Gateway runner. `run_adversarial_benchmark.py` emits `artifacts/desktop-v3-adversarial/benchmark-matrix.json` plus a live screenshot. The benchmark requires zero false clicks and zero unsafe side effects.

Known environment limitation: this validation host provides DISPLAY and AT-SPI but no D-Bus session address. Portal-backed settings/file-picker mutations and true DPI/theme pixel fidelity therefore remain for the subsequent installed-session validation card; their planning, approval, timeout, and redaction paths are covered here without mutation.
