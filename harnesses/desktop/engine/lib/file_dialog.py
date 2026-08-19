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
# 'frame' is intentionally excluded: the root desktop is a frame, and matching it
# would mistake the background for a dialog.
_DIALOG_ROLES = ('file chooser', 'dialog', 'alert')
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
    """Return the most likely active dialog/file-chooser node, or None.

    A SHOWING dialog/file-chooser/alert qualifies even when AT-SPI does not mark
    it MODAL/ACTIVE — Zenity's GtkFileChooserDialog, for example, exposes only
    SHOWING+VISIBLE. MODAL/ACTIVE/FOCUSED and the file-chooser role only raise a
    candidate's priority so the front-most dialog wins when several are open.
    Retries briefly because a just-opened dialog may still be mapping.
    """
    from .atspi_engine import get_desktop
    Atspi = _atspi()
    deadline = time.time() + timeout
    while True:
        candidates = []
        desktop = get_desktop()
        for app in _iter_children(desktop):
            for win in _iter_children(app):
                try:
                    role = win.get_role_name()
                    states = win.get_state_set()
                except Exception:
                    continue
                if role not in _DIALOG_ROLES:
                    continue
                if not states.contains(Atspi.StateType.SHOWING):
                    continue
                pri = 0
                if role == 'file chooser':
                    pri += 4
                if states.contains(Atspi.StateType.MODAL):
                    pri += 2
                if states.contains(Atspi.StateType.ACTIVE):
                    pri += 1
                if states.contains(Atspi.StateType.FOCUSED):
                    pri += 1
                candidates.append((pri, win))
        if candidates:
            # Highest priority wins; among ties, the last-enumerated (most
            # recently mapped) window is the front-most in practice.
            candidates.sort(key=lambda c: c[0])
            return candidates[-1][1]
        if time.time() >= deadline:
            return None
        time.sleep(0.25)


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


def _set_clipboard(text):
    """Put text on the CLIPBOARD selection so it can be pasted atomically."""
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk
    cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    cb.set_text(text, -1)
    cb.store()
    n = 0
    while Gtk.events_pending() and n < 50:
        Gtk.main_iteration_do(False)
        n += 1


def _enter_path(path):
    """Put `path` into a GTK file chooser's location entry.

    Typing the path character by character races the location entry's
    autocompletion and corrupts the tail (e.g. `/a/b.txt` -> `/a/b.txtt.txt`).
    Instead: press `/` to open the GTK location popup, select-all, and paste the
    path from the clipboard in one atomic step — no per-character autocomplete.
    """
    if not path:
        print("ERROR: a path argument is required", file=sys.stderr)
        sys.exit(1)
    from .xdotool_engine import press_key
    _set_clipboard(path)
    press_key('slash')     # open the GTK location popup (its content becomes "/")
    time.sleep(0.4)
    press_key('ctrl+a')    # select the existing content
    time.sleep(0.1)
    press_key('ctrl+v')    # paste the full path atomically
    time.sleep(0.3)


def _dialog_gone(checks=3, gap=0.3):
    """True only if no dialog is found across several consecutive polls — guards
    against a transient AT-SPI miss being mistaken for a confirmed dialog."""
    for _ in range(checks):
        if _find_active_dialog(timeout=0.2) is not None:
            return False
        time.sleep(gap)
    return True


def _open_like(path, names):
    _require_dialog()
    _enter_path(path)
    from .xdotool_engine import press_key
    press_key('Return')    # commit the location entry (confirms for a file path)
    time.sleep(0.5)
    if _dialog_gone():
        print(f"Dialog confirmed with path: {path}")
        return
    # Still open (e.g. a directory chooser that navigated into the path): click
    # the accessible confirm button, then re-verify it actually closed.
    dialog = _find_active_dialog(timeout=1.0)
    if dialog is not None and _confirm(dialog, names) and _dialog_gone():
        print(f"Dialog confirmed with path: {path}")
        return
    print(f"ERROR: set path {path} but the dialog did not confirm", file=sys.stderr)
    sys.exit(1)


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


def inspect():
    """Report the active dialog's title, buttons, and text entries as JSON
    (dialog.inspect) — read-only, so an agent can decide how to respond."""
    import json
    dialog = _find_active_dialog()
    if dialog is None:
        print(json.dumps({'dialog': None}, separators=(',', ':')))
        return
    try:
        title = dialog.get_name()
        role = dialog.get_role_name()
    except Exception:
        title, role = '', 'dialog'
    buttons = []
    for btn in _descendant_buttons(dialog):
        try:
            name = btn.get_name()
            if name:
                buttons.append(name)
        except Exception:
            continue

    def _text_fields(node, out, depth=0):
        if depth > 6:
            return
        for child in _iter_children(node):
            try:
                r = child.get_role_name()
            except Exception:
                continue
            if r in ('text', 'entry', 'password text'):
                try:
                    out.append({'role': r, 'name': child.get_name() or ''})
                except Exception:
                    pass
            _text_fields(child, out, depth + 1)

    fields = []
    _text_fields(dialog, fields)
    print(json.dumps(
        {'dialog': {'title': title, 'role': role, 'buttons': buttons, 'fields': fields}},
        separators=(',', ':')))


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
