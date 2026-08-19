"""Safety gates for desktop computer-use actions."""

import json
import os
import re

SENSITIVE_TEXT = re.compile(r'\b(password|passwd|secret|token|api[_ -]?key|credit card|ssn|otp|2fa|private key)\b', re.I)
DANGEROUS_TEXT = re.compile(r'\b(delete|remove|rm\s+-|purchase|buy|submit|send|transfer|deploy|restart|shutdown|format|pay|curl\s|wget\s)\b', re.I)


def load_policy(path=None):
    path = path or os.environ.get('DESKTOP_POLICY')
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _flatten_action_text(action):
    values = []
    for key in ('kind', 'text', 'query', 'target', 'app', 'url', 'combo', 'into'):
        if action.get(key) is not None:
            values.append(str(action.get(key)))
    args = action.get('args')
    if isinstance(args, (list, tuple)):
        values.extend(str(x) for x in args)
    elif args is not None:
        values.append(str(args))
    fields = action.get('fields')
    if isinstance(fields, list):
        for field in fields:
            if isinstance(field, dict):
                values.extend(str(field.get(k, '')) for k in ('into', 'target', 'name', 'text'))
    return ' '.join(values)


def require_allowed_action(action, policy=None, allow_coordinate=False, approve_sensitive=False, force=False):
    policy = policy or {}
    kind = action.get('kind') or ''
    text = _flatten_action_text(action)
    if kind in ('click_xy', 'coordinate_click', 'click_image') and not allow_coordinate:
        raise PermissionError('coordinate click requires --allow-coordinate')
    if kind in ('force_close',) and not force:
        raise PermissionError('force close requires --force')
    if SENSITIVE_TEXT.search(text) and not approve_sensitive:
        raise PermissionError('sensitive text/action requires explicit approval')
    if DANGEROUS_TEXT.search(text) and not approve_sensitive:
        raise PermissionError('potentially destructive/external action requires explicit approval')
    allowed_apps = policy.get('allowedApps') or policy.get('allowed_apps')
    app = action.get('app')
    if allowed_apps and app and app not in allowed_apps:
        raise PermissionError(f'app {app!r} is not allowlisted')
    return True
