"""Application launch/close/focus manager with accessibility auto-config."""

import os
import shlex
import subprocess
import sys
import time

os.environ.setdefault('DISPLAY', ':99')

from .exit_codes import EXIT_APP_FAIL

_ENV = {**os.environ, 'DISPLAY': ':99'}

_APP_ALIASES = {
    'browser': 'chromium', 'chrome': 'chromium', 'chromium': 'chromium',
    'firefox': 'firefox',
    'vscode': 'code', 'code': 'code',
    'terminal': 'xfce4-terminal', 'term': 'xfce4-terminal',
    'files': 'thunar', 'filemanager': 'thunar', 'thunar': 'thunar',
    'calc': 'libreoffice --calc', 'writer': 'libreoffice --writer',
    'impress': 'libreoffice --impress', 'draw': 'libreoffice --draw',
    'gimp': 'gimp', 'inkscape': 'inkscape',
}

_ACCESSIBILITY_FLAGS = {
    # Keep renderer accessibility enabled and suppress stale-session UI that can
    # steal focus/intercept form-entry stress tests after forced cleanup.
    'chromium': ['--force-renderer-accessibility', '--no-first-run', '--disable-session-crashed-bubble'],
}


def _process_name_for(app_name):
    app_lower = (app_name or '').lower()
    cmd_base = _APP_ALIASES.get(app_lower, app_name or '')
    return os.path.basename(cmd_base.split()[0]) if cmd_base else ''


def _ensure_vscode_accessibility():
    """Configure VS Code accessibility settings."""
    import json
    settings_dir = os.path.expanduser('~/.config/Code/User')
    settings_file = os.path.join(settings_dir, 'settings.json')
    settings = {}
    if os.path.exists(settings_file):
        try:
            with open(settings_file) as f:
                settings = json.load(f)
        except Exception:
            pass
    if settings.get('accessibility.support') != 'on':
        settings['accessibility.support'] = 'on'
        os.makedirs(settings_dir, exist_ok=True)
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)


def _wait_for_window(app_name, timeout=10, aliases=None):
    """Wait for app window to appear in AT-SPI, up to timeout seconds."""
    names = [app_name] + list(aliases or [])
    start = time.time()
    while time.time() - start < timeout:
        for name in names:
            try:
                result = subprocess.run(
                    ['xdotool', 'search', '--name', name],
                    capture_output=True, text=True, env=_ENV
                )
                if result.stdout.strip():
                    return True
            except Exception:
                pass
        try:
            from .atspi_engine import list_apps, get_desktop
            desktop = get_desktop()
            for i in range(desktop.get_child_count()):
                app = desktop.get_child_at_index(i)
                aname = (app.get_name() or '').lower() if app else ''
                if any(name.lower() in aname for name in names):
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def open_app(app_name, *args):
    """Open an application with accessibility auto-config.
    Waits up to 10s for window to appear."""
    app_lower = app_name.lower()
    cmd_base = _APP_ALIASES.get(app_lower, app_name)
    cmd_parts = cmd_base.split()
    cmd = cmd_parts[0]

    if cmd == 'code':
        _ensure_vscode_accessibility()

    env = dict(_ENV)
    env['QT_ACCESSIBILITY'] = '1'
    env['GTK_MODULES'] = 'gail:atk-bridge'

    extra_flags = _ACCESSIBILITY_FLAGS.get(cmd, [])
    full_cmd = cmd_parts + extra_flags + list(args)

    if app_lower == 'browser' and args:
        url = args[0]
        if not url.startswith(('http://', 'https://', 'file://')):
            url = 'https://' + url
        full_cmd = cmd_parts + extra_flags + [url]

    if app_lower == 'file' and args:
        full_cmd = ['xdg-open'] + list(args)

    wait_aliases = []

    if app_lower in ('terminal', 'term'):
        wait_aliases = ['Terminal', 'xfce4-terminal']
        if args:
            user_cmd = ' '.join(args)
            # Run through a shell inside the terminal so quoting, semicolons, and
            # simple sentinel commands behave the way users expect.
            full_cmd = [cmd, '--command', f"bash -lc {shlex.quote(user_cmd)}"]

    try:
        subprocess.Popen(
            full_cmd, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        print(f"Launched: {' '.join(full_cmd)}")

        # Wait for window to appear
        search_name = app_name if app_lower not in _APP_ALIASES else cmd
        if _wait_for_window(search_name, aliases=wait_aliases):
            print(f"Window ready: {app_name}")
        else:
            print(f"WARNING: Window not detected after 10s (app may still be loading)")
            if app_lower in ('terminal', 'term') and args:
                print("HINT: terminal command launch was not detected; retry with `desktop open terminal`, then `desktop type ...` and `desktop key enter` for visible terminal workflows")

    except FileNotFoundError:
        print(f"ERROR: '{cmd}' not found. Is it installed?", file=sys.stderr)
        sys.exit(EXIT_APP_FAIL)
    except Exception as e:
        print(f"ERROR: Could not open '{app_name}': {e}", file=sys.stderr)
        sys.exit(EXIT_APP_FAIL)


def close_app(app_name=None, force=False):
    """Close active window or a specific app."""
    if app_name:
        try:
            result = subprocess.run(
                ['xdotool', 'search', '--name', app_name],
                capture_output=True, text=True, env=_ENV, timeout=3
            )
            windows = [w for w in result.stdout.strip().split('\n') if w]
            closed = 0
            for wid in windows:
                try:
                    subprocess.run(['xdotool', 'windowclose', wid], env=_ENV, timeout=3)
                    closed += 1
                except subprocess.TimeoutExpired:
                    # WM hang — try alt+F4 fallback
                    try:
                        subprocess.run(['xdotool', 'windowactivate', wid], env=_ENV, timeout=2)
                        subprocess.run(['xdotool', 'key', 'alt+F4'], env=_ENV, timeout=2)
                        closed += 1
                    except (subprocess.TimeoutExpired, Exception):
                        pass
            if closed:
                print(f"Closed {closed} window(s) for '{app_name}'")
                if force:
                    proc_name = _process_name_for(app_name)
                    if proc_name:
                        time.sleep(0.5)
                        subprocess.run(['pkill', '-x', proc_name], timeout=3)
                        print(f"Killed process: {proc_name}")
            else:
                proc_name = _process_name_for(app_name)
                if force and proc_name:
                    subprocess.run(['pkill', '-x', proc_name], timeout=3)
                    print(f"Killed process: {proc_name}")
                else:
                    print(
                        f"WARNING: No windows found for '{app_name}'. "
                        "Process kill skipped; re-run with --force to kill by process name."
                    )
        except subprocess.TimeoutExpired:
            proc_name = _process_name_for(app_name)
            if force and proc_name:
                subprocess.run(['pkill', '-x', proc_name], timeout=3)
                print(f"Killed process (timeout): {proc_name}")
            else:
                print(
                    f"WARNING: Window close timed out for '{app_name}'. "
                    "Process kill skipped; re-run with --force to kill by process name."
                )
        except Exception as e:
            print(f"ERROR: Could not close '{app_name}': {e}", file=sys.stderr)
            sys.exit(EXIT_APP_FAIL)
    else:
        try:
            subprocess.run(['xdotool', 'getactivewindow', 'windowclose'], env=_ENV, check=True)
            print("Closed active window")
        except Exception:
            print("ERROR: No active window to close", file=sys.stderr)
            sys.exit(EXIT_APP_FAIL)
