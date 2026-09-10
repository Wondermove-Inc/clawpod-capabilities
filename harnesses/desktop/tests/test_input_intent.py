import importlib.util
import json
import pathlib
import subprocess
import pytest

CLI = pathlib.Path(__file__).parents[1] / 'desktop.py'
SPEC = importlib.util.spec_from_file_location('input_desktop', CLI)
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)
TARGET = {'kind':'coordinate', 'x':20, 'y':30}

def test_replace_selects_after_single_click():
    argv = D.safe_pointer_argv(TARGET, 'keyboard.type', ['hello'], text_mode='replace')
    assert argv.count('click') == 1
    assert argv.index('click') < argv.index('ctrl+a') < argv.index('type')
    assert argv[-2:] == ['--', 'hello']

def test_append_has_no_select_all_and_option_text_is_literal():
    argv = D.safe_pointer_argv(TARGET, 'keyboard.type', ['--help'])
    assert 'ctrl+a' not in argv
    assert argv[-2:] == ['--', '--help']

@pytest.mark.parametrize('cmd,tail', [('pointer.right-click',['click','3']), ('pointer.double-click',['click','--repeat','2','--delay','100','1'])])
def test_distinct_pointer_intents(cmd, tail):
    assert D.safe_pointer_argv(TARGET, cmd)[-len(tail):] == tail

@pytest.mark.parametrize('cmd,payload', [
    ('keyboard.type', {'args':[]}), ('keyboard.type', {'args':['a','b']}),
    ('keyboard.type', {'args':['x'], 'textMode':'guess'}),
    ('keyboard.shortcut', {'args':['ctrl+l','ctrl+a']}),
    ('keyboard.key', {'args':['--window']}),
    ('keyboard.key', {'args':'Return'}),
])
def test_invalid_request_rejected_before_backend_or_approval(cmd,payload):
    p = subprocess.run([str(CLI), cmd, '--input', json.dumps(payload), '--dry-run', '--idempotency-key','test'], text=True,capture_output=True)
    assert p.returncode == 10
    assert json.loads(p.stdout)['error']['code'] == 'INVALID_INPUT'

@pytest.mark.parametrize('receipt,expected', [
    ({'requestDigest':'wanted','expiresAt':'2099-01-01T00:00:00+00:00'},True),
    ({'requestDigest':'wrong','expiresAt':'2099-01-01T00:00:00+00:00'},False),
    ({'requestDigest':'wanted','expiresAt':'2000-01-01T00:00:00+00:00'},False),
    ({'requestDigest':'wanted'},False), ([],False),
])
def test_inline_receipt_preserves_digest_expiry_gate(receipt,expected):
    assert bool(D.valid_approval(None,'wanted',json.dumps(receipt))) is expected

def test_conflicting_approval_sources_rejected(tmp_path):
    with pytest.raises(ValueError):
        D.valid_approval(str(tmp_path/'receipt.json'),'wanted','{}')

@pytest.mark.parametrize('expires', ['zzzz', '2099-01-01', '2099-01-01T00:00:00', 42, None])
def test_invalid_expiry_fails_closed(expires):
    assert D.valid_approval(None,'wanted',json.dumps({'requestDigest':'wanted','expiresAt':expires})) is None
