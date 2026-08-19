"""Human-verification detection for safe browser computer use.

This module does not solve, bypass, or automate CAPTCHA/bot checks. It detects
human-verification screens and raises a stop condition so a human can intervene.
"""

import json
import re
import sys

from .exit_codes import EXIT_NOT_FOUND
from . import atspi_engine

HUMAN_VERIFICATION_RE = re.compile(
    r'(captcha|recaptcha|hcaptcha|turnstile|cloudflare|verify you are human|'
    r'are you human|human verification|bot detection|security check|'
    r'checking your browser|unusual traffic|automated queries|로봇|사람인지|인증|보안 확인)',
    re.I,
)


def detect_in_observation(observation):
    hits = []
    for node in observation.get('nodes') or []:
        text = ' '.join(str(node.get(k) or '') for k in ('name', 'text', 'role', 'app'))
        if HUMAN_VERIFICATION_RE.search(text):
            hits.append({
                'id': node.get('id'),
                'app': node.get('app'),
                'role': node.get('role'),
                'name': node.get('name'),
                'bbox': node.get('bbox'),
            })
    active = observation.get('active_window') or {}
    if HUMAN_VERIFICATION_RE.search(str(active.get('title') or '')):
        hits.append({'id': 'active_window', 'role': 'window', 'name': active.get('title')})
    return hits


def detect_current_accessibility(app_name=None):
    hits = []
    desktop = atspi_engine.get_desktop()
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if not app:
            continue
        aname = app.get_name() or ''
        if app_name and app_name.lower() not in aname.lower():
            continue
        for node in atspi_engine._walk_tree_nodes(app, max_depth=20):
            try:
                role = node.get_role_name()
                name = node.get_name() or ''
                # Chromium exposes names of background tabs as "page tab" nodes.
                # They are useful UI chrome, but treating stale hidden tab titles
                # as the current page creates false stops for local benchmarks.
                # Active/visible page content is still covered by observations.
                if role.lower() == 'page tab':
                    continue
                text = name
                try:
                    text_iface = node.get_text_iface()
                    if text_iface:
                        n = min(text_iface.get_character_count(), 500)
                        if n > 0:
                            text += ' ' + text_iface.get_text(0, n)
                except Exception:
                    pass
                if HUMAN_VERIFICATION_RE.search(text):
                    hits.append({'app': aname, 'role': role, 'name': name or text[:120]})
            except Exception:
                continue
    return hits


def assert_no_human_verification(observation, as_json=False, app_name=None):
    hits = detect_in_observation(observation)
    hits.extend(detect_current_accessibility(app_name=app_name))
    result = {
        'type': 'human_verification_detected',
        'passed': not hits,
        'requiresHuman': bool(hits),
        'hits': hits[:20],
        'message': 'Human verification detected; stop automation and request human intervention.' if hits else 'No human verification detected.',
    }
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        status = 'PASS' if result['passed'] else 'STOP'
        print(f"{status}: {result['message']}")
    if hits:
        sys.exit(EXIT_NOT_FOUND)
    return result
