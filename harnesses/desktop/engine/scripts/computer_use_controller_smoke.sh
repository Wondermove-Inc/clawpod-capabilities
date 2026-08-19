#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SKILL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
DESKTOP=${DESKTOP_BIN:-$SKILL_DIR/desktop}
OUT=${1:-/workspace/desktop-skill-test/controller-smoke-$(date +%Y%m%d-%H%M%S)}
mkdir -p "$OUT"

log() { printf '\n## %s\n' "$*" | tee -a "$OUT/run.log"; }

"$DESKTOP" close --app Chromium --force >/dev/null 2>&1 || true
sleep 1

log syntax
python3 -m py_compile "$SKILL_DIR/desktop" "$SKILL_DIR"/lib/*.py

log verify_file
printf 'ok' > "$OUT/file.txt"
"$DESKTOP" verify --file "$OUT/file.txt" --nonempty --json | tee "$OUT/verify-file.json"

log run_task_browser
cat > "$OUT/browser-task.json" <<'JSON'
{
  "goal": "Open example.com and verify page text",
  "maxSteps": 3,
  "steps": [
    {"action": {"kind": "open", "app": "browser", "args": ["https://example.com"]}, "verify": {"type": "text", "text": "Example Domain", "timeout": 20}, "observeDepth": 2},
    {"action": {"kind": "wait_text", "text": "Example Domain", "timeout": 5}, "verify": {"type": "text", "text": "Example Domain", "timeout": 1}, "observeDepth": 2}
  ]
}
JSON
"$DESKTOP" run-task "$OUT/browser-task.json" --record "$OUT/run-task" | tee "$OUT/run-task.out"
test -s "$OUT/run-task/events.jsonl"
test -s "$OUT/run-task/001-attempt1-before.json"
test -s "$OUT/run-task/001-attempt1-after.json"

grep -q 'task_pass' "$OUT/run-task/events.jsonl"
grep -q '"kind": "action_start"' "$OUT/run-task/events.jsonl"
grep -q '"iso":' "$OUT/run-task/events.jsonl"

log safety_coordinate_denied
cat > "$OUT/coordinate-task.json" <<'JSON'
{"steps":[{"action":{"kind":"click_xy","x":1,"y":1}}]}
JSON
if "$DESKTOP" run-task "$OUT/coordinate-task.json" --record "$OUT/coordinate-run" > "$OUT/coordinate.out" 2>&1; then
  echo "ERROR: coordinate click was not denied" | tee -a "$OUT/run.log"
  exit 1
fi
grep -q 'coordinate click requires' "$OUT/coordinate.out"

log safety_coordinate_allowed
"$DESKTOP" run-task "$OUT/coordinate-task.json" --record "$OUT/coordinate-run-allowed" --allow-coordinate | tee "$OUT/coordinate-allowed.out"
grep -q 'RUN_TASK_OK' "$OUT/coordinate-allowed.out"

log safety_sensitive_args_denied
cat > "$OUT/sensitive-task.json" <<'JSON'
{"steps":[{"action":{"kind":"open","app":"terminal","args":["rm -rf /tmp/desktop-danger"]}}]}
JSON
if "$DESKTOP" run-task "$OUT/sensitive-task.json" --record "$OUT/sensitive-run" > "$OUT/sensitive.out" 2>&1; then
  echo "ERROR: destructive args were not denied" | tee -a "$OUT/run.log"
  exit 1
fi
grep -q 'potentially destructive' "$OUT/sensitive.out"

log retry_recovery_records
cat > "$OUT/retry-task.json" <<'JSON'
{"retry":1,"steps":[{"action":{"kind":"wait_text","text":"definitely-not-present","timeout":1}}]}
JSON
if "$DESKTOP" run-task "$OUT/retry-task.json" --record "$OUT/retry-run" > "$OUT/retry.out" 2>&1; then
  echo "ERROR: missing text retry task unexpectedly passed" | tee -a "$OUT/run.log"
  exit 1
fi
test -s "$OUT/retry-run/001-attempt1-recovery.json"
grep -q 'step_recovery_observation' "$OUT/retry-run/events.jsonl"

log safety_policy_allowed_apps
cat > "$OUT/policy.json" <<'JSON'
{"allowedApps":["browser"]}
JSON
cat > "$OUT/policy-deny-task.json" <<'JSON'
{"steps":[{"action":{"kind":"open","app":"terminal"}}]}
JSON
if "$DESKTOP" run-task "$OUT/policy-deny-task.json" --record "$OUT/policy-run" --policy "$OUT/policy.json" > "$OUT/policy.out" 2>&1; then
  echo "ERROR: policy did not deny non-allowlisted app" | tee -a "$OUT/run.log"
  exit 1
fi
grep -q 'not allowlisted' "$OUT/policy.out"

log screenshot_injection_safe
BAD="$OUT/screen-\$(touch SHOULD_NOT_EXIST).png"
"$DESKTOP" screenshot "$BAD" | tee "$OUT/screenshot.out"
test ! -e /workspace/SHOULD_NOT_EXIST

"$DESKTOP" close --app Chromium >/dev/null 2>&1 || true

echo "CONTROLLER_SMOKE_OK $OUT" | tee -a "$OUT/run.log"
