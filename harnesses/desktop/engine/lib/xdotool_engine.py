"""xdotool wrapper for keyboard/mouse simulation."""

import os
import subprocess
import sys
import time

os.environ.setdefault('DISPLAY', ':99')

from . import human_input

_ENV = {**os.environ, 'DISPLAY': ':99'}


def _run_xdotool(*args):
    """Run xdotool with DISPLAY=:99. shell=False always."""
    try:
        result = subprocess.run(
            ['xdotool'] + list(args),
            env=_ENV, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"ERROR: xdotool {' '.join(args)}: {result.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
        return result.stdout.strip()
    except FileNotFoundError:
        print("ERROR: xdotool not installed", file=sys.stderr)
        sys.exit(1)


def _focus_editable_node(node, name, allow_coordinate=False):
    """Focus an editable node by clicking its screen bbox center.

    Browser text fields may expose an AT-SPI activate action that returns
    success without moving keyboard focus. For actual typing, a verified
    coordinate click on the editable control is more reliable than activating
    a same-named label or static text node.
    """
    try:
        from gi.repository import Atspi
        component = node.get_component_iface()
        rect = component.get_extents(Atspi.CoordType.SCREEN) if component else None
        if not rect or rect.width <= 0 or rect.height <= 0:
            print(f"ERROR: Element '{name}' has invalid editable bbox; refusing coordinate focus", file=sys.stderr)
            sys.exit(1)
        if not (allow_coordinate or os.environ.get('DESKTOP_ALLOW_COORDINATE_CLICK') == '1'):
            print(
                f"ERROR: Element '{name}' requires coordinate fallback at "
                f"({rect.x + rect.width // 2}, {rect.y + rect.height // 2}). "
                "Re-run with --allow-coordinate after verifying the target.",
                file=sys.stderr,
            )
            sys.exit(1)
        x = rect.x + rect.width // 2
        y = rect.y + rect.height // 2
        # A newly opened or just force-cleaned browser window may consume the
        # first click for window activation; repeat keeps the caret placement
        # deterministic for editable targets while still using the verified bbox.
        human_input.click_at(x, y, button=1, repeat=2, delay_ms=90)
        print(f"Focused editable '{name}' at ({x}, {y})")
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: Could not focus editable '{name}': {exc}", file=sys.stderr)
        sys.exit(1)


def type_text(text, into_element=None, allow_coordinate=False, clear=False, verify=False):
    """Type text with human-paced timing. Log is masked for security."""
    if into_element:
        from .atspi_engine import click, _find_node
        # Labels and editable controls often share the same accessible name in
        # browsers. Prefer editable roles for type targets so --into "Name"
        # focuses the input, not its label. Fall back to generic matching for
        # non-browser widgets that expose a different role.
        clicked = False
        for preferred_role in ('entry', 'password text', 'text'):
            node, _ = _find_node(into_element, role_filter=preferred_role)
            if node:
                _focus_editable_node(node, into_element, allow_coordinate=allow_coordinate)
                clicked = True
                break
        if not clicked:
            click(into_element, allow_coordinate=allow_coordinate)
        time.sleep(0.2)

    if clear:
        human_input.press_key('ctrl+a')
        human_input.press_key('BackSpace')
        time.sleep(0.1)

    human_input.type_text(text)
    target = f" into '{into_element}'" if into_element else ""
    print(f"Typed [{len(text)} chars]{target}")

    if verify and into_element:
        try:
            from .atspi_engine import read_element_value
            current = read_element_value(into_element, prefer_roles=('entry', 'password text', 'text'))
            if current is not None and current != text:
                print(f"WARNING: typed field verification mismatch for '{into_element}'", file=sys.stderr)
        except Exception:
            pass


def press_key(key_combo):
    """Press a key combination. Log is masked."""
    key_map = {
        'enter': 'Return', 'esc': 'Escape', 'escape': 'Escape',
        'tab': 'Tab', 'space': 'space', 'backspace': 'BackSpace',
        'delete': 'Delete', 'home': 'Home', 'end': 'End',
        'pageup': 'Page_Up', 'pagedown': 'Page_Down',
        'up': 'Up', 'down': 'Down', 'left': 'Left', 'right': 'Right',
        'f1': 'F1', 'f2': 'F2', 'f3': 'F3', 'f4': 'F4',
        'f5': 'F5', 'f6': 'F6', 'f7': 'F7', 'f8': 'F8',
        'f9': 'F9', 'f10': 'F10', 'f11': 'F11', 'f12': 'F12',
    }

    parts = key_combo.split('+')
    mapped = []
    for p in parts:
        low = p.strip().lower()
        mapped.append(key_map.get(low, p.strip()))

    combo = '+'.join(mapped)
    human_input.press_key(combo)
    # Log key combo (safe — no sensitive content in key combos)
    print(f"Pressed: {key_combo}")


def scroll(direction, amount=3):
    """Scroll up/down by amount."""
    button = '4' if direction == 'up' else '5'
    for _ in range(int(amount)):
        human_input.pause('before')
        _run_xdotool('click', button)
        human_input.pause('after')
    print(f"Scrolled {direction} {amount} clicks")


def screenshot(output_path=None):
    """Take a screenshot."""
    if output_path is None:
        output_path = '/tmp/desktop_screenshot.png'

    for cmd in [
        ['scrot', output_path],
        ['import', '-window', 'root', output_path],
    ]:
        try:
            result = subprocess.run(cmd, env=_ENV, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"Screenshot saved: {output_path}")
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    try:
        xwd = subprocess.Popen(
            ['xwd', '-root', '-display', ':99'],
            env=_ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        convert = subprocess.Popen(
            ['convert', 'xwd:-', output_path],
            env=_ENV, stdin=xwd.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if xwd.stdout:
            xwd.stdout.close()
        _, convert_err = convert.communicate(timeout=10)
        _, xwd_err = xwd.communicate(timeout=2)
        if convert.returncode == 0 and xwd.returncode == 0:
            print(f"Screenshot saved: {output_path}")
            return
        err = (convert_err or xwd_err or b'').decode(errors='replace')
        raise RuntimeError(err.strip() or 'xwd/convert failed')
    except Exception as e:
        try:
            xwd.kill()
        except Exception:
            pass
        try:
            convert.kill()
        except Exception:
            pass
        print(f"ERROR: Could not take screenshot: {e}", file=sys.stderr)
        sys.exit(1)
