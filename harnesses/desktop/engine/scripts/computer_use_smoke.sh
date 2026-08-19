#!/usr/bin/env bash
set -euo pipefail
OUT=${1:-/workspace/desktop-skill-test/smoke-$(date +%Y%m%d-%H%M%S)}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SKILL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
DESKTOP=${DESKTOP_BIN:-$SKILL_DIR/desktop}
mkdir -p "$OUT"

log() { printf '\n## %s\n' "$*" | tee -a "$OUT/run.log"; }
run() { log "$*"; "$@" 2>&1 | tee -a "$OUT/run.log"; }

run "$DESKTOP" selftest
log "$DESKTOP observe --json --screenshot $OUT/baseline.png --depth 2"
"$DESKTOP" observe --json --screenshot "$OUT/baseline.png" --depth 2 > "$OUT/baseline.json"
python3 - "$OUT/baseline.json" <<'PY'
import json, sys
p=sys.argv[1]
d=json.load(open(p))
assert d['schema']=='desktop.observation.v1'
assert isinstance(d.get('nodes'), list)
assert d.get('screenshot', {}).get('bytes', 0) > 0
print('baseline observation OK')
PY

run "$DESKTOP" open browser https://example.com
run "$DESKTOP" wait --timeout 20 "Example Domain"
log "$DESKTOP observe --json --app Chromium --screenshot $OUT/chromium.png --depth 0"
"$DESKTOP" observe --json --app Chromium --screenshot "$OUT/chromium.png" --depth 0 > "$OUT/chromium.json"
python3 - "$OUT/chromium.json" <<'PY'
import json, sys
p=sys.argv[1]
d=json.load(open(p))
assert any('Chromium' in a['name'] for a in d['apps']), d['apps']
assert len(d['nodes']) > 0
assert any(n.get('bbox') for n in d['nodes']), 'expected at least one bbox'
print('chromium observation OK')
PY

# Known regression guard: this target may not be directly clickable by visible text.
# It must fail loudly with suggestions rather than silently succeeding.
if "$DESKTOP" click "More information" --app Chromium > "$OUT/click-mismatch.out" 2>&1; then
  echo "ERROR: visible-text mismatch unexpectedly clicked" | tee -a "$OUT/run.log"
  exit 1
fi
grep -E "not found|Did you mean|requires coordinate" "$OUT/click-mismatch.out" >/dev/null

run "$DESKTOP" snapshot "$OUT/final.png" --json --depth 2
test -s "$OUT/final.json"
"$DESKTOP" close --app Chromium >/dev/null 2>&1 || true

echo "SMOKE_OK $OUT" | tee -a "$OUT/run.log"
