#!/usr/bin/env python3
"""Deterministic Track B closeout gate.

Reads a plain-text export of the practitioner start comment and completion
summary and fails when a required field is missing, left as an angle-bracket
template placeholder, or carries a non-referential evidence value.
"""
from pathlib import Path
import re
import sys

# Either name satisfies the scope requirement: the start-comment template uses
# understood_scope, the leader comment template uses scope.
REQUIRED_FIELDS = [
    ('leader_coordination_task_id',),
    ('execution_task_id',),
    ('understood_scope', 'scope'),
    ('context_validation',),
    ('pre_existing_modified_files',),
    ('planned_evidence',),
    ('result',),
    ('evidence',),
    ('blockers',),
    ('residual_risks',),
    ('next_responsible_role',),
]

FIELD_LINE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$')
PLACEHOLDER = re.compile(r'^<.*>$')


def parse(text):
    values = {}
    for line in text.splitlines():
        match = FIELD_LINE.match(line)
        if match:
            values.setdefault(match.group(1), []).append(match.group(2))
    return values


def is_filled(value):
    return bool(value) and not PLACEHOLDER.match(value)


def is_path_token(token):
    # A slash alone is not a reference: prose like "and/or" contains one. Require
    # a shape that only a path can plausibly have.
    if '/' not in token:
        return False
    return '.' in token or token.startswith('/') or token.count('/') >= 2


def is_evidence(value):
    if not is_filled(value):
        return False
    if value.strip().lower() == 'none':
        return False
    if '://' in value or '`' in value:
        return True
    return any(is_path_token(token) for token in value.split())


def check(values):
    failures = []
    for names in REQUIRED_FIELDS:
        validator = is_evidence if names[0] == 'evidence' else is_filled
        present = [v for name in names for v in values.get(name, [])]
        if not present:
            failures.append('MISSING ' + '/'.join(names))
        elif not any(validator(v) for v in present):
            failures.append('INVALID ' + '/'.join(names))
    return failures


def main(argv):
    if len(argv) != 2:
        print('usage: task-closeout-gate.py <closeout-report-path>')
        return 2
    report = Path(argv[1])
    if not report.is_file():
        print('MISSING report file: ' + str(report))
        return 1
    failures = check(parse(report.read_text(encoding='utf-8')))
    if failures:
        for failure in failures:
            print(failure)
        return 1
    print('PASS task closeout gate fields=' + str(len(REQUIRED_FIELDS)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
