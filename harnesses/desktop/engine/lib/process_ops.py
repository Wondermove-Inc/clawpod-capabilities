"""Process control: process-terminate (SIGTERM) / process-kill (SIGKILL).

Guards refuse to signal PID 1, this process's own tree, and any process whose
command matches a critical-infrastructure denylist (X server, D-Bus, AT-SPI,
the OpenClaw gateway, the container entrypoint). The agent may stop GUI apps it
launched, never the session that hosts it.
"""

import os
import signal
import sys

# Substrings that mark a process as session-critical; matched against the
# process's /proc/<pid>/comm and cmdline (case-insensitive).
_PROTECTED = (
    'xvfb', 'dbus-daemon', 'dbus-launch', 'at-spi', 'at-spi2',
    'openclaw', 'gateway', 'entrypoint', 'systemd', 'init',
    'xdg-desktop-portal', 'xfwm4', 'xfce4-session', 'openbox',
)


def _proc_text(pid):
    """Lowercased comm + cmdline for a pid, or '' if it cannot be read."""
    parts = []
    for name in ('comm', 'cmdline'):
        try:
            with open(f'/proc/{pid}/{name}', 'rb') as f:
                parts.append(f.read().replace(b'\x00', b' ').decode('utf-8', 'replace'))
        except OSError:
            pass
    return ' '.join(parts).lower()


def _guarded_pid(raw):
    if raw is None:
        print("ERROR: process signal requires <pid>", file=sys.stderr)
        sys.exit(1)
    try:
        pid = int(raw)
    except (TypeError, ValueError):
        print(f"ERROR: invalid pid {raw!r}", file=sys.stderr)
        sys.exit(1)
    if pid <= 1:
        print(f"ERROR: refusing to signal pid {pid} (reserved)", file=sys.stderr)
        sys.exit(1)
    if pid in (os.getpid(), os.getppid()):
        print(f"ERROR: refusing to signal own process tree (pid {pid})", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(f'/proc/{pid}'):
        print(f"ERROR: no such process {pid}", file=sys.stderr)
        sys.exit(1)
    text = _proc_text(pid)
    for marker in _PROTECTED:
        if marker in text:
            print(f"ERROR: refusing to signal session-critical process {pid} ({marker})", file=sys.stderr)
            sys.exit(1)
    return pid


def _send(pid, sig, label):
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        print(f"ERROR: no such process {pid}", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"ERROR: not permitted to signal process {pid}", file=sys.stderr)
        sys.exit(1)
    print(f"Sent {label} to process {pid}")


def terminate(pid):
    _send(_guarded_pid(pid), signal.SIGTERM, "SIGTERM")


def kill(pid):
    _send(_guarded_pid(pid), signal.SIGKILL, "SIGKILL")
