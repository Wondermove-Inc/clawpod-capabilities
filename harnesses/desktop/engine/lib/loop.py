"""Task runner for desktop computer-use YAML/JSON specs."""

import json
import os
import sys
import time

try:
    import yaml
except Exception:
    yaml = None

from .actions import execute_action
from .observation import build_observation
from .recorder import append_event, new_run_dir, write_json
from .verify import verify_text, verify_active, verify_file
from .safety import load_policy
from .human_verification import assert_no_human_verification


def _load_spec(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    if path.endswith('.json'):
        return json.loads(text)
    if yaml:
        return yaml.safe_load(text)
    return json.loads(text)


def run_task(spec_path, record_dir=None, allow_coordinate=False, approve_sensitive=False, force=False, policy_path=None):
    spec = _load_spec(spec_path)
    policy = load_policy(policy_path)
    record_dir = record_dir or new_run_dir()
    append_event(record_dir, 'task_start', {'spec': spec_path, 'goal': spec.get('goal'), 'maxSteps': spec.get('maxSteps') or spec.get('max_steps')})
    steps = spec.get('steps') or []
    max_steps = int(spec.get('maxSteps') or spec.get('max_steps') or len(steps) or 1)
    if len(steps) > max_steps:
        raise RuntimeError(f'step count {len(steps)} exceeds maxSteps {max_steps}')
    default_retries = int(spec.get('retry') or spec.get('retries') or spec.get('retryBudget') or 0)
    for idx, step in enumerate(steps, start=1):
        retries = int(step.get('retry') or step.get('retries') or default_retries)
        attempt = 0
        while True:
            attempt += 1
            started = time.time()
            try:
                before_name = f'{idx:03d}-attempt{attempt}-before'
                after_name = f'{idx:03d}-attempt{attempt}-after'
                before = build_observation(screenshot_path=os.path.join(record_dir, f'{before_name}.png'), max_depth=int(step.get('observeDepth', 2)))
                write_json(record_dir, f'{before_name}.json', before)
                append_event(record_dir, 'step_before', {'idx': idx, 'attempt': attempt, 'action': step.get('action'), 'observation': f'{before_name}.json'})
                if step.get('stopOnHumanVerification', True):
                    assert_no_human_verification(before, as_json=False, app_name=(step.get('app') or (step.get('action') or {}).get('app')))
                append_event(record_dir, 'action_start', {'idx': idx, 'attempt': attempt, 'action': step.get('action')})
                execute_action(step['action'], allow_coordinate=allow_coordinate, approve_sensitive=approve_sensitive, force=force, policy=policy)
                append_event(record_dir, 'action_done', {'idx': idx, 'attempt': attempt, 'elapsedMs': int((time.time() - started) * 1000)})
                after = build_observation(screenshot_path=os.path.join(record_dir, f'{after_name}.png'), max_depth=int(step.get('observeDepth', 2)))
                write_json(record_dir, f'{after_name}.json', after)
                if step.get('stopOnHumanVerification', True):
                    assert_no_human_verification(after, as_json=False, app_name=(step.get('app') or (step.get('action') or {}).get('app')))
                _run_verification(step.get('verify') or {}, record_dir, idx)
                append_event(record_dir, 'step_pass', {'idx': idx, 'attempt': attempt, 'elapsedMs': int((time.time() - started) * 1000), 'observation': f'{after_name}.json'})
                break
            except SystemExit as exc:
                append_event(record_dir, 'step_fail', {'idx': idx, 'attempt': attempt, 'exit': exc.code, 'elapsedMs': int((time.time() - started) * 1000)})
                if attempt <= retries:
                    _record_recovery_observation(record_dir, idx, attempt, step)
                    continue
                raise
            except Exception as exc:
                append_event(record_dir, 'step_fail', {'idx': idx, 'attempt': attempt, 'error': str(exc), 'errorType': type(exc).__name__, 'elapsedMs': int((time.time() - started) * 1000)})
                if attempt <= retries:
                    _record_recovery_observation(record_dir, idx, attempt, step)
                    continue
                raise
    append_event(record_dir, 'task_pass', {'steps': len(steps)})
    print(f'RUN_TASK_OK {record_dir}')


def _record_recovery_observation(record_dir, idx, attempt, step):
    name = f'{idx:03d}-attempt{attempt}-recovery'
    obs = build_observation(screenshot_path=os.path.join(record_dir, f'{name}.png'), max_depth=int(step.get('recoveryObserveDepth', step.get('observeDepth', 2))))
    write_json(record_dir, f'{name}.json', obs)
    append_event(record_dir, 'step_recovery_observation', {'idx': idx, 'attempt': attempt, 'observation': f'{name}.json', 'warnings': obs.get('warnings', [])})


def _run_verification(verify, record_dir, idx):
    if not verify:
        return
    append_event(record_dir, 'verify_start', {'idx': idx, 'verify': verify})
    typ = verify.get('type')
    if typ in ('text', 'text_exists'):
        verify_text(verify['text'], app_name=verify.get('app'), timeout=int(verify.get('timeout', 0)), gone=False, as_json=True)
    elif typ == 'text_gone':
        verify_text(verify['text'], app_name=verify.get('app'), timeout=int(verify.get('timeout', 0)), gone=True, as_json=True)
    elif typ == 'active':
        verify_active(verify.get('title'), as_json=True)
    elif typ == 'file':
        verify_file(verify['path'], nonempty=bool(verify.get('nonempty', False)), as_json=True)
    elif typ == 'human_check':
        obs = build_observation(screenshot_path=os.path.join(record_dir, f'{idx:03d}-verify-human.png'), max_depth=int(verify.get('observeDepth', 2)))
        write_json(record_dir, f'{idx:03d}-verify-human.json', obs)
        assert_no_human_verification(obs, as_json=True, app_name=verify.get('app'))
    else:
        raise ValueError(f'unknown verification type: {typ}')
