#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-/workspace/desktop-skill-test/image-target-smoke}"
DESKTOP="/workspace/skills/desktop/desktop"
mkdir -p "$OUT"
python3 - "$OUT" <<'PY'
from pathlib import Path
import struct, sys, zlib
out = Path(sys.argv[1])
def write_png(path, w, h, pix):
    def chunk(t, d):
        import zlib, struct
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t+d)&0xffffffff)
    raw = b''.join(b'\x00' + pix[y*w*3:(y+1)*w*3] for y in range(h))
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w,h,8,2,0,0,0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
    path.write_bytes(data)
w,h=220,140
pix=bytearray([255,255,255]*(w*h))
for y in range(h):
  for x in range(w):
    if x in (0,w-1) or y in (0,h-1): pix[(y*w+x)*3:(y*w+x)*3+3]=bytes([229,231,235])
for y in range(52,87):
  for x in range(88,143): pix[(y*w+x)*3:(y*w+x)*3+3]=bytes([37,99,235])
write_png(out/'screen.png',w,h,pix)
tw,th=55,35
tp=bytearray()
for y in range(52,87):
  tp.extend(pix[(y*w+88)*3:(y*w+143)*3])
write_png(out/'target.png',tw,th,tp)
PY
"$DESKTOP" locate-image --screenshot "$OUT/screen.png" --template "$OUT/target.png" --threshold 0.99 --json > "$OUT/locate.json"
python3 - "$OUT/locate.json" <<'PY'
import json, sys
r=json.load(open(sys.argv[1]))
assert r['found'], r
assert r['center']['x'] in range(110,122), r
assert r['center']['y'] in range(66,75), r
PY
if "$DESKTOP" locate-image --screenshot "$OUT/screen.png" --template "$OUT/target.png" --label captcha-check > "$OUT/forbidden.out" 2>&1; then
  echo "expected CAPTCHA label refusal" >&2; exit 1
fi
echo "IMAGE_TARGET_SMOKE_OK $OUT"
