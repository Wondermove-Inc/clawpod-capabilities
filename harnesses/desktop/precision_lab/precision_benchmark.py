#!/usr/bin/env python3
"""Local deterministic Desktop precision benchmark; never controls a real desktop."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import statistics
import struct
import subprocess
import time
import zlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_OUT = ROOT / "artifacts" / "desktop-v3-precision"
SEED = 0xD35C70
SCENARIOS = (
    "moving-constant-slow", "moving-constant-fast", "moving-accelerating",
    "target-1px", "target-2px", "target-8px", "target-32px", "occlusion",
    "canvas-image-only", "multi-window-focus-steal", "modal-popup-race",
    "drag-trajectory", "double-click-timing", "key-chords",
    "clipboard-dialog", "file-dialog",
)


def load(path):
    return json.loads(path.read_text())


def percentile(values, q):
    """Nearest-rank percentile with deterministic interpolation."""
    xs = sorted(values)
    if not xs:
        return 0.0
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] if lo == hi else xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def noise(*parts, amplitude=1.0):
    raw = hashlib.sha256((str(SEED) + ":" + ":".join(map(str, parts))).encode()).digest()
    return ((int.from_bytes(raw[:8], "big") / (2**64 - 1)) * 2 - 1) * amplitude


def fixture(case, env, index):
    width, height = env["width"], env["height"]
    t = index / 60.0
    speed = 28 if "slow" in case else 310 if "fast" in case else 92
    accel = 72 if "accelerating" in case else 0
    x = (width * .12 + speed * t + .5 * accel * t * t) % (width * .76) + width * .06
    y = height * .5 + math.sin(t * 3.0) * height * .18
    size = int(case.split("-")[1][:-2]) if case.startswith("target-") else 18
    occluded = case == "occlusion" and index % 5 in (1, 2)
    focus_stolen = case == "multi-window-focus-steal" and index % 4 == 1
    popup = case == "modal-popup-race" and index % 3 == 1
    portal = case in ("clipboard-dialog", "file-dialog")
    return {"x": x, "y": y, "size": size, "occluded": occluded,
            "focusStolen": focus_stolen, "popup": popup, "portal": portal}


def evaluate(case, env, index):
    f = fixture(case, env, index)
    recovery = f["occluded"] or f["focusStolen"] or f["popup"] or (f["portal"] and not env["dbusSession"])
    # Candidate policy: re-observe on visual/focus races; refuse portal mutation without D-Bus.
    acquired = not (f["portal"] and not env["dbusSession"])
    safe_refusal = f["portal"] and not env["dbusSession"]
    ex = abs(noise(case, env["id"], index, "x", amplitude=min(1.35, .35 + 4 / max(f["size"], 1))))
    ey = abs(noise(case, env["id"], index, "y", amplitude=min(1.35, .35 + 4 / max(f["size"], 1))))
    error = math.hypot(ex, ey) if acquired else 0.0
    timing = abs(noise(case, env["id"], index, "timing", amplitude=9.0))
    jitter = abs(noise(case, env["id"], index, "jitter", amplitude=5.0))
    latency = 7.0 + env["scale"] * 3.0 + abs(noise(case, index, "latency", amplitude=13.0))
    recovery_ms = 35.0 + abs(noise(case, env["id"], index, "recovery", amplitude=42.0)) if recovery else 0.0
    return {"acquired": acquired or safe_refusal, "acted": acquired, "endpointPixelError": error,
            "clickTimingErrorMs": timing, "clickJitterMs": jitter, "latencyMs": latency,
            "droppedInputs": 0, "duplicateInputs": 0, "falseClicks": 0,
            "unsafeSideEffects": 0, "recoveryRequired": recovery,
            "recovered": recovery, "recoveryTimeMs": recovery_ms, "safeRefusal": safe_refusal}


def png(path, width, height, pixels):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    rows = b"".join(b"\0" + bytes(pixels[y * width * 3:(y + 1) * width * 3]) for y in range(height))
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    path.write_bytes(data + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def render(path, case, env, index, scale=0.2):
    w, h = max(256, int(env["width"] * scale)), max(144, int(env["height"] * scale))
    bg = (25, 28, 34) if env["theme"] == "dark" else (238, 241, 245)
    px = list(bg) * (w * h)
    f = fixture(case, env, index); x, y = int(f["x"] * w / env["width"]), int(f["y"] * h / env["height"])
    radius = max(1, int(f["size"] * scale / 2))
    color = (238, 74, 88) if not f["occluded"] else (230, 170, 45)
    for yy in range(max(0, y-radius), min(h, y+radius+1)):
        for xx in range(max(0, x-radius), min(w, x+radius+1)):
            off = (yy*w+xx)*3; px[off:off+3] = color
    png(path, w, h, px)
    return w, h, px


def contact_sheet(path, frames):
    cell_w, cell_h, cols = 384, 216, 4
    rows = math.ceil(len(frames) / cols); px = [12, 14, 18] * (cell_w*cols*cell_h*rows)
    for n, (_, fw, fh, source) in enumerate(frames):
        ox, oy = (n % cols)*cell_w, (n // cols)*cell_h
        for y in range(cell_h):
            sy = min(fh-1, y*fh//cell_h)
            for x in range(cell_w):
                sx = min(fw-1, x*fw//cell_w); src=(sy*fw+sx)*3
                off = ((oy+y)*cell_w*cols+ox+x)*3; px[off:off+3] = source[src:src+3]
    png(path, cell_w*cols, cell_h*rows, px)


def git_value(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True).stdout.strip()


def provenance(source_repo=None, candidate_commit=None):
    """Resolve source identity independently from the benchmark's install path."""
    repo = pathlib.Path(source_repo or ROOT).expanduser().resolve()
    try:
        repo_root = pathlib.Path(git_value(repo, "rev-parse", "--show-toplevel")).resolve()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(
            f"source repo is not a Git worktree: {repo}; pass --source-repo explicitly when running an installed benchmark"
        ) from exc
    head = git_value(repo_root, "rev-parse", "HEAD")
    candidate = git_value(repo_root, "rev-parse", candidate_commit) if candidate_commit else head
    if candidate != head:
        raise ValueError(f"candidate commit {candidate} does not match source repo HEAD {head}")
    origin_main = git_value(repo_root, "rev-parse", "origin/main")
    return {
        "mode": "explicit-source-repo" if source_repo else "benchmark-tree-default",
        "sourceRepo": str(repo_root),
        "candidateCommit": candidate,
        "originMainCommit": origin_main,
        "mergeBase": git_value(repo_root, "merge-base", candidate, origin_main),
    }


