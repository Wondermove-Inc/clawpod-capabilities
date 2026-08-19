"""Clipboard read/write/clear via Gtk.Clipboard (no xclip/xsel dependency).

Uses the GTK3 CLIPBOARD selection. After a write we call store() so a running
clipboard manager (xfce4-clipman in the XFCE session) keeps the value once this
short-lived process exits, then pump the GLib loop briefly to flush the request.
"""

import os
import sys

os.environ.setdefault('DISPLAY', ':99')


def _clipboard():
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk, Gdk
    except (ImportError, ValueError) as e:
        print(f"ERROR: GTK clipboard unavailable: {e}", file=sys.stderr)
        sys.exit(1)
    display = Gdk.Display.get_default()
    if display is None:
        print("ERROR: no X display for clipboard (is DISPLAY set?)", file=sys.stderr)
        sys.exit(1)
    # GTK3: the clipboard is Gtk.Clipboard.get(selection); Gdk.Clipboard is GTK4.
    return Gtk, Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)


def _pump(Gtk, iterations=50):
    """Flush pending GTK events so set/store/read actually complete."""
    count = 0
    while Gtk.events_pending() and count < iterations:
        Gtk.main_iteration_do(False)
        count += 1


def read():
    Gtk, cb = _clipboard()
    text = cb.wait_for_text()
    _pump(Gtk)
    if text is None:
        # Empty vs unavailable: an empty clipboard yields None too; report empty.
        print("")
        return
    sys.stdout.write(text)
    if not text.endswith('\n'):
        sys.stdout.write('\n')


def write(text):
    if text is None:
        print("ERROR: clipboard-write requires <text>", file=sys.stderr)
        sys.exit(1)
    Gtk, cb = _clipboard()
    cb.set_text(text, -1)
    cb.store()
    _pump(Gtk)
    print(f"Clipboard set ({len(text)} chars)")


def clear():
    Gtk, cb = _clipboard()
    cb.set_text('', -1)
    cb.store()
    _pump(Gtk)
    print("Clipboard cleared")
