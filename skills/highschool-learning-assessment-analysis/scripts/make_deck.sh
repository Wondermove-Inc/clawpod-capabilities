#!/bin/bash
# One-shot pipeline: build -> render (layout check + PNG + PDF + sheets + no-JS shot) -> QA.
# usage: make_deck.sh DATA.json OUTDIR
# Exit code = first failing stage (build/render/qa). Sequential, one chromium at a time.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
data="$1"; out="$2"
mkdir -p "$out"
python3 -c 'import PIL' 2>/dev/null || pip install --user -q pillow  # render.py needs Pillow for the PDF and sheets
timeout 60 python3 "$here/build_deck.py" "$data" "$out" || { echo "BUILD FAILED"; exit 2; }
timeout 900 python3 "$here/render.py" "$out" --nojs || { echo "RENDER FAILED (see $out/_layout.json)"; exit 3; }
timeout 60 python3 "$here/qa.py" "$data" "$out" > "$out/qa.json"; rc=$?
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('QA', 'PASS' if d['ok'] else 'FAIL', {k:v['fails'] for k,v in d['checks'].items() if v['fails']})" "$out/qa.json"
exit $rc
