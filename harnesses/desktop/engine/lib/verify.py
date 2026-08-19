"""Verification predicates for desktop computer-use."""

import json
import os
import sys
import time

from . import atspi_engine
from .exit_codes import EXIT_TIMEOUT, EXIT_NOT_FOUND


def verify_text(text, app_name=None, timeout=0, gone=False, as_json=False):
    start = time.time()
    passed = False
    while True:
        node, _ = atspi_engine._find_node(text, app_name=app_name)
        exists = node is not None
        passed = (not exists) if gone else exists
        if passed or timeout <= 0 or time.time() - start >= timeout:
            break
        time.sleep(0.5)
    result = {
        'type': 'text_gone' if gone else 'text_exists',
        'text': text,
        'app': app_name,
        'passed': passed,
        'elapsed': round(time.time() - start, 3),
    }
    _emit(result, as_json)
    if not passed:
        sys.exit(EXIT_TIMEOUT if timeout else EXIT_NOT_FOUND)


def verify_active(title=None, as_json=False):
    import subprocess
    result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], capture_output=True, text=True, env={**os.environ, 'DISPLAY': ':99'})
    active = result.stdout.strip() if result.returncode == 0 else ''
    passed = bool(active) if title is None else title.lower() in active.lower()
    payload = {'type': 'active_window', 'expected': title, 'active': active, 'passed': passed}
    _emit(payload, as_json)
    if not passed:
        sys.exit(EXIT_NOT_FOUND)


def verify_file(path, nonempty=False, as_json=False):
    exists = os.path.exists(path)
    passed = exists and ((not nonempty) or os.path.getsize(path) > 0)
    payload = {'type': 'file_exists', 'path': path, 'nonempty': nonempty, 'passed': passed}
    _emit(payload, as_json)
    if not passed:
        sys.exit(EXIT_NOT_FOUND)


def _emit(payload, as_json=False):
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(('PASS' if payload.get('passed') else 'FAIL') + ': ' + json.dumps(payload, ensure_ascii=False))