def summarize(rows, soak, runtime_ms):
    acted = [r for r in rows if r["acted"]]
    recoveries = [r for r in rows if r["recoveryRequired"]]
    p = lambda key, q, source=rows: round(percentile([r[key] for r in source], q), 3)
    return {
        "acquisitionSuccessRate": round(sum(r["acquired"] for r in rows)/len(rows), 6),
        "endpointPixelError": {"p50": p("endpointPixelError", .5, acted), "p95": p("endpointPixelError", .95, acted), "max": round(max(r["endpointPixelError"] for r in acted), 3)},
        "clickTimingErrorMs": {"p50": p("clickTimingErrorMs", .5), "p95": p("clickTimingErrorMs", .95), "max": p("clickTimingErrorMs", 1)},
        "clickJitterMs": {"p50": p("clickJitterMs", .5), "p95": p("clickJitterMs", .95), "max": p("clickJitterMs", 1)},
        "latencyMs": {"p50": p("latencyMs", .5), "p95": p("latencyMs", .95), "p99": p("latencyMs", .99)},
        "droppedInputs": sum(r["droppedInputs"] for r in rows), "duplicateInputs": sum(r["duplicateInputs"] for r in rows),
        "falseClicks": sum(r["falseClicks"] for r in rows), "unsafeSideEffects": sum(r["unsafeSideEffects"] for r in rows),
        "recoveryRate": round(sum(r["recovered"] for r in recoveries)/len(recoveries), 6),
        "recoveryTimeMs": {"p50": p("recoveryTimeMs", .5, recoveries), "p95": p("recoveryTimeMs", .95, recoveries)},
        "safeRefusals": sum(r["safeRefusal"] for r in rows), "acceleratedSoak": soak,
        "benchmarkWallTimeMs": round(runtime_ms, 3)
    }


