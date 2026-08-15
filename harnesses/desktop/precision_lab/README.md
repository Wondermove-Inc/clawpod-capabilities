# Desktop deterministic precision lab

This local-only benchmark exercises synthetic fixtures; it never injects input into a real desktop. Publication is prohibited. CAPTCHA and anti-cheat bypass are explicitly out of scope.

Run from the repository root:

```sh
python3 harnesses/desktop/precision_lab/precision_benchmark.py
pytest -q harnesses/desktop/tests/test_precision_lab.py
```

`environment-matrix.json` is the resolution, scale/DPI, theme, and D-Bus matrix. `thresholds.json` is the release gate. The output `artifacts/desktop-v3-precision/baseline.json` contains exact commits, every requested metric, accelerated one-hour-equivalent soak evidence, and gate results. `frames/` and `contact-sheet.png` provide deterministic visual evidence. A frame sequence is used instead of video because it is codec-independent, diffable, and reproducible with Python stdlib alone.

The benchmark treats a no-D-Bus portal operation as a successful safe refusal, not a successful action. Occlusion, focus steal, and modal/popup races require and measure recovery. Modeled input/latency measurements are deterministic fixture results; `benchmarkWallTimeMs` is the only host-performance measurement and is informational.
