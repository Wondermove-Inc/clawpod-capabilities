import copy
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('bridge', ROOT / 'bridge.py')
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)
CANARY = 'synthetic-test-secret-DO-NOT-USE'


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def request(port=54321, ttl=5):
    return dict(kind='request', reply_required=True, msgid='round-1', nonce='0123456789abcdef0123456789abcdef',
                target='AGENT', agent_name='OPERATOR', reply_to=f'http://127.0.0.1:{port}/inbox',
                text='Review only.', ttl_seconds=ttl)


def reply(req, status='complete'):
    r = copy.deepcopy(req)
    r.update(kind='info', reply_required=False, target=req['agent_name'], agent_name=req['target'],
             result={'status': status})
    if status == 'complete':
        if 'document' in req:
            r['result']['document_sha256'] = req['document']['sha256']
        if 'repository' in req:
            r['result']['repository'] = req['repository']
    return r


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # macOS /var itself may be a symlink: use an explicit canonical staging root.
        self.root = Path(self.tmp.name).resolve()
        self.env = dict(os.environ, OPENCLAW_HOOK_TOKEN=CANARY, BRIDGE_TEST_LOOPBACK='1', PYTHONDONTWRITEBYTECODE='1')
        self.patch = patch.dict(os.environ, self.env)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.tmp.cleanup)

    def save(self, name, value):
        p = self.root / name
        p.write_bytes(b.dumps(value))
        return p

    def cli(self, *args):
        p = subprocess.run([sys.executable, str(ROOT / 'bridge.py'), *map(str, args)], env=self.env,
                           capture_output=True, text=True, timeout=15)
        self.assertNotIn(CANARY, p.stdout + p.stderr)
        self.assertEqual(p.stderr, '')
        return p.returncode, json.loads(p.stdout)

    def test_kat_and_verbatim_bytes(self):
        b.kat()
        self.assertNotEqual(b.derive(' x ', request()['nonce']), b.derive('x', request()['nonce']))
        for nonce in ('ABCDEF'*5, '0'*31, 'a'*33, None):
            with self.assertRaises(b.BridgeError):
                b.derive(CANARY, nonce)

    def test_strict_schema_and_url_allowlist(self):
        for change in ({'extra': True}, {'ttl_seconds': True}, {'ttl_seconds': 1801}, {'nonce':'x'},
                       {'reply_required': False}, {'text': 5}, {'reply_to':'http://example.com/inbox'},
                       {'reply_to':'http://user:password@127.0.0.1/inbox'}):
            with self.subTest(change=change), self.assertRaises(b.BridgeError):
                b.validate_envelope(dict(request(), **change), ['127.0.0.1'])
        with self.assertRaises(b.BridgeError):
            b.validate_envelope(request(), [])
        with patch.dict(os.environ, {'BRIDGE_TEST_LOOPBACK':'0'}), self.assertRaises(b.BridgeError):
            b.validate_envelope(request(), ['127.0.0.1'])
        with self.assertRaises(b.BridgeError):
            b.parse_json(b'{"a":1,"a":2}')

    def test_repo_identity_and_path_rejection(self):
        self.assertEqual(b.repository_identity('git@example.com:owner/repo.git'),
                         b.repository_identity('https://example.com/owner/repo'))
        for value in ('https://secret@example.com/owner/repo', 'ssh://key@example.com/owner/repo',
                      'https://example.com/owner/repo?token=secret'):
            with self.assertRaises(b.BridgeError):
                b.repository_identity(value)
        for value in ('../x', '/x', '.git/config', '.env', 'x/.sf/a', 'x/.sfdx/a', 'x/.env.local', 'a//b', 'a/./b', 'a\\b'):
            with self.subTest(value=value), self.assertRaises(b.BridgeError):
                b.path_parts(value)

    def make_repo(self):
        root = self.root / 'repos' / 'sample'
        root.mkdir(parents=True)
        def git(*args):
            return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).decode().strip()
        git('init')
        git('config', 'user.name', 'Synthetic')
        git('config', 'user.email', 'synthetic@example.invalid')
        git('remote', 'add', 'origin', 'https://example.com/owner/sample.git')
        (root / 'readme.md').write_text('sample')
        git('add', 'readme.md')
        git('commit', '-m', 'fixture')
        context = dict(project_id='sample', repository_identity='git@example.com:owner/sample.git',
                       expected_commit=git('rev-parse','HEAD'), relative_path='readme.md')
        return root, context

    def test_repository_actual_checks_and_no_mutation(self):
        root, ctx = self.make_repo()
        self.assertEqual(b.check_repository(ctx, str(self.root)), ctx)
        with self.assertRaises(b.BridgeError):
            b.check_repository(ctx)
        context_file = self.save('context.json', dict(request(), repository=ctx))
        code, result = self.cli('preflight', '--request', context_file, '--allow-host', '127.0.0.1',
                                '--repo-root', root)
        self.assertNotEqual(code, 0)
        self.assertEqual(result['error']['code'], 'CLI_ARGUMENTS')
        for field, value in [('project_id','missing'), ('expected_commit','f'*40),
                             ('repository_identity','https://example.com/wrong/repo'), ('relative_path','missing.md')]:
            with self.subTest(field=field), self.assertRaises(b.BridgeError):
                b.check_repository(dict(ctx, **{field:value}), str(self.root))
        (root/'link').symlink_to(self.root)
        with self.assertRaises(b.BridgeError):
            b.check_repository(dict(ctx, relative_path='link'), str(self.root))
        (root/'link').unlink()
        (root/'readme.md').write_text('dirty')
        with self.assertRaises(b.BridgeError) as failure:
            b.check_repository(ctx, str(self.root))
        self.assertEqual(failure.exception.code, 'REPOSITORY_DIRTY')
        self.assertEqual((root/'readme.md').read_text(), 'dirty')

    def test_document_validation_and_secrets(self):
        for raw in (b'', b'\xff', b'x'*65537):
            with self.assertRaises(b.BridgeError):
                b.document_metadata(raw, 'note.md', request())
        doc = self.root/'note.md'
        doc.write_text('한글\n')
        req, raw = b.prepare(request(), ['127.0.0.1'], doc)
        self.assertEqual(req['document']['byte_count'], len(raw))
        bad = copy.deepcopy(req)
        bad['document']['url'] = 'http://127.0.0.1:9999/document/'+req['nonce']
        with self.assertRaises(b.BridgeError):
            b.validate_envelope(bad, ['127.0.0.1'])
        doc.write_text(CANARY)
        with self.assertRaises(b.BridgeError):
            b.prepare(request(), ['127.0.0.1'], doc)
        with self.assertRaises(b.BridgeError):
            b.validate_envelope(dict(request(), text=CANARY), ['127.0.0.1'])
        req['text'] = b.derive(CANARY, req['nonce'])
        with self.assertRaises(b.BridgeError):
            b.validate_envelope(req, ['127.0.0.1'])

    def test_cli_preflight_and_errors_are_sanitized(self):
        path = self.save('request.json', request())
        code, result = self.cli('preflight','--request',path,'--allow-host','127.0.0.1')
        self.assertEqual(code,0)
        self.assertEqual(result['status'],'ready')
        self.assertGreaterEqual(result['timing']['elapsedMs'],0)
        code, result = self.cli('send','--secret',CANARY)
        self.assertNotEqual(code,0)
        self.assertEqual(result['error']['code'],'CLI_ARGUMENTS')
        path = self.save('secret.json', dict(request(), text=CANARY))
        code, result = self.cli('preflight','--request',path,'--allow-host','127.0.0.1')
        self.assertNotEqual(code,0)

    def start_inbox(self, req, document=None):
        path = self.save('request.json', req)
        output, ready = self.root/'proof.json', self.root/'ready.json'
        args = [sys.executable,str(ROOT/'bridge.py'),'receive','--request',str(path),'--allow-host','127.0.0.1',
                '--mode','inbox','--bind','127.0.0.1','--port',str(url_port(req)), '--output',str(output),'--ready-file',str(ready)]
        if document:
            args += ['--document-file',str(document)]
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)
        def cleanup():
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=5)
        self.addCleanup(cleanup)
        limit = time.monotonic()+5
        while not ready.exists() and process.poll() is None and time.monotonic()<limit:
            time.sleep(.02)
        self.assertTrue(ready.exists(), process.poll())
        return process, path, output

    def call(self, req, method='POST', path='/inbox', payload=None, token=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1',url_port(req),timeout=3)
        body = b.dumps(payload) if payload is not None else b''
        fields = {'Authorization':'Bearer '+(token or b.derive(CANARY,req['nonce'])), 'Content-Type':'application/json'}
        fields.update(headers or {})
        connection.request(method,path,body=body,headers=fields)
        result = connection.getresponse()
        value = (result.status,result.read())
        connection.close()
        return value

    def test_full_subprocess_document_callback_and_verify(self):
        doc = self.root/'note.md'
        doc.write_text('# Synthetic\n한글 bytes\n')
        req, _ = b.prepare(request(free_port()), ['127.0.0.1'], doc)
        process, path, output = self.start_inbox(req, doc)
        self.assertEqual(self.call(req,'GET','/document/'+req['nonce'],token='wrong')[0],401)
        self.assertEqual(self.call(req,'PUT')[0],405)
        self.assertEqual(self.call(req,path='/other',payload=reply(req))[0],404)
        self.assertEqual(self.call(req)[0],400)
        for change in ('nonce','hash','identity'):
            bad = reply(req)
            if change == 'nonce': bad['nonce']='f'*32
            if change == 'hash': bad['result']['document_sha256']='0'*64
            if change == 'identity': bad['agent_name']='OTHER'
            self.assertEqual(self.call(req,payload=bad)[0],400)
        stage = self.root/'stage'
        stage.mkdir()
        code, data = self.cli('receive','--request',path,'--allow-host','127.0.0.1','--mode','document','--staging-dir',stage)
        self.assertEqual(code,0,data)
        self.assertEqual((stage/'note.md').read_bytes(),doc.read_bytes())
        self.assertFalse(output.exists())
        code, data = self.cli('receive','--request',path,'--allow-host','127.0.0.1','--mode','document','--staging-dir',stage)
        self.assertNotEqual(code,0)
        terminal = self.save('terminal.json',reply(req))
        code, data = self.cli('send','--request',terminal,'--allow-host','127.0.0.1','--target-url',req['reply_to'])
        self.assertEqual(code,0,data)
        self.assertEqual(data['status'],'accepted')
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(stderr,'')
        self.assertEqual(json.loads(stdout)['status'],'complete')
        code, verified = self.cli('verify','--request',path,'--allow-host','127.0.0.1','--proof',output)
        self.assertEqual(code,0,verified)
        for file in (output,self.root/'ready.json'):
            self.assertNotIn(CANARY,file.read_text())
            self.assertNotIn(b.derive(CANARY,req['nonce']),file.read_text())

    def test_failed_callback_without_unobserved_document_proof(self):
        doc=self.root/'note.md'
        doc.write_text('sample')
        req,_=b.prepare(request(free_port()),['127.0.0.1'],doc)
        process,path,output=self.start_inbox(req,doc)
        self.assertEqual(self.call(req,payload=reply(req,'failed'))[0],200)
        stdout,_=process.communicate(timeout=5)
        self.assertFalse(json.loads(stdout)['ok'])
        code,result=self.cli('verify','--request',path,'--allow-host','127.0.0.1','--proof',output)
        self.assertNotEqual(code,0)
        self.assertEqual(result['error']['code'],'ROUND_NOT_COMPLETE')

    def test_concurrent_callback_consumes_once(self):
        req=request(free_port())
        process,_,output=self.start_inbox(req)
        barrier=threading.Barrier(3)
        outcomes=[]
        def deliver():
            barrier.wait()
            try: outcomes.append(self.call(req,payload=reply(req))[0])
            except OSError: outcomes.append('closed')
        workers=[threading.Thread(target=deliver) for _ in range(2)]
        for worker in workers: worker.start()
        barrier.wait()
        for worker in workers: worker.join()
        self.assertEqual(outcomes.count(200),1,outcomes)
        process.communicate(timeout=5)
        self.assertEqual(json.loads(output.read_text()),reply(req))

    def test_timeout_and_sigterm_cleanup(self):
        req=request(free_port(),ttl=1)
        process,_,output=self.start_inbox(req)
        stdout,stderr=process.communicate(timeout=5)
        self.assertEqual(stderr,'')
        self.assertEqual(json.loads(stdout)['error']['code'],'ROUND_TIMEOUT')
        self.assertFalse(output.exists())
        (self.root/'ready.json').unlink()
        process,_,_=self.start_inbox(request(free_port()))
        process.terminate()
        stdout,_=process.communicate(timeout=5)
        self.assertEqual(json.loads(stdout)['error']['code'],'INTERRUPTED')

    def test_atomic_collision_and_symlink(self):
        path=self.root/'new.md'
        b.atomic_new(path,b'first')
        with self.assertRaises(b.BridgeError): b.atomic_new(path,b'second')
        self.assertEqual(path.read_bytes(),b'first')
        link=self.root/'link.md'
        link.symlink_to(path)
        with self.assertRaises(b.BridgeError): b.atomic_new(link,b'bad')

    def test_wake_shape_and_no_redirect_retry(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                seen.append((self.path,self.headers.get('Authorization'),json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(200 if len(seen)==1 else 302)
                self.send_header('Location','http://example.com/never')
                self.end_headers()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        req=request()
        path=self.save('request.json',req)
        args=('send','--request',path,'--allow-host','127.0.0.1','--target-url',f'http://127.0.0.1:{server.server_port}/hooks/wake')
        code,data=self.cli(*args)
        self.assertEqual(code,0)
        self.assertEqual(data['status'],'accepted')
        self.assertEqual(seen[0][1],'Bearer '+CANARY)
        self.assertEqual(set(seen[0][2]),{'text','mode'})
        self.assertEqual(json.loads(seen[0][2]['text']),req)
        code,data=self.cli(*args)
        self.assertNotEqual(code,0)
        self.assertEqual(data['status'],'reconciliation-needed')
        self.assertEqual(len(seen),2)

    def test_verify_rejects_wrong_commit_and_blocked(self):
        _,ctx=self.make_repo()
        req=dict(request(),repository=ctx)
        terminal=reply(req)
        terminal['result']['repository']=dict(ctx,expected_commit='0'*40)
        with self.assertRaises(b.BridgeError): b.correlate(req,terminal,['127.0.0.1'])
        self.assertEqual(b.correlate(req,reply(req,'blocked'),['127.0.0.1']),'blocked')

    def test_download_negative_responses_never_stage(self):
        state={'raw':b'correct markdown','type':'text/markdown; charset=utf-8','code':200}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                self.send_response(state['code'])
                self.send_header('Content-Type',state['type'])
                self.send_header('Location','http://example.com/blocked')
                self.end_headers()
                self.wfile.write(state['raw'])
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        req=request(server.server_port)
        req['document']=b.document_metadata(state['raw'],'note.md',req)
        for values in ({'raw':b'wrong'}, {'raw':b'\xff'}, {'raw':b'x'*65537}, {'raw':b''},
                       {'type':'text/html'}, {'code':302}):
            state.update(raw=b'correct markdown',type='text/markdown; charset=utf-8',code=200)
            state.update(values)
            with self.subTest(values=list(values)), self.assertRaises(b.BridgeError):
                b.download(req,['127.0.0.1'],self.root)
            self.assertFalse((self.root/'note.md').exists())

    def test_context_failure_precedes_document_read(self):
        _,ctx=self.make_repo()
        req=dict(request(),repository=dict(ctx,expected_commit='0'*40))
        path=self.save('bad-context.json',req)
        code,result=self.cli('preflight','--request',path,'--allow-host','127.0.0.1',
                             '--workspace-root',self.root,'--document-file',self.root/'missing.md')
        self.assertNotEqual(code,0)
        self.assertEqual(result['error']['code'],'REPOSITORY_COMMIT_MISMATCH')

    def test_backend_connection_failure_needs_reconciliation(self):
        path=self.save('request.json',request())
        code,result=self.cli('send','--request',path,'--allow-host','127.0.0.1',
                             '--target-url',f'http://127.0.0.1:{free_port()}/hooks/wake')
        self.assertNotEqual(code,0)
        self.assertEqual(result['status'],'reconciliation-needed')

    def test_malformed_and_oversized_callback_does_not_consume(self):
        req=request(free_port())
        process,_,output=self.start_inbox(req)
        self.assertEqual(self.call(req,payload=reply(req),token='wrong')[0],401)
        self.assertEqual(self.call(req,payload=reply(req),headers={'Content-Type':'text/plain'})[0],400)
        bad=reply(req)
        bad['text']='x'*131073
        self.assertEqual(self.call(req,payload=bad)[0],400)
        self.assertFalse(output.exists())
        self.assertEqual(self.call(req,payload=reply(req))[0],200)
        process.communicate(timeout=5)

    def test_slow_client_does_not_prevent_timeout_shutdown(self):
        req=request(free_port(),ttl=1)
        process,_,_=self.start_inbox(req)
        connection=socket.create_connection(('127.0.0.1',url_port(req)))
        self.addCleanup(connection.close)
        connection.sendall(b'POST /inbox HTTP/1.1\r\n')
        start=time.monotonic()
        stdout,stderr=process.communicate(timeout=5)
        self.assertLess(time.monotonic()-start,4)
        self.assertEqual(stderr,'')
        self.assertEqual(json.loads(stdout)['error']['code'],'ROUND_TIMEOUT')

    def test_case_aliases_are_denied_before_read_or_write(self):
        repo, ctx = self.make_repo()
        for component in ('.Git', '.ENV', '.eNv.Local', '.SF', '.SfDx'):
            directory = self.root / component.lower()
            directory.mkdir(exist_ok=True)
            original = directory / 'dummy.md'
            original.write_text('SYNTHETIC-NONSECRET')
            alias = self.root / component
            # On case-insensitive macOS this points at the existing lower-case directory.
            if alias.exists():
                self.assertTrue((alias / 'dummy.md').samefile(original))
            with self.subTest(component=component):
                for relative in (component, component + '/dummy.md'):
                    with self.assertRaises(b.BridgeError): b.path_parts(relative)
                with self.assertRaises(b.BridgeError): b.read_file(alias / 'dummy.md', 65536)
                with self.assertRaises(b.BridgeError): b.atomic_new(alias / 'new.md', b'bad')
                self.assertFalse((directory / 'new.md').exists())
                self.assertEqual(original.read_text(), 'SYNTHETIC-NONSECRET')
                req = request()
                req['document'] = b.document_metadata(b'note', 'note.md', req)
                with patch.object(b, 'http_call') as call:
                    with self.assertRaises(b.BridgeError): b.download(req, ['127.0.0.1'], alias)
                    call.assert_not_called()
                with self.assertRaises(b.BridgeError):
                    b.check_repository(dict(ctx, relative_path=component + '/config'), str(self.root))
        actual_git_alias = repo / '.Git' / 'config'
        if actual_git_alias.exists():
            self.assertTrue(actual_git_alias.samefile(repo / '.git' / 'config'))
        with self.assertRaises(b.BridgeError): b.read_file(actual_git_alias, 65536)

    def test_absolute_cancellation_with_header_and_body_drips(self):
        for phase in ('header', 'body'):
            for trigger in ('ttl', 'sigterm'):
                with self.subTest(phase=phase, trigger=trigger):
                    ready = self.root / 'ready.json'
                    if ready.exists(): ready.unlink()
                    req = request(free_port(), ttl=1 if trigger == 'ttl' else 30)
                    process, _, output = self.start_inbox(req)
                    connection = socket.create_connection(('127.0.0.1', url_port(req)))
                    self.addCleanup(connection.close)
                    if phase == 'header':
                        connection.sendall(b'POST /inbox HTTP/1.1\r\nX-Slow: ')
                    else:
                        token = b.derive(CANARY, req['nonce'])
                        connection.sendall(('POST /inbox HTTP/1.1\r\nAuthorization: Bearer ' + token +
                            '\r\nContent-Type: application/json\r\nContent-Length: 10000\r\n\r\n').encode())
                    stop_drip = threading.Event()
                    def drip():
                        while not stop_drip.wait(.05):
                            try: connection.sendall(b'x')
                            except OSError: return
                    writer = threading.Thread(target=drip)
                    writer.start()
                    try:
                        time.sleep(.15)
                        started = time.monotonic()
                        if trigger == 'sigterm': process.terminate()
                        stdout, stderr = process.communicate(timeout=3)
                        self.assertLess(time.monotonic() - started, 2.5)
                        self.assertGreaterEqual(connection.fileno(), 0, 'client must remain open through process exit')
                        self.assertEqual(stderr, '')
                        result = json.loads(stdout)
                        self.assertFalse(result['ok'])
                        self.assertEqual(result['error']['code'], 'ROUND_TIMEOUT' if trigger == 'ttl' else 'INTERRUPTED')
                        self.assertFalse(output.exists())
                    finally:
                        stop_drip.set()
                        writer.join(timeout=1)
                        connection.close()

    def test_request_fetch_reply_content_full_subprocess_round(self):
        _, context = self.make_repo()
        doc = self.root/'handoff.md'
        doc.write_text('# Synthetic handoff\n한글 bytes\n')
        req, _ = b.prepare(dict(request(free_port()), repository=context), ['127.0.0.1'], doc)
        process, original, proof_path = self.start_inbox(req, doc)
        before = original.read_bytes()
        fetch_path = '/request/' + req['nonce']
        self.assertEqual(self.call(req, 'GET', fetch_path, token='wrong')[0], 401)
        self.assertEqual(self.call(req, 'GET', '/request/'+'f'*32)[0], 404)
        first = self.call(req, 'GET', fetch_path)
        self.assertEqual(first[0], 200)
        self.assertEqual(json.loads(first[1]), req)
        self.assertEqual(self.call(req, 'GET', fetch_path), first)
        self.assertFalse(proof_path.exists())
        stage = self.root/'fetched'; stage.mkdir()
        reference = {key:req[key] for key in ('nonce','msgid','target','reply_to')}
        bad_reference = self.save('bad-reference.json', dict(reference,target='OTHER'))
        code, result = self.cli('receive','--mode','request','--request',bad_reference,
                                '--allow-host','127.0.0.1','--staging-dir',stage)
        self.assertNotEqual(code, 0)
        self.assertEqual(result['error']['code'], 'REQUEST_REFERENCE')
        self.assertEqual(list(stage.iterdir()), [])
        reference_file = self.save('reference.json', reference)
        args = ('receive','--mode','request','--request',reference_file,'--allow-host','127.0.0.1','--staging-dir',stage)
        code, result = self.cli(*args)
        self.assertEqual(code, 0, result)
        self.assertEqual(result['data']['kat'], 'passed')
        self.assertNotIn('envelope', result['data'])
        staged = Path(result['data']['staged_path'])
        self.assertEqual(json.loads(staged.read_text()), req)
        self.assertFalse(proof_path.exists())
        code, result = self.cli(*args)
        self.assertNotEqual(code, 0)
        self.assertEqual(result['error']['code'], 'OUTPUT_COLLISION')
        terminal = reply(req)
        content = self.save('content.json', {'text':'Reviewed handoff.', 'result':terminal['result']})
        staged_before = staged.read_bytes()
        code, result = self.cli('send','--request',staged,'--reply-content-file',content,
                                '--allow-host','127.0.0.1','--target-url',req['reply_to'])
        self.assertEqual(code, 0, result)
        self.assertEqual(result['status'], 'accepted')
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(stderr, '')
        self.assertEqual(json.loads(stdout)['status'], 'complete')
        observed = json.loads(proof_path.read_text())
        self.assertEqual(observed['target'], 'OPERATOR')
        self.assertEqual(observed['agent_name'], 'AGENT')
        self.assertEqual(observed['document'], req['document'])
        self.assertEqual(observed['repository'], req['repository'])
        self.assertEqual(original.read_bytes(), before)
        self.assertEqual(staged.read_bytes(), staged_before)
        code, result = self.cli('verify','--request',staged,'--allow-host','127.0.0.1','--proof',proof_path)
        self.assertEqual(code, 0, result)

    def test_reference_validation_precedes_network(self):
        reference = {key:request()[key] for key in ('nonce','msgid','target','reply_to')}
        for changes in ({'nonce':'bad'},{'msgid':1},{'target':None},{'extra':True},
                        {'reply_to':'http://127.0.0.1:54321/other'}):
            with self.subTest(changes=changes), patch.object(b,'http_call') as transport:
                with self.assertRaises(b.BridgeError):
                    b.fetch_request(dict(reference,**changes),['127.0.0.1'],self.root)
                transport.assert_not_called()
        symlink = self.root/'stage-link'; symlink.symlink_to(self.root, target_is_directory=True)
        with patch.object(b,'http_call') as transport:
            with self.assertRaises(b.BridgeError): b.fetch_request(reference,['127.0.0.1'],symlink)
            transport.assert_not_called()

    def test_request_fetch_rejects_bad_http_and_envelope_without_stage(self):
        state = {'body':b'', 'type':'application/json; charset=utf-8', 'code':200}
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                seen.append(self.path)
                self.send_response(state['code'])
                self.send_header('Content-Type',state['type'])
                self.send_header('Location','http://example.com/forbidden')
                self.end_headers()
                self.wfile.write(state['body'])
        server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        req = request(server.server_port)
        reference = {key:req[key] for key in ('nonce','msgid','target','reply_to')}
        valid = b.dumps(req)
        variants = [{'body':b''},{'body':b'\xff'},{'body':b'x'*(b.MAX_BODY+1)},
                    {'body':valid[:-1]+b',"msgid":"duplicate"}'},{'type':'text/plain'},
                    {'type':'application/json; charset=latin-1'},{'code':302},
                    {'body':b.dumps(dict(req,target='WRONG'))},
                    {'body':b.dumps(dict(req,msgid='wrong-round'))},
                    {'body':b.dumps(dict(req,nonce='f'*32))},
                    {'body':b.dumps(reply(req))},{'body':b.dumps(dict(req,legacy=True))}]
        for variant in variants:
            state.update(body=valid,type='application/json; charset=utf-8',code=200)
            state.update(variant)
            count = len(seen)
            with self.subTest(variant=list(variant)), self.assertRaises(b.BridgeError):
                b.fetch_request(reference,['127.0.0.1'],self.root)
            self.assertEqual(len(seen),count+1)
            self.assertFalse((self.root/('request-'+req['nonce']+'.json')).exists())

    def test_reply_content_rejects_legacy_fields_and_bad_proof_before_send(self):
        req = request()
        req['document'] = b.document_metadata(b'content','note.md',req)
        _, req['repository'] = self.make_repo()
        original = self.save('original.json',req)
        valid = {'text':'done','result':reply(req)['result']}
        for content in (dict(valid,nonce=req['nonce']),dict(valid,target='OPERATOR'),
                        {'text':'done','result':{'status':'complete'}},
                        {'text':'done','result':dict(valid['result'],document_sha256='0'*64)}):
            with self.subTest(content=content),patch.object(b,'http_call') as transport:
                content_path = self.save('reply-content.json',content)
                args = b.parser().parse_args(['send','--request',str(original),'--reply-content-file',str(content_path),
                                              '--allow-host','127.0.0.1','--target-url',req['reply_to']])
                with self.assertRaises(b.BridgeError): b.execute(args)
                transport.assert_not_called()
        with self.assertRaises(b.BridgeError) as error:
            b.compose_reply(req,dict(valid,legacy='field'),['127.0.0.1'])
        self.assertEqual(error.exception.code,'REPLY_CONTENT_FIELDS')
        content_path = self.save('reply-content.json',valid)
        with patch.object(b,'http_call') as transport:
            args = b.parser().parse_args(['send','--request',str(original),'--reply-content-file',str(content_path),
                                          '--document-file','missing.md','--allow-host','127.0.0.1','--target-url',req['reply_to']])
            with self.assertRaises(b.BridgeError): b.execute(args)
            transport.assert_not_called()

    def test_reply_content_failed_or_blocked_preserves_context(self):
        req = request()
        req['document'] = b.document_metadata(b'content','note.md',req)
        _, req['repository'] = self.make_repo()
        before = copy.deepcopy(req)
        for status in ('failed','blocked'):
            observed = b.compose_reply(req,{'text':'Could not complete','result':{'status':status}},['127.0.0.1'])
            self.assertEqual(observed['target'],req['agent_name'])
            self.assertEqual(observed['agent_name'],req['target'])
            self.assertEqual(observed['document'],req['document'])
            self.assertEqual(observed['repository'],req['repository'])
            self.assertEqual(b.correlate(req,observed,['127.0.0.1']),status)
        self.assertEqual(req,before)


def url_port(req):
    return int(req['reply_to'].split(':')[-1].split('/')[0])


if __name__=='__main__':
    unittest.main()
