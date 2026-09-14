"""Three-command app onboarding; no real Tailscale, node, or service changes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).parents[1]
CLI = ROOT / 'clawpod_node_host.py'


def call(tmp_path, command, *, state=None, env=None, extra=()):
    environment = dict(os.environ)
    environment.pop('CLAWPOD_NODE_HOST_FIXTURE', None)
    environment['CLAWPOD_NODE_HOST_RECORD'] = str(tmp_path / 'record.jsonl')
    if state is not None:
        fixture = tmp_path / 'fixture.json'
        fixture.write_text(json.dumps({'agentTailscale': state}))
        environment['CLAWPOD_NODE_HOST_FIXTURE'] = str(fixture)
    environment.update(env or {})
    result = subprocess.run([sys.executable, str(CLI), '--json', *command.split(), *extra],
                            cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=15)
    assert result.stdout.count('\n') == 1, result.stderr
    return result, json.loads(result.stdout)


def test_signin_handoff_recheck_then_computer_setup(tmp_path):
    needs = {'present': True, 'backendState': 'NeedsLogin', 'loginUrl': 'https://login.tailscale.com/a/example'}
    result, out = call(tmp_path, 'agent status', state=needs)
    assert result.returncode == 3 and out['nextAction']['resumeCommand'] == 'agent login'
    assert not (tmp_path / 'record.jsonl').exists()
    result, out = call(tmp_path, 'agent login', state=needs)
    assert result.returncode == 3 and not out['agentTailscale']['ready']
    assert out['agentTailscale']['url'] == needs['loginUrl']
    assert needs['loginUrl'] in out['nextAction']['message']
    assert out['nextAction']['resumeCommand'] == 'agent status'
    assert json.loads((tmp_path / 'record.jsonl').read_text())['argv'] == ['tailscale', 'login']
    result, out = call(tmp_path, 'agent status', state={'present': True, 'backendState': 'Running'})
    assert result.returncode == 0 and out['agentTailscale']['ready']
    assert out['nextAction']['step'] == 2 and out['nextAction']['resumeCommand'] is None


@pytest.mark.parametrize('command', ['agent status', 'agent login'])
def test_connected_agent_is_not_reauthenticated(tmp_path, command):
    result, out = call(tmp_path, command, state={'present': True, 'backendState': 'Running'})
    assert result.returncode == 0 and out['effects'] == []
    assert out['nextAction']['step'] == 2
    assert not (tmp_path / 'record.jsonl').exists()
    assert not {'service', 'version', 'plan', 'bootstrap'}.intersection(out)


@pytest.mark.parametrize('state', ['Stopped', 'NeedsMachineAuth', 'Starting', 'Unknown'])
@pytest.mark.parametrize('command', ['agent status', 'agent login'])
def test_non_login_states_do_not_start_new_signin(tmp_path, state, command):
    result, out = call(tmp_path, command, state={'present': True, 'backendState': state})
    assert result.returncode == 3 and out['nextAction']['step'] == 1
    assert out['nextAction']['resumeCommand'] == 'agent status'
    assert not (tmp_path / 'record.jsonl').exists()


@pytest.mark.parametrize('state,code', [({'present': False}, 'AGENT_TAILSCALE_ABSENT'),
    ({'present': True}, 'AGENT_TAILSCALE_STATUS_FAILED'),
    ({'backendState': True}, 'AGENT_TAILSCALE_STATUS_FAILED'),
    ({'backendState': 'NeedsLogin'}, 'LOGIN_URL_UNAVAILABLE')])
def test_missing_or_unusable_agent_state(tmp_path, state, code):
    result, out = call(tmp_path, 'agent login', state=state)
    assert result.returncode in {5, 6} and not out['ok']
    assert out['errors'][0]['code'] == code


def fake_tailscale(tmp_path):
    script = tmp_path / 'tailscale'
    script.write_text('#!' + sys.executable + '''
import json, os, sys, time
from pathlib import Path
with open(os.environ['FAKE_CALLS'], 'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1:] == ['status','--json']:
    print(os.environ.get('FAKE_STATUS','{"BackendState":"NeedsLogin"}'))
    sys.exit(int(os.environ.get('FAKE_STATUS_EXIT','0')))
if sys.argv[1:] == ['login']:
    Path(os.environ['FAKE_PID']).write_text(str(os.getpid()))
    print(os.environ.get('FAKE_LINK','https://login.tailscale.com/a/example'),flush=True)
    time.sleep(60)
''')
    script.chmod(0o755)
    return {'PATH': str(tmp_path), 'FAKE_CALLS': str(tmp_path / 'calls'),
            'FAKE_PID': str(tmp_path / 'pid'), 'CLAWPOD_NODE_HOST_COMMAND_TIMEOUT': '0.15'}


@pytest.mark.parametrize('link', ['https://login.tailscale.com/a/example', 'no link available'])
def test_actual_cli_signin_process_is_reaped_for_link_and_timeout(tmp_path, link):
    env = fake_tailscale(tmp_path)
    env.update(FAKE_LINK=link, FAKE_STATUS_EXIT='1')
    start = time.monotonic()
    result, out = call(tmp_path, 'agent login', env=env)
    assert time.monotonic() - start < 4
    assert result.returncode == (3 if link.startswith('https:') else 6)
    calls = [json.loads(line) for line in (tmp_path / 'calls').read_text().splitlines()]
    assert calls == [['status', '--json'], ['login']]
    pid = int((tmp_path / 'pid').read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    if result.returncode == 3:
        assert out['agentTailscale']['url'] == link


@pytest.mark.parametrize('raw,exit_code', [('not-json', 0), ('[]', 0), ('{}', 0), ('{"BackendState":"Running"}', 1)])
def test_actual_bad_status_cannot_claim_connected_or_initiate_login(tmp_path, raw, exit_code):
    env = fake_tailscale(tmp_path)
    env.update(FAKE_STATUS=raw, FAKE_STATUS_EXIT=str(exit_code))
    result, out = call(tmp_path, 'agent login', env=env)
    assert result.returncode == 6 and out['errors'][0]['code'] == 'AGENT_TAILSCALE_STATUS_FAILED'
    assert not (tmp_path / 'pid').exists()


def test_absent_cli_does_not_install_tailscale(tmp_path):
    result, out = call(tmp_path, 'agent login', env={'PATH': str(tmp_path)})
    assert result.returncode == 5 and out['errors'][0]['code'] == 'AGENT_TAILSCALE_ABSENT'
    assert not (tmp_path / 'record.jsonl').exists()


@pytest.mark.parametrize('timeout', ['nan', 'inf', '0', '-1'])
def test_invalid_timeout_cannot_spawn_signin(tmp_path, timeout):
    env = fake_tailscale(tmp_path)
    env['CLAWPOD_NODE_HOST_COMMAND_TIMEOUT'] = timeout
    result, out = call(tmp_path, 'agent login', env=env)
    assert result.returncode == 2 and out['errors'][0]['code'] == 'INVALID_INPUT'
    assert not (tmp_path / 'pid').exists()


@pytest.mark.parametrize('command', ['enroll generate', 'enroll status', 'enroll approve', 'bootstrap generate',
    'bootstrap inspect', 'bootstrap plan', 'bootstrap apply', 'install plan', 'install apply',
    'repair plan', 'repair apply', 'uninstall plan', 'uninstall apply', 'rollback plan', 'rollback apply',
    'service start', 'service stop', 'service restart', 'service status', 'pairing status', 'pairing approve',
    'tailscale install-plan', 'tailscale install-apply', 'tailscale login-plan', 'tailscale login-apply',
    'tailscale status', 'tailscale address', 'tailscale same-tailnet', 'tailscale verify', 'tailscale install-status',
    'ssh-server status', 'ssh-server plan', 'ssh-server apply', 'ssh-server verify',
    'system inspect', 'version inspect', 'onboarding status', 'validate plan', 'validate run'])
def test_removed_command_has_no_effect(tmp_path, command):
    result, out = call(tmp_path, command)
    assert result.returncode == 2 and out['effects'] == []
    assert out['errors'][0]['code'] == 'INVALID_INPUT'
    assert not (tmp_path / 'record.jsonl').exists()


@pytest.mark.parametrize('extra', [('--state', 'old-state.json'), ('--node-id', 'old-node'),
    ('--confirm', 'old-confirmation'), ('--openclaw-version', '2026.4.11'), ('--transport', 'openssh')])
def test_removed_arguments_do_not_enter_old_flow(tmp_path, extra):
    result, out = call(tmp_path, 'agent status', extra=extra)
    assert result.returncode == 2 and not out['ok']


def test_installed_harness_wrapper_still_runs(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/install.py'), '--bin-dir', str(tmp_path / 'bin')],
                            capture_output=True, text=True, check=True)
    wrapper = Path(result.stdout.strip())
    result = subprocess.run([str(wrapper), '--json', 'installer', 'info', '--platform', 'linux', '--arch', 'x64'],
                            capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)['installer']['platform'] == 'linux'


def test_manifest_exposes_only_implemented_commands_and_agent_results(tmp_path):
    manifest = json.loads((ROOT / 'harness.json').read_text())
    assert set(manifest['commands']) == {'agent.status', 'agent.login', 'installer.info'}
    for command in ('agent.status', 'agent.login'):
        result, out = call(tmp_path, command.replace('.', ' '), state={'backendState': 'Running'})
        contract = manifest['commands'][command]
        assert contract['baseArgv'] == ['--json', *command.split('.')]
        assert result.returncode == 0 and set(contract['outputSchema']['required']).issubset(out)
    assert 'agentTailscale' in manifest['commands']['agent.status']['outputSchema']['properties']


def test_standalone_agent_command_needs_no_removed_helpers(tmp_path):
    import shutil
    package = tmp_path / 'package'
    package.mkdir()
    for name in ('clawpod_node_host.py', 'agent_tailscale.py'):
        shutil.copyfile(ROOT / name, package / name)
    fixture = tmp_path / 'state.json'
    fixture.write_text('{"agentTailscale":{"backendState":"Running"}}')
    result = subprocess.run([sys.executable, str(package / 'clawpod_node_host.py'), '--json', 'agent', 'status'],
                            env={**os.environ,'CLAWPOD_NODE_HOST_FIXTURE':str(fixture)}, capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)['nextAction']['step'] == 2


@pytest.mark.parametrize('raw', ['null', '[]', 'false', '1'])
def test_configured_nonobject_fixture_never_falls_through_to_live_commands(tmp_path, raw):
    env = fake_tailscale(tmp_path)
    fixture = tmp_path / 'nonobject.json'
    fixture.write_text(raw)
    env['CLAWPOD_NODE_HOST_FIXTURE'] = str(fixture)
    result, out = call(tmp_path, 'agent login', env=env)
    assert result.returncode == 2 and out['errors'][0]['code'] == 'INVALID_INPUT'
    assert not (tmp_path / 'calls').exists()
