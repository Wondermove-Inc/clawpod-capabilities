"""Structured recording for desktop computer-use runs."""

import json
import os
import time
import uuid
from datetime import datetime, timezone


def new_run_dir(base='/workspace/desktop-runs'):
    run_id = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    path = os.path.join(base, run_id)
    os.makedirs(path, exist_ok=True)
    return path


def append_event(run_dir, kind, data=None):
    if not run_dir:
        return
    os.makedirs(run_dir, exist_ok=True)
    event = {
        'ts': time.time(),
        'iso': datetime.now(timezone.utc).isoformat(),
        'pid': os.getpid(),
        'kind': kind,
        'data': data or {},
    }
    with open(os.path.join(run_dir, 'events.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + '\n')


def write_json(run_dir, name, data):
    os.makedirs(run_dir, exist_ok=True)
    path = os.path.join(run_dir, name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    return path
