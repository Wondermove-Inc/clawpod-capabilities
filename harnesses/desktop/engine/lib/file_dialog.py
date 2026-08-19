"""File-chooser dialog driving: file-dialog-open/save/choose-directory/cancel
and dialog-respond.

Hybrid, portal-aware: a file chooser reaches the screen either as an app-native
GTK dialog or as one rendered by xdg-desktop-portal-gtk. Both expose the same
AT-SPI structure and the same GTK "type a location" affordance, so this module
detects and verifies the live dialog through AT-SPI (never acting blindly on the
wrong window), then drives it: Ctrl+L to open the location entry, type the path,
and confirm through the dialog's accessible default button when found, falling
back to Return. Cancel uses the accessible Cancel button or Escape.

Requires an active graphical session (DISPLAY + AT-SPI). The contract layer
(desktop.py) additionally gates these as portal actions on DBUS_SESSION_BUS_ADDRESS.
"""

import os
import sys
import time

os.environ.setdefault('DISPLAY', ':99')

# AT-SPI role names that can host a file chooser / confirmation dialog.
_DIALOG_ROLES = ('file chooser', 'dialog', 'alert', 'frame')
# Accessible names (accelerator underscores stripped) treated as confirm/cancel.
_CONFIRM_NAMES = ('open', 'save', 'select', 'choose', 'ok', 'yes', 'apply')
_CANCEL_NAMES = ('cancel', 'close', 'no')


def _atspi():
    try:
        import gi
        gi.require_version('Atspi', '2.0')
        from gi.repository import Atspi
        return Atspi
    except (ImportError, ValueError) as e:
        print(f"ERROR: AT-SPI unavailable: {e}", file=sys.stderr)
        sys.exit(1)


def _norm(name):
    return (name or '').replace('_', '').strip().lower()


def _iter_children(node):
    try:
        for i in range(node.get_child_count()):
            child = node.get_child_at_index(i)
            if child is not None:
                yield child
    except Exception:
        return


def _find_active_dialog(timeout=5.0):
    """Return the top-most active dialog/file-chooser node, or None.

    Prefers a MODAL/ACTIVE dialog; falls back to any showing file-chooser role.
    Retries briefly because a just-opened dialog may still be mapping.
    """
    from .atspi_engine import get_desktop
    Atspi = _atspi()
    deadline = time.time() + timeout
    best = None
    while time.time() < deadline:
        desktop = get_desktop()
        for app in _iter_children(desktop):
            for win in _iter_children(app):
                try:
                    role = win.get_role_name()
                except Exception:
                    continue
                if role not in _DIALOG_ROLES:
                    continue
                try:
                    states = win.get_state_set()
                except Exception:
                    continue
                if not states.contains(Atspi.StateType.SHOWING):
                    continue
                modal = states.contains(Atspi.StateType.MODAL)
                active = states.contains(Atspi.StateType.ACTIVE)
                if role == 'file chooser' or modal or active:
                    if modal or active or role == 'file chooser':
                        return win
                    best = best or win
        if best:
            return best
        time.sleep(0.25)
    return best


def _descendant_buttons(node, out=None, depth=0):
    if out is None:
        out = []
    if depth > 6:
        return out
    for child in _iter_children(node):
        try:
            role = child.get_role_name()
        except Exception:
            continue
        if role in ('push button', 'button'):
            out.append(child)
        _descendant_buttons(child, out, depth + 1)
    return out


def _click_button(node):
    """Activate a button through AT-SPI action; return True on success."""
    Atspi = _atspi()
    try:
        action = node.get_action_iface()
        if action:
            for i in range(action.get_n_actions()):
                if action.get_action_name(i) in ('click', 'activate', 'press'):
                    return bool(action.do_action(i))
            if action.get_n_actions() > 0:
                return bool(action.do_action(0))
    except Exception:
        pass
    # Coordinate fallback on the button's accessible center.
    try:
        from . import human_input
        comp = node.get_component_iface()
        rect = comp.get_extents(Atspi.CoordType.SCREEN) if comp else None
        if rect and rect.width > 0 and rect.height > 0:
            human_input.click_at(rect.x + rect.width // 2, rect.y + rect.height // 2, button=1)
            return True
    except Exception:
        pass
    return False


def _confirm(dialog, names):
    """Click the first button whose accessible name matches `names`."""
    for btn in _descendant_buttons(dialog):
        try:
            if _norm(btn.get_name()) in names:
                if _click_button(btn):
                    return True
        except Exception:
            continue
    return False


def _require_dialog():
    dialog = _find_active_dialog()
    if dialog is None:
        print("ERROR: no active file/confirmation dialog found on screen", file=sys.stderr)
        sys.exit(1)
    return dialog


def _enter_path(path):
    """Focus a dialog's location entry (Ctrl+L) and type the path."""
    if not path:
        print("ERROR: a path argument is required", file=sys.stderr)
        sys.exit(1)
    from .xdotool_engine import press_key, type_text
    press_key('ctrl+l')
    time.sleep(0.2)
    type_text(path)
    time.sleep(0.2)


def _open_like(path, names):
    _require_dialog()
    _enter_path(path)
    dialog = _find_active_dialog(timeout=2.0) or _require_dialog()
    if _confirm(dialog, names):
        print(f"Dialog confirmed with path: {path}")
        return
    # Keyboard fallback: Return activates the GTK default (Open/Save) button.
    from .xdotool_engine import press_key
    press_key('Return')
    print(f"Dialog confirmed via Return with path: {path}")


def open(path):
    _open_like(path, _CONFIRM_NAMES)


def save(path):
    _open_like(path, _CONFIRM_NAMES)


def choose_directory(path):
    _open_like(path, _CONFIRM_NAMES)


def cancel():
    dialog = _require_dialog()
    if _confirm(dialog, _CANCEL_NAMES):
        print("Dialog cancelled")
        return
    from .xdotool_engine import press_key
    press_key('Escape')
    print("Dialog cancelled via Escape")


def respond(button):
    """Click a named button in the active dialog (e.g. 'OK', 'Yes', 'Discard')."""
    if not button:
        print("ERROR: dialog-respond requires a button label", file=sys.stderr)
        sys.exit(1)
    dialog = _require_dialog()
    target = _norm(button)
    for btn in _descendant_buttons(dialog):
        try:
            if _norm(btn.get_name()) == target:
                if _click_button(btn):
                    print(f"Dialog button clicked: {button}")
                    return
        except Exception:
            continue
    print(f"ERROR: button '{button}' not found in active dialog", file=sys.stderr)
    sys.exit(1)
