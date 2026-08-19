"""Deterministic screenshot/template target localization for desktop automation.

This module deliberately uses local image processing only. It does not solve,
bypass, or interact with CAPTCHA/human-verification challenges. Clicking a visual
match remains coordinate-gated by the caller.
"""

import json
import os
import struct
import subprocess
import sys
import zlib
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .exit_codes import EXIT_NOT_FOUND

_FORBIDDEN_TERMS = (
    'captcha', 'recaptcha', 'hcaptcha', 'cloudflare', 'human-verification',
    'human_verification', 'bot-detection', 'bot_detection', 'anti-abuse',
)


@dataclass
class ImageData:
    width: int
    height: int
    pixels: bytes  # RGB bytes, row-major


def _reject_unsafe_label(*values: Optional[str]) -> None:
    joined = ' '.join(v or '' for v in values).lower()
    if any(term in joined for term in _FORBIDDEN_TERMS):
        raise PermissionError('image target localization refuses CAPTCHA/human-verification/bot-detection targets')


def _read_png(path: str) -> ImageData:
    """Read common non-interlaced PNG files without third-party dependencies."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    data = open(path, 'rb').read()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise RuntimeError('not a PNG file')
    pos = 8
    width = height = bit_depth = color_type = interlace = None
    compressed = bytearray()
    while pos + 8 <= len(data):
        length = struct.unpack('>I', data[pos:pos+4])[0]
        ctype = data[pos+4:pos+8]
        chunk = data[pos+8:pos+8+length]
        pos += 12 + length
        if ctype == b'IHDR':
            width, height, bit_depth, color_type, _comp, _filter, interlace = struct.unpack('>IIBBBBB', chunk)
        elif ctype == b'IDAT':
            compressed.extend(chunk)
        elif ctype == b'IEND':
            break
    if bit_depth != 8 or color_type not in (2, 6) or interlace != 0:
        raise RuntimeError('unsupported PNG; expected 8-bit non-interlaced RGB/RGBA')
    channels = 3 if color_type == 2 else 4
    raw = zlib.decompress(bytes(compressed))
    stride = width * channels
    rows = []
    i = 0
    prev = bytearray(stride)
    for _y in range(height):
        ftype = raw[i]; i += 1
        row = bytearray(raw[i:i+stride]); i += stride
        for x in range(stride):
            left = row[x - channels] if x >= channels else 0
            up = prev[x]
            up_left = prev[x - channels] if x >= channels else 0
            if ftype == 1:
                row[x] = (row[x] + left) & 255
            elif ftype == 2:
                row[x] = (row[x] + up) & 255
            elif ftype == 3:
                row[x] = (row[x] + ((left + up) // 2)) & 255
            elif ftype == 4:
                p = left + up - up_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                pr = left if pa <= pb and pa <= pc else (up if pb <= pc else up_left)
                row[x] = (row[x] + pr) & 255
            elif ftype != 0:
                raise RuntimeError(f'unsupported PNG filter {ftype}')
        rows.append(bytes(row))
        prev = row
    rgb = bytearray(width * height * 3)
    j = 0
    for row in rows:
        for x in range(0, len(row), channels):
            rgb[j:j+3] = row[x:x+3]
            j += 3
    return ImageData(width, height, bytes(rgb))


def _sample_offsets(tw: int, th: int, max_samples: int = 1600) -> List[Tuple[int, int]]:
    total = tw * th
    if total <= max_samples:
        return [(x, y) for y in range(th) for x in range(tw)]
    step = max(1, int((total / max_samples) ** 0.5))
    offsets = [(x, y) for y in range(0, th, step) for x in range(0, tw, step)]
    # Always include corners/center to avoid missing small distinctive edges.
    for p in ((0, 0), (tw - 1, 0), (0, th - 1), (tw - 1, th - 1), (tw // 2, th // 2)):
        if p not in offsets:
            offsets.append(p)
    return offsets


def locate_template(screenshot_path: str, template_path: str, threshold: float = 0.96, stride: int = 1, label: Optional[str] = None) -> dict:
    """Return the best normalized RGB template match.

    Score is 1.0 for exact pixel match and decreases with mean absolute RGB
    distance. This is deterministic and local, suitable for user-provided UI
    icons/buttons, not adversarial verification challenges.
    """
    _reject_unsafe_label(screenshot_path, template_path, label)
    if threshold < 0 or threshold > 1:
        raise ValueError('threshold must be between 0 and 1')
    stride = max(1, int(stride))
    screen = _read_png(screenshot_path)
    tmpl = _read_png(template_path)
    if tmpl.width <= 0 or tmpl.height <= 0 or tmpl.width > screen.width or tmpl.height > screen.height:
        raise ValueError('template must fit inside screenshot')
    offsets = _sample_offsets(tmpl.width, tmpl.height)
    best = {'score': -1.0, 'x': 0, 'y': 0}
    denom = 255.0 * 3.0 * len(offsets)
    max_y = screen.height - tmpl.height
    max_x = screen.width - tmpl.width
    sp = screen.pixels
    tp = tmpl.pixels
    for y in range(0, max_y + 1, stride):
        for x in range(0, max_x + 1, stride):
            diff = 0
            for ox, oy in offsets:
                si = ((y + oy) * screen.width + (x + ox)) * 3
                ti = (oy * tmpl.width + ox) * 3
                diff += abs(sp[si] - tp[ti]) + abs(sp[si + 1] - tp[ti + 1]) + abs(sp[si + 2] - tp[ti + 2])
                if 1.0 - (diff / denom) < best['score'] - 0.02:
                    break
            score = 1.0 - (diff / denom)
            if score > best['score']:
                best = {'score': round(score, 6), 'x': x, 'y': y}
    found = best['score'] >= threshold
    return {
        'schema': 'desktop.image_target.v1',
        'screenshot': screenshot_path,
        'template': template_path,
        'threshold': threshold,
        'stride': stride,
        'found': found,
        'score': best['score'],
        'bbox': {'x': best['x'], 'y': best['y'], 'width': tmpl.width, 'height': tmpl.height},
        'center': {'x': best['x'] + tmpl.width // 2, 'y': best['y'] + tmpl.height // 2},
        'method': 'local_rgb_template_sad',
        'safety': {'captcha_or_human_verification_refused': True},
    }


def print_locate(screenshot_path: str, template_path: str, threshold: float = 0.96, stride: int = 1, as_json: bool = False, label: Optional[str] = None) -> dict:
    result = locate_template(screenshot_path, template_path, threshold=threshold, stride=stride, label=label)
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        status = 'FOUND' if result['found'] else 'NOT_FOUND'
        c = result['center']
        print(f"{status} score={result['score']:.6f} center=({c['x']},{c['y']}) bbox={result['bbox']}")
    if not result['found']:
        sys.exit(EXIT_NOT_FOUND)
    return result
