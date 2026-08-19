"""Human-paced input primitives for legitimate desktop automation.

These helpers make desktop actions easier for real applications to accept by adding
small, bounded pauses and pointer movement steps. They are not intended for, and
must not be used as, CAPTCHA/bot-detection bypass or anti-abuse evasion.
"""

import os
import random
import subprocess
import sys
import time

os.environ.setdefault('DISPLAY', ':99')

_ENV = {**os.environ, 'DISPLAY': ':99'}
_RNG = random.Random()


def _float_env(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return float(default)


def _int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return int(default)


def _run_xdotool(*args, timeout=10):
    try:
        result = subprocess.run(
            ['xdotool'] + [str(a) for a in args],
            env=_ENV,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        print("ERROR: xdotool not installed", file=sys.stderr)
        sys.exit(1)
    if result.returncode != 0:
        print(f"ERROR: xdotool {' '.join(str(a) for a in args)}: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def pause(kind='action'):
    """Sleep for a small bounded interval, configurable via DESKTOP_HUMAN_* env."""
    if os.environ.get('DESKTOP_FAST_INPUT') == '1':
        return
    defaults = {
        'before': (0.05, 0.16),
        'after': (0.08, 0.22),
        'key': (0.03, 0.09),
        'action': (0.06, 0.18),
    }
    lo, hi = defaults.get(kind, defaults['action'])
    lo = _float_env(f'DESKTOP_HUMAN_{kind.upper()}_MIN', lo)
    hi = _float_env(f'DESKTOP_HUMAN_{kind.upper()}_MAX', hi)
    if hi < lo:
        hi = lo
    time.sleep(_RNG.uniform(lo, hi))


def current_pointer():
    out = _run_xdotool('getmouselocation', '--shell')
    x = y = None
    for line in out.splitlines():
        if line.startswith('X='):
            x = int(line.split('=', 1)[1])
        elif line.startswith('Y='):
            y = int(line.split('=', 1)[1])
    return x, y


def move_pointer(x, y):
    """Move pointer in small steps to avoid abrupt jumps that miss focus changes."""
    x = int(x)
    y = int(y)
    if os.environ.get('DESKTOP_FAST_INPUT') == '1':
        _run_xdotool('mousemove', x, y)
        return
    try:
        sx, sy = current_pointer()
    except Exception:
        sx, sy = None, None
    if sx is None or sy is None:
        _run_xdotool('mousemove', x, y)
        return
    distance = max(abs(x - sx), abs(y - sy))
    steps = max(1, min(_int_env('DESKTOP_HUMAN_MOUSE_STEPS', 14), max(2, distance // 80)))
    for i in range(1, steps + 1):
        t = i / steps
        # smoothstep easing, with tiny bounded jitter on intermediate points only.
        eased = t * t * (3 - 2 * t)
        jx = 0 if i == steps else _RNG.randint(-2, 2)
        jy = 0 if i == steps else _RNG.randint(-2, 2)
        nx = round(sx + (x - sx) * eased + jx)
        ny = round(sy + (y - sy) * eased + jy)
        _run_xdotool('mousemove', nx, ny)
        time.sleep(_float_env('DESKTOP_HUMAN_MOUSE_STEP_DELAY', 0.015))


def click_at(x, y, button=1, repeat=1, delay_ms=120):
    pause('before')
    move_pointer(x, y)
    pause('action')
    if repeat > 1:
        _run_xdotool('click', '--repeat', int(repeat), '--delay', int(delay_ms), str(button))
    else:
        _run_xdotool('click', str(button))
    pause('after')


def press_key(combo):
    pause('before')
    _run_xdotool('key', '--clearmodifiers', combo)
    pause('after')


def type_text(text, delay_ms=None):
    """Type text with a conservative per-character delay."""
    delay_ms = int(delay_ms if delay_ms is not None else _int_env('DESKTOP_HUMAN_TYPE_DELAY_MS', 35))
    pause('before')
    _run_xdotool('type', '--delay', delay_ms, '--clearmodifiers', text, timeout=max(10, len(text) // 5 + 5))
    pause('after')
