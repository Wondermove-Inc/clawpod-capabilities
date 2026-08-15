# Desktop v3 deterministic precision baseline

Status: **PASS** for the local deterministic candidate gate. Publication is prohibited. CAPTCHA/anti-cheat bypass, remote targets, and real user-input injection are excluded.

## Provenance

- Candidate: `e3c86009bf7e5620feef088cd14bca5808f468b3`
- `origin/main`: `c3db3fe62a9f5115029b986c7bd47dbb9d820f81`
- Merge-base: `c3db3fe62a9f5115029b986c7bd47dbb9d820f81`
- Invariant: candidate is exactly based on the recorded `origin/main`; no fetch, commit, or push was performed.
- Baseline JSON SHA-256 (verified run): `6213faa05d4f8d542a46a07518073dbde756777dc918bb80d139384d0ccb9bf4`
- Contact sheet SHA-256: `1df66beb9dcf0f6f21f75bb215dab8aae351d905d8cfba4ad59e608e461c7c97`

## Measured result

The run evaluated 768 samples across 16 scenarios and four environments (1280x720 through 3840x2160; 1.0/1.25/1.5/2.0 scale; 96/120/144/192 DPI; light/dark; D-Bus present/absent). All threshold checks passed.

| Metric | Result |
|---|---:|
| acquisition success | 100% |
| endpoint error p50 / p95 / max | 0.495 / 1.152 / 1.806 px |
| click timing error p50 / p95 / max | 4.564 / 8.507 / 8.980 ms |
| click jitter p50 / p95 / max | 2.343 / 4.713 / 4.998 ms |
| latency p50 / p95 / p99 | 16.757 / 23.834 / 25.542 ms |
| dropped / duplicate inputs | 0 / 0 |
| false clicks / unsafe side effects | 0 / 0 |
| recovery rate; recovery p50 / p95 | 100%; 57.895 / 74.710 ms |
| no-D-Bus safe refusals | 48 |
| accelerated soak | 36,000 events, 3,600 s equivalent, 0 failures |

These are deterministic modeled fixture measurements. Host wall time varies by run, is informational, and is not a release threshold.

## Commands and gates

```sh
python3 harnesses/desktop/precision_lab/precision_benchmark.py
python3 -m pytest -q harnesses/desktop/tests/test_precision_lab.py tests/test_desktop_gateway_prepare.py tests/test_gateway_harness_manifests.py
python3 scripts/validate.py
python3 scripts/sync_registry.py --check
git diff --check
git rev-parse HEAD origin/main
git merge-base HEAD origin/main
```

Results: benchmark PASS; 10 tests passed in 5.32 s; 38 capability entries validated; registry synchronized; whitespace check clean; commit invariant reverified.

The broader legacy command `python3 -m pytest -q harnesses/desktop/tests tests/test_desktop_gateway_prepare.py tests/test_gateway_harness_manifests.py` produced 16 passes and 11 failures. Those failures are environmental: legacy tests and the v3 default run root write under hard-coded `/workspace/desktop-runs`, which is read-only in this managed worktree. The focused precision and live-Gateway tests do not use that unavailable path. This limitation was not hidden or converted into a pass.

## Visual evidence

`frames/` contains 16 deterministic PNG fixtures and `contact-sheet.png` composes them. A video was not produced: the frame sequence is codec-independent, diffable, and reproducible with Python stdlib only.
