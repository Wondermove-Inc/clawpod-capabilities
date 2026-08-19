#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SKILL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
DESKTOP=${DESKTOP_BIN:-$SKILL_DIR/desktop}
OUT=${1:-/workspace/desktop-skill-test/human-verification-smoke-$(date +%Y%m%d-%H%M%S)}
mkdir -p "$OUT"

log() { printf '\n## %s\n' "$*" | tee -a "$OUT/run.log"; }

"$DESKTOP" close --app Chromium --force >/dev/null 2>&1 || true
sleep 1

log syntax
python3 -m py_compile "$SKILL_DIR/desktop" "$SKILL_DIR"/lib/*.py

log create_local_pages
cat > "$OUT/normal.html" <<'HTML'
<!doctype html><title>Normal Form</title><label>Name <input aria-label="Name" id="name"></label><button>Submit</button>
HTML
cat > "$OUT/captcha.html" <<'HTML'
<!doctype html><title>Security Check</title><h1>Verify you are human</h1><p>CAPTCHA required</p>
HTML

log normal_browser_form
"$DESKTOP" open browser "file://$OUT/normal.html"
"$DESKTOP" wait --timeout 15 "Name"
"$DESKTOP" verify --human-check --json --screenshot "$OUT/normal-check.png" > "$OUT/normal-check.json"
"$DESKTOP" type --into Name "Jieun Test" --allow-coordinate
"$DESKTOP" snapshot "$OUT/normal-final.png" --json --depth 2

log human_verification_detected
"$DESKTOP" open browser "file://$OUT/captcha.html"
"$DESKTOP" wait --timeout 15 "Verify you are human"
if "$DESKTOP" verify --human-check --json --screenshot "$OUT/captcha-check.png" > "$OUT/captcha-check.json" 2> "$OUT/captcha-check.err"; then
  echo "ERROR: human verification was not detected" | tee -a "$OUT/run.log"
  exit 1
fi
python3 - "$OUT/captcha-check.json" <<'PY'
import json, sys
with open(sys.argv[1]) as f: d=json.load(f)
assert d['requiresHuman'] is True
assert d['hits']
print('human verification detection JSON OK')
PY

log run_task_stops_on_human_verification
cat > "$OUT/captcha-task.json" <<JSON
{
  "goal": "Open local human verification page and stop",
  "steps": [
    {"action": {"kind": "open", "app": "browser", "args": ["file://$OUT/captcha.html"]}, "verify": {"type": "human_check"}, "observeDepth": 3}
  ]
}
JSON
if "$DESKTOP" run-task "$OUT/captcha-task.json" --record "$OUT/captcha-run" > "$OUT/captcha-run.out" 2>&1; then
  echo "ERROR: run-task did not stop on human verification" | tee -a "$OUT/run.log"
  exit 1
fi
grep -q 'Human verification detected' "$OUT/captcha-run.out"
grep -q 'step_fail' "$OUT/captcha-run/events.jsonl"

"$DESKTOP" close --app Chromium >/dev/null 2>&1 || true

echo "HUMAN_VERIFICATION_SMOKE_OK $OUT" | tee -a "$OUT/run.log"
