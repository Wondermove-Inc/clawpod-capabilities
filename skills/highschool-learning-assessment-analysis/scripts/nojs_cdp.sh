#!/bin/bash
# Optional cross-check: true browser-level no-JS render via CDP (Emulation.setScriptExecutionDisabled).
# render.py --nojs (script-stripped copy) is the default; use this when you want the real JS-off path.
# usage: nojs_cdp.sh <abs-or-rel html> <out.png> [W] [H]     (one chromium, timeout 60, own user-data-dir)
set -u
here="$(cd "$(dirname "$0")" && pwd)"
html="$(realpath "$1")"; out="$(realpath -m "$2")"; W="${3:-1920}"; H="${4:-1080}"
ud=$(mktemp -d /tmp/chr-nojs-XXXX); port=$((9300 + RANDOM % 500))
timeout 60 chromium --headless=new --no-sandbox --disable-gpu --user-data-dir=$ud --hide-scrollbars --remote-debugging-port=$port about:blank >/dev/null 2>&1 &
cpid=$!
for i in $(seq 1 30); do curl -s http://127.0.0.1:$port/json/version >/dev/null && break; sleep 0.5; done
timeout 40 node "$here/nojs_shot.mjs" $port "$html" "$out" $W $H; rc=$?
kill $cpid 2>/dev/null; wait $cpid 2>/dev/null; rm -rf $ud
exit $rc
