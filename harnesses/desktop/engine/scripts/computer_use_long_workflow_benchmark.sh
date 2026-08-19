#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-/workspace/desktop-skill-test/long-workflow-benchmark}"
DESKTOP="/workspace/skills/desktop/desktop"
mkdir -p "$OUT/site" "$OUT/record"
"$DESKTOP" close --app Chromium >/dev/null 2>&1 || true
cat > "$OUT/site/index.html" <<'HTML'
<!doctype html><meta charset="utf-8"><title>Desktop Long Workflow Step One</title>
<h1>Step One</h1><label>Full name <input aria-label="Full name" id="name"></label>
<label>Project code <input aria-label="Project code" id="code"></label>
<button id="next">Continue to step two</button><div id="status">Waiting for step one</div>
<script>next.onclick=()=>{localStorage.name=name.value;localStorage.code=code.value; location.href='step2.html'};</script>
HTML
cat > "$OUT/site/step2.html" <<'HTML'
<!doctype html><meta charset="utf-8"><title>Desktop Long Workflow Step Two</title>
<h1>Step Two</h1><p id="intro">Delayed options ready</p>
<div id="delayed"><label><input type="checkbox" aria-label="Safe option"> Safe option</label><button id="review">Continue to review</button></div>
HTML
cat > "$OUT/site/review.html" <<'HTML'
<!doctype html><meta charset="utf-8"><title>Desktop Long Workflow Review</title>
<h1>Review</h1><p id="summary">Review for Jieun Test / DSK-IMG-LONG</p><div id="result">Workflow complete: recorder evidence ready</div>
HTML
python3 - "$OUT" <<'PY'
from pathlib import Path
import json, sys
out=Path(sys.argv[1])
page1=(out/'site/index.html').resolve().as_uri()
page2=(out/'site/step2.html').resolve().as_uri()
review=(out/'site/review.html').resolve().as_uri()
spec={"goal":"Long multi-page browser workflow benchmark with form input, navigation, delayed state, and recorder evidence","maxSteps":9,"retry":1,"steps":[
 {"action":{"kind":"open","app":"browser","args":[page1]},"verify":{"type":"text","text":"Step One","timeout":20},"observeDepth":4},
 {"action":{"kind":"form_fill","fields":[{"into":"Full name","text":"Jieun Test","verify":False},{"into":"Project code","text":"DSK-IMG-LONG","verify":False}]},"verify":{"type":"text","text":"Continue to step two","timeout":5},"observeDepth":5},
 {"action":{"kind":"open","app":"browser","args":[page2]},"verify":{"type":"text","text":"Step Two","timeout":20},"observeDepth":5},
 {"action":{"kind":"wait_seconds","seconds":1.2},"verify":{"type":"text","text":"Delayed options ready","timeout":10},"observeDepth":5},
 {"action":{"kind":"open","app":"browser","args":[review]},"verify":{"type":"text","text":"Review for Jieun Test / DSK-IMG-LONG","timeout":20},"observeDepth":5},
 {"action":{"kind":"wait_seconds","seconds":0.5},"verify":{"type":"text","text":"Workflow complete: recorder evidence ready","timeout":10},"observeDepth":5}
]}
(out/'long-workflow-task.json').write_text(json.dumps(spec, indent=2), encoding='utf-8')
PY
"$DESKTOP" run-task "$OUT/long-workflow-task.json" --record "$OUT/record" --allow-coordinate > "$OUT/run-task.out" 2> "$OUT/run-task.err"
test -s "$OUT/record/events.jsonl"
grep -q 'task_pass' "$OUT/record/events.jsonl"
echo "LONG_WORKFLOW_BENCHMARK_OK $OUT"