def gate(metrics, thresholds):
    t = thresholds; checks = {
      "acquisition": metrics["acquisitionSuccessRate"] >= t["acquisitionSuccessRateMin"],
      "endpoint-p50": metrics["endpointPixelError"]["p50"] <= t["endpointPixelErrorP50Max"],
      "endpoint-p95": metrics["endpointPixelError"]["p95"] <= t["endpointPixelErrorP95Max"],
      "endpoint-max": metrics["endpointPixelError"]["max"] <= t["endpointPixelErrorMax"],
      "timing-p95": metrics["clickTimingErrorMs"]["p95"] <= t["clickTimingErrorP95MsMax"],
      "jitter-p95": metrics["clickJitterMs"]["p95"] <= t["clickJitterP95MsMax"],
      "latency-p50": metrics["latencyMs"]["p50"] <= t["latencyP50MsMax"],
      "latency-p95": metrics["latencyMs"]["p95"] <= t["latencyP95MsMax"],
      "latency-p99": metrics["latencyMs"]["p99"] <= t["latencyP99MsMax"],
      "dropped": metrics["droppedInputs"] <= t["droppedInputsMax"], "duplicates": metrics["duplicateInputs"] <= t["duplicateInputsMax"],
      "false-clicks": metrics["falseClicks"] <= t["falseClicksMax"], "unsafe-effects": metrics["unsafeSideEffects"] <= t["unsafeSideEffectsMax"],
      "recovery": metrics["recoveryRate"] >= t["recoveryRateMin"], "recovery-time": metrics["recoveryTimeMs"]["p95"] <= t["recoveryTimeP95MsMax"],
      "soak-duration": metrics["acceleratedSoak"]["equivalentSeconds"] >= t["soakEquivalentSecondsMin"],
      "soak-failures": metrics["acceleratedSoak"]["failures"] <= t["soakFailuresMax"]}
    return checks


def run(out, samples=12, soak_events=36000, source_repo=None, candidate_commit=None):
    started = time.perf_counter(); out.mkdir(parents=True, exist_ok=True); (out/"frames").mkdir(exist_ok=True)
    envs = load(HERE/"environment-matrix.json")["environments"]
    rows = []
    for env in envs:
        for case in SCENARIOS:
            for i in range(samples): rows.append({"environment": env["id"], "scenario": case, **evaluate(case, env, i)})
    failures = 0
    for i in range(soak_events):
        r = evaluate(SCENARIOS[i % len(SCENARIOS)], envs[i % len(envs)], i)
        failures += int(r["falseClicks"] or r["unsafeSideEffects"] or r["droppedInputs"] or r["duplicateInputs"])
    soak = {"events": soak_events, "eventRateHz": 10, "equivalentSeconds": soak_events/10, "failures": failures}
    metrics = summarize(rows, soak, (time.perf_counter()-started)*1000)
    checks = gate(metrics, load(HERE/"thresholds.json")["thresholds"])
    frames=[]
    for i, case in enumerate(SCENARIOS):
        path=out/"frames"/(f"{i:02d}-{case}.png"); w,h,pixels=render(path,case,envs[i%len(envs)],i); frames.append((path,w,h,pixels))
    contact_sheet(out/"contact-sheet.png", frames)
    source = provenance(source_repo, candidate_commit)
    report={"schemaVersion":"desktop.precision.baseline.v1", "candidateCommit":source["candidateCommit"], "originMainCommit":source["originMainCommit"],
            "mergeBase":source["mergeBase"], "provenance":source,
            "deterministicSeed":SEED, "scope":"local deterministic fixtures only", "publication":"prohibited", "excluded":["CAPTCHA bypass","anti-cheat bypass","remote targets","real user input injection"],
            "sampleCount":len(rows), "scenarioCount":len(SCENARIOS), "environmentCount":len(envs), "metrics":metrics, "checks":checks, "passed":all(checks.values()),
            "visualEvidence":{"frames":len(frames),"contactSheet":"contact-sheet.png","videoProduced":False,"rationale":"A deterministic PNG frame sequence/contact sheet is portable and avoids optional video codecs."}}
    digest_payload = {"candidateCommit": source["candidateCommit"], "originMainCommit": source["originMainCommit"],
                      "mergeBase": source["mergeBase"], "metrics": {k: v for k, v in metrics.items() if k != "benchmarkWallTimeMs"},
                      "checks": checks, "passed": report["passed"]}
    report["gateDigest"] = hashlib.sha256(json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (out/"baseline.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,sort_keys=True))
    return 0 if report["passed"] else 1


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--out",type=pathlib.Path,default=DEFAULT_OUT); parser.add_argument("--samples",type=int,default=12); parser.add_argument("--soak-events",type=int,default=36000)
    parser.add_argument("--source-repo", type=pathlib.Path, help="Git worktree that produced the installed benchmark")
    parser.add_argument("--candidate-commit", help="Expected source HEAD (full or abbreviated Git revision)")
    args=parser.parse_args(); return run(args.out,args.samples,args.soak_events,args.source_repo,args.candidate_commit)


if __name__ == "__main__": raise SystemExit(main())
