#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-/workspace/desktop-skill-test/modal-dialog-benchmark}"
DESKTOP="/workspace/skills/desktop/desktop"
mkdir -p "$OUT/record"
"$DESKTOP" close --app Chromium --force >/dev/null 2>&1 || true
sleep 1
cat > "$OUT/modal.html" <<'HTML'
<!doctype html>
<meta charset="utf-8">
<title>Desktop Modal Benchmark</title>
<style>
body { font-family: sans-serif; padding: 24px; }
button, input { font-size: 18px; margin: 6px; padding: 8px; }
.backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.25); display: flex; align-items: center; justify-content: center; }
.dialog { background: white; border: 3px solid #335; border-radius: 8px; padding: 24px; min-width: 360px; box-shadow: 0 8px 30px rgba(0,0,0,.35); }
.hidden { display: none; }
.status { margin-top: 20px; font-weight: bold; }
</style>
<h1>Desktop Modal Benchmark</h1>
<p>Safe local modal/permission-like benchmark page.</p>
<button id="alertBtn" onclick="openAlert()">Open Safe Alert</button>
<button id="confirmBtn" onclick="openConfirm()">Open Safe Confirm</button>
<button id="promptBtn" onclick="openPrompt()">Open Safe Prompt</button>
<button id="permissionBtn" onclick="openPermission()">Open Permission Dialog</button>
<div id="status" class="status" aria-live="polite">Ready</div>
<div id="modal" class="backdrop hidden" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
  <div class="dialog">
    <h2 id="modalTitle">Dialog</h2>
    <p id="modalText">Text</p>
    <input id="promptInput" aria-label="Prompt Value" class="hidden" />
    <button id="acceptBtn" onclick="acceptDialog()">Dialog OK</button>
    <button id="cancelBtn" onclick="cancelDialog()">Dialog Cancel</button>
  </div>
</div>
<script>
let mode = 'alert';
function show(title, text, prompt=false) {
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalText').textContent = text;
  const inp = document.getElementById('promptInput');
  inp.className = prompt ? '' : 'hidden';
  document.getElementById('modal').className = 'backdrop';
  setTimeout(() => (prompt ? inp : document.getElementById('acceptBtn')).focus(), 80);
}
function hide() { document.getElementById('modal').className = 'backdrop hidden'; }
function openAlert() { mode='alert'; show('Safe Alert Dialog', 'Safe benchmark alert opened.'); }
function openConfirm() { mode='confirm'; show('Safe Confirm Dialog', 'Safe benchmark confirm opened.'); }
function openPrompt() { mode='prompt'; document.getElementById('promptInput').value=''; show('Safe Prompt Dialog', 'Type safe prompt value.', true); }
function openPermission() { mode='permission'; show('Permission Request Dialog', 'Allow local benchmark permission?', false); }
function acceptDialog() {
  const v = document.getElementById('promptInput').value;
  hide();
  if (mode === 'prompt') document.getElementById('status').textContent = 'Prompt accepted: ' + v;
  else if (mode === 'permission') document.getElementById('status').textContent = 'Permission accepted';
  else if (mode === 'confirm') document.getElementById('status').textContent = 'Confirm accepted';
  else document.getElementById('status').textContent = 'Alert accepted';
}
function cancelDialog() { hide(); document.getElementById('status').textContent = 'Dialog dismissed'; }
document.addEventListener('keydown', (e) => {
  if (document.getElementById('modal').className.includes('hidden')) return;
  if (e.key === 'Escape') cancelDialog();
  if (e.key === 'Enter' && mode !== 'prompt') acceptDialog();
});
</script>
HTML
python3 - "$OUT" <<'PY'
from pathlib import Path
import json, sys
out=Path(sys.argv[1])
url=(out/'modal.html').absolute().as_uri()
spec={"goal":"Modal/permission dialog benchmark using safe local browser modal-like UI with recorder evidence","maxSteps":16,"retries":2,"steps":[
 {"action":{"kind":"open","app":"browser","args":[url]},"verify":{"type":"text","text":"Desktop Modal Benchmark","timeout":20},"observeDepth":3},
 {"action":{"kind":"click_text","text":"Open Safe Alert"},"verify":{"type":"text","text":"Safe Alert Dialog","timeout":10},"observeDepth":5},
 {"action":{"kind":"handle_dialog","choice":"accept","target":"Dialog OK"},"verify":{"type":"text","text":"Alert accepted","timeout":10},"observeDepth":5},
 {"action":{"kind":"click_text","text":"Open Safe Confirm"},"verify":{"type":"text","text":"Safe Confirm Dialog","timeout":10},"observeDepth":5},
 {"action":{"kind":"handle_dialog","choice":"accept","target":"Dialog OK"},"verify":{"type":"text","text":"Confirm accepted","timeout":10},"observeDepth":5},
 {"action":{"kind":"click_text","text":"Open Safe Prompt"},"verify":{"type":"text","text":"Safe Prompt Dialog","timeout":10},"observeDepth":5},
 {"action":{"kind":"type","into":"Prompt Value","text":"desktop-ok","clear":True,"verify":True},"observeDepth":5},
 {"action":{"kind":"handle_dialog","choice":"accept","target":"Dialog OK"},"verify":{"type":"text","text":"Prompt accepted: desktop-ok","timeout":10},"observeDepth":5},
 {"action":{"kind":"click_text","text":"Open Permission Dialog"},"verify":{"type":"text","text":"Permission Request Dialog","timeout":10},"observeDepth":5},
 {"action":{"kind":"handle_dialog","choice":"accept","target":"Dialog OK"},"verify":{"type":"text","text":"Permission accepted","timeout":10},"observeDepth":5}
]}
(out/'modal-dialog-task.json').write_text(json.dumps(spec, indent=2), encoding='utf-8')
PY
"$DESKTOP" run-task "$OUT/modal-dialog-task.json" --record "$OUT/record" --allow-coordinate > "$OUT/run-task.out" 2> "$OUT/run-task.err"
grep -q 'Alert accepted' "$OUT/run-task.out"
grep -q 'Confirm accepted' "$OUT/run-task.out"
grep -q 'Prompt accepted: desktop-ok' "$OUT/run-task.out"
grep -q 'Permission accepted' "$OUT/run-task.out"
test -s "$OUT/record/events.jsonl"
grep -q 'task_pass' "$OUT/record/events.jsonl"
"$DESKTOP" snapshot "$OUT/final.png" --json --depth 3 >/dev/null
echo "MODAL_DIALOG_BENCHMARK_OK $OUT"
