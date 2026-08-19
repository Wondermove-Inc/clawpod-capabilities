"""Window management via xdotool + EWMH work-area (no wmctrl/Xlib needed).

Commands: window-activate/close/minimize/maximize/restore/resize/move.

xdotool has no native maximize, so maximize records the current geometry to a
small per-user cache and resizes the window to the EWMH work area
(`_NET_WORKAREA`, which excludes panels/struts); restore replays the saved
geometry. Window ids are X ids (decimal or 0xHEX) as emitted by ui.observe /
window.list; they are passed to xdotool verbatim.
"""

import json
import os
import pathlib
import subprocess
import sys

os.environ.setdefault('DISPLAY', ':99')

_ENV = {**os.environ, 'DISPLAY': ':99'}
_GEOM_CACHE = pathlib.Path(
    os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))
) / 'desktop' / 'window-geometry.json'


def _run(*args, check=True):
    """Run a tool with DISPLAY set; shell=False. Exit 1 with stderr on failure."""
    try:
        result = subprocess.run(list(args), env=_ENV, capture_output=True, text=True)
    except FileNotFoundError:
        print(f"ERROR: {args[0]} not installed", file=sys.stderr)
        sys.exit(1)
    if check and result.returncode != 0:
        print(f"ERROR: {' '.join(args)}: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def _require_wid(wid):
    if not wid:
        print("ERROR: window id required", file=sys.stderr)
        sys.exit(1)
    return wid


def _window_geometry(wid):
    """Return (x, y, width, height) for a window via xdotool getwindowgeometry."""
    out = _run('xdotool', 'getwindowgeometry', '--shell', wid)
    vals = {}
    for line in out.splitlines():
        if '=' in line:
            k, _, v = line.partition('=')
            vals[k.strip()] = v.strip()
    try:
        return int(vals['X']), int(vals['Y']), int(vals['WIDTH']), int(vals['HEIGHT'])
    except (KeyError, ValueError):
        print(f"ERROR: could not read geometry for window {wid}", file=sys.stderr)
        sys.exit(1)


def _work_area():
    """EWMH work area (x, y, w, h) excluding panels; falls back to display size."""
    try:
        out = _run('xprop', '-root', '_NET_WORKAREA', check=False)
        # _NET_WORKAREA(CARDINAL) = 0, 0, 1920, 1053, ...  (first 4 = primary)
        nums = [int(n) for n in out.split('=')[-1].replace(',', ' ').split()][:4]
        if len(nums) == 4 and nums[2] > 0 and nums[3] > 0:
            return tuple(nums)
    except (ValueError, IndexError):
        pass
    geo = _run('xdotool', 'getdisplaygeometry')  # "1920 1080"
    w, h = (int(n) for n in geo.split()[:2])
    return 0, 0, w, h


def _load_cache():
    try:
        return json.loads(_GEOM_CACHE.read_text())
    except (OSError, ValueError):
        return {}


def _save_cache(cache):
    try:
        _GEOM_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _GEOM_CACHE.write_text(json.dumps(cache))
    except OSError:
        pass  # cache is best-effort; restore just falls back to work area


def activate(wid):
    wid = _require_wid(wid)
    _run('xdotool', 'windowactivate', '--sync', wid)
    print(f"Window {wid} activated")


def close(wid):
    wid = _require_wid(wid)
    _run('xdotool', 'windowclose', wid)
    print(f"Window {wid} closed")


def minimize(wid):
    wid = _require_wid(wid)
    _run('xdotool', 'windowminimize', '--sync', wid)
    print(f"Window {wid} minimized")


def maximize(wid):
    wid = _require_wid(wid)
    x, y, w, h = _window_geometry(wid)
    cache = _load_cache()
    cache[str(wid)] = {'x': x, 'y': y, 'width': w, 'height': h}
    _save_cache(cache)
    ax, ay, aw, ah = _work_area()
    _run('xdotool', 'windowsize', '--sync', wid, str(aw), str(ah))
    _run('xdotool', 'windowmove', '--sync', wid, str(ax), str(ay))
    print(f"Window {wid} maximized to work area {aw}x{ah}+{ax}+{ay}")


def restore(wid):
    wid = _require_wid(wid)
    saved = _load_cache().get(str(wid))
    if not saved:
        print(f"ERROR: no saved geometry for window {wid}; nothing to restore", file=sys.stderr)
        sys.exit(1)
    _run('xdotool', 'windowsize', '--sync', wid, str(saved['width']), str(saved['height']))
    _run('xdotool', 'windowmove', '--sync', wid, str(saved['x']), str(saved['y']))
    print(f"Window {wid} restored to {saved['width']}x{saved['height']}+{saved['x']}+{saved['y']}")


def resize(wid, width, height):
    wid = _require_wid(wid)
    if width is None or height is None:
        print("ERROR: window-resize requires <wid> <width> <height>", file=sys.stderr)
        sys.exit(1)
    _run('xdotool', 'windowsize', '--sync', wid, str(int(width)), str(int(height)))
    print(f"Window {wid} resized to {int(width)}x{int(height)}")


def move(wid, x, y):
    wid = _require_wid(wid)
    if x is None or y is None:
        print("ERROR: window-move requires <wid> <x> <y>", file=sys.stderr)
        sys.exit(1)
    _run('xdotool', 'windowmove', '--sync', wid, str(int(x)), str(int(y)))
    print(f"Window {wid} moved to {int(x)},{int(y)}")


# --- observation (read-only) -------------------------------------------------

def _window_record(wid):
    """Build a JSON-able record for one X window id, or None if it vanished."""
    name = _run('xdotool', 'getwindowname', wid, check=False)
    geo = _run('xdotool', 'getwindowgeometry', '--shell', wid, check=False)
    if not geo:
        return None
    vals = {}
    for line in geo.splitlines():
        if '=' in line:
            k, _, v = line.partition('=')
            vals[k.strip()] = v.strip()
    try:
        rec = {
            'id': str(wid),
            'name': name,
            'x': int(vals['X']), 'y': int(vals['Y']),
            'width': int(vals['WIDTH']), 'height': int(vals['HEIGHT']),
        }
    except (KeyError, ValueError):
        return None
    pid = _run('xdotool', 'getwindowpid', wid, check=False)
    if pid.isdigit():
        rec['pid'] = int(pid)
    return rec


def list_windows():
    """List visible top-level windows (id, name, geometry, pid) as JSON."""
    ids = _run('xdotool', 'search', '--onlyvisible', '--name', '', check=False)
    windows = []
    seen = set()
    for wid in ids.split():
        if wid in seen:
            continue
        seen.add(wid)
        rec = _window_record(wid)
        # Skip unnamed zero-size scaffolding (root/desktop/panels have no useful name+size).
        if rec and (rec['name'] or (rec['width'] > 1 and rec['height'] > 1)):
            windows.append(rec)
    print(json.dumps({'windows': windows}, separators=(',', ':')))


def get_window(wid):
    wid = _require_wid(wid)
    rec = _window_record(wid)
    if rec is None:
        print(f"ERROR: no such window {wid}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(rec, separators=(',', ':')))


def list_screens():
    """List connected screens/monitors (name, geometry, primary) via xrandr."""
    out = _run('xrandr', '--query', check=False)
    screens = []
    for line in out.splitlines():
        if ' connected' not in line:
            continue
        parts = line.split()
        name = parts[0]
        primary = 'primary' in parts
        geom = next((p for p in parts if 'x' in p and '+' in p), None)  # e.g. 1920x1080+0+0
        rec = {'name': name, 'primary': primary}
        if geom:
            try:
                res, x, y = geom.split('+')
                w, h = res.split('x')
                rec.update({'width': int(w), 'height': int(h), 'x': int(x), 'y': int(y)})
            except ValueError:
                pass
        screens.append(rec)
    if not screens:
        geo = _run('xdotool', 'getdisplaygeometry', check=False)
        try:
            w, h = (int(n) for n in geo.split()[:2])
            screens.append({'name': 'default', 'primary': True, 'width': w, 'height': h, 'x': 0, 'y': 0})
        except (ValueError, IndexError):
            pass
    print(json.dumps({'screens': screens}, separators=(',', ':')))
