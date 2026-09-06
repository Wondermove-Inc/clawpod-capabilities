#!/usr/bin/env python3
"""Bounded, standard-library bridge transport. Never executes received content."""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import http.client
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

MAX_BODY = 131072
MAX_DOCUMENT = 65536
NONCE = re.compile(r"[0-9a-f]{32}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
DENIED = {'.env', '.git', '.sf', '.sfdx'}


class BridgeError(Exception):
    def __init__(self, code, status='rejected'):
        self.code, self.status = code, status


def require(condition, code='INVALID_INPUT'):
    if not condition:
        raise BridgeError(code)


def exact(obj, required, optional=()):
    require(isinstance(obj, dict))
    require(set(required) <= obj.keys() and obj.keys() <= set(required) | set(optional))


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def parse_json(raw):
    def pairs(rows):
        value = {}
        for key, item in rows:
            require(key not in value, 'DUPLICATE_FIELD')
            value[key] = item
        return value
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda _: require(False))
    except (ValueError, UnicodeError, RecursionError):
        raise BridgeError('INVALID_JSON') from None


def derive(secret, nonce):
    require(isinstance(secret, str) and bool(secret), 'SECRET_REQUIRED')
    require(isinstance(nonce, str) and NONCE.fullmatch(nonce), 'INVALID_NONCE')
    return base64.urlsafe_b64encode(hmac.new(secret.encode('utf-8'),
        ('inbox-token-derive-v1|' + nonce).encode('ascii'), hashlib.sha256).digest()).rstrip(b'=').decode('ascii')


def kat():
    require(derive('kat-dummy-secret-do-not-use-0000', '00112233445566778899aabbccddeeff') ==
            'Ot8VTiqyT36pMDFtVJ0GDHI2bHpuSRJ3gu05qXCHr6M', 'KAT_FAILED')


def secret():
    kat()
    value = os.environ.get('OPENCLAW_HOOK_TOKEN', '')
    require(bool(value) and '\r' not in value and '\n' not in value, 'SECRET_REQUIRED')
    return value


def path_parts(value):
    require(isinstance(value, str) and value and '\\' not in value, 'UNSAFE_PATH')
    p = PurePosixPath(value)
    require(not p.is_absolute() and value == p.as_posix() and
            all(part not in ('..', '.') and part.casefold() not in DENIED and not part.casefold().startswith('.env.')
                for part in p.parts), 'UNSAFE_PATH')
    return p.parts


def safe_local(value):
    path = Path(os.path.abspath(value))
    require(all(not p.is_symlink() for p in (path, *path.parents)), 'SYMLINK_PATH')
    require(all(part.casefold() not in DENIED and not part.casefold().startswith('.env.')
                for part in path.parts), 'UNSAFE_PATH')
    return path


def read_file(value, maximum):
    path = safe_local(value)
    with path.open('rb') as stream:
        data = stream.read(maximum + 1)
    require(len(data) <= maximum, 'FILE_TOO_LARGE')
    return data


def load_request(value):
    return parse_json(read_file(value, MAX_BODY))


def repository_identity(value):
    require(isinstance(value, str), 'REPOSITORY_IDENTITY')
    # SSH's fixed git username is a transport username, not embedded credentials.
    if re.fullmatch(r'git@[A-Za-z0-9.-]+:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value):
        host, path = value[4:].split(':', 1)
    else:
        u = urlsplit(value)
        require(u.scheme in ('https', 'ssh') and u.hostname and not u.password and
                (u.username is None or (u.scheme == 'ssh' and u.username == 'git')) and
                u.port is None and not u.query and not u.fragment, 'REPOSITORY_IDENTITY')
        host, path = u.hostname, u.path.lstrip('/')
    require(re.fullmatch(r'[A-Za-z0-9.-]+', host) and
            re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', path), 'REPOSITORY_IDENTITY')
    path = path[:-4] if path.endswith('.git') else path
    require(all(part not in ('.', '..') for part in path.split('/')), 'REPOSITORY_IDENTITY')
    return host.lower() + '/' + path


def validate_repository(value):
    exact(value, ('project_id', 'repository_identity', 'expected_commit', 'relative_path'))
    require(isinstance(value['project_id'], str) and ID.fullmatch(value['project_id']) and
            value['project_id'] not in ('.', '..'), 'PROJECT_ID')
    repository_identity(value['repository_identity'])
    require(isinstance(value['expected_commit'], str) and
            re.fullmatch(r'[0-9a-f]{40}', value['expected_commit']), 'EXPECTED_COMMIT')
    path_parts(value['relative_path'])


def check_repository(value, workspace_root=None):
    validate_repository(value)
    require(bool(workspace_root), 'REPOSITORY_ROOT_REQUIRED')
    root = safe_local(safe_local(workspace_root) / 'repos' / value['project_id'])
    require(root.is_dir(), 'REPOSITORY_MISSING')
    def git(*args):
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env['GIT_OPTIONAL_LOCKS'] = '0'
        p = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-C', str(root), *args], capture_output=True,
                           timeout=10, env=env)
        require(p.returncode == 0, 'REPOSITORY_CHECK_FAILED')
        return p.stdout.decode('utf-8').strip()
    require(Path(git('rev-parse', '--show-toplevel')).resolve() == root, 'REPOSITORY_ROOT_MISMATCH')
    require(repository_identity(git('remote', 'get-url', 'origin')) ==
            repository_identity(value['repository_identity']), 'REPOSITORY_IDENTITY_MISMATCH')
    require(git('rev-parse', 'HEAD') == value['expected_commit'], 'REPOSITORY_COMMIT_MISMATCH')
    require(not git('status', '--porcelain', '--untracked-files=all'), 'REPOSITORY_DIRTY')
    target = safe_local(root.joinpath(*path_parts(value['relative_path'])))
    require(target.is_relative_to(root) and target.exists(), 'REPOSITORY_PATH_MISSING')
    return dict(value)


def endpoint(value, allowed, path=None):
    require(isinstance(value, str), 'ENDPOINT_REJECTED')
    try:
        u = urlsplit(value)
        addr = ipaddress.IPv4Address(u.hostname or '')
        port = u.port
    except ValueError:
        raise BridgeError('ENDPOINT_REJECTED') from None
    loopback = os.environ.get('BRIDGE_TEST_LOOPBACK') == '1' and addr.is_loopback
    require(u.scheme in ('http', 'https') and not u.username and not u.password and
            not u.query and not u.fragment and u.hostname in allowed and
            (addr in ipaddress.IPv4Network('100.64.0.0/10') or loopback) and
            (port is None or 1 <= port <= 65535) and (path is None or u.path == path),
            'ENDPOINT_REJECTED')
    return u


def document_metadata(raw, filename, request):
    require(0 < len(raw) <= MAX_DOCUMENT, 'DOCUMENT_SIZE')
    try:
        raw.decode('utf-8')
    except UnicodeError:
        raise BridgeError('DOCUMENT_UTF8') from None
    require(isinstance(filename, str) and len(path_parts(filename)) == 1 and
            filename.lower().endswith('.md'), 'DOCUMENT_FILENAME')
    u = urlsplit(request['reply_to'])
    return {'filename': filename, 'byte_count': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'url': f'{u.scheme}://{u.netloc}/document/{request["nonce"]}'}


def validate_envelope(value, allowed):
    exact(value, ('kind', 'reply_required', 'msgid', 'nonce', 'target', 'agent_name', 'reply_to', 'text', 'ttl_seconds'),
          ('repository', 'document', 'result'))
    require(value['kind'] in ('request', 'info') and type(value['reply_required']) is bool)
    require(value['reply_required'] == (value['kind'] == 'request'))
    require(type(value['ttl_seconds']) is int and 1 <= value['ttl_seconds'] <= 1800, 'INVALID_TTL')
    for key in ('msgid', 'target', 'agent_name'):
        require(isinstance(value[key], str) and ID.fullmatch(value[key]), 'INVALID_ID')
    require(isinstance(value['nonce'], str) and NONCE.fullmatch(value['nonce']), 'INVALID_NONCE')
    require(isinstance(value['text'], str) and len(value['text'].encode('utf-8')) <= 65536, 'INVALID_TEXT')
    endpoint(value['reply_to'], allowed, '/inbox')
    if 'repository' in value:
        validate_repository(value['repository'])
    if 'document' in value:
        doc = value['document']
        exact(doc, ('filename', 'byte_count', 'sha256', 'url'))
        require(isinstance(doc['filename'], str) and len(path_parts(doc['filename'])) == 1 and
                doc['filename'].lower().endswith('.md'), 'DOCUMENT_FILENAME')
        require(type(doc['byte_count']) is int and 0 < doc['byte_count'] <= MAX_DOCUMENT, 'DOCUMENT_SIZE')
        require(isinstance(doc['sha256'], str) and SHA.fullmatch(doc['sha256']), 'DOCUMENT_HASH')
        d = endpoint(doc['url'], allowed, '/document/' + value['nonce'])
        r = urlsplit(value['reply_to'])
        require((d.scheme, d.netloc) == (r.scheme, r.netloc), 'DOCUMENT_ORIGIN')
    if value['kind'] == 'request':
        require('result' not in value)
    else:
        exact(value.get('result'), ('status',), ('document_sha256', 'repository', 'evidence'))
        require(value['result']['status'] in ('complete', 'failed', 'blocked'), 'RESULT_STATUS')
        if 'evidence' in value['result']:
            require(isinstance(value['result']['evidence'], dict), 'RESULT_EVIDENCE')
    require(len(dumps(value)) <= MAX_BODY, 'BODY_TOO_LARGE')
    reject_secrets(dumps(value), value['nonce'])
    return value


def reject_secrets(raw, nonce):
    key = os.environ.get('OPENCLAW_HOOK_TOKEN', '')
    if key:
        for sensitive in (key, derive(key, nonce)):
            require(sensitive.encode('utf-8') not in raw and dumps(sensitive)[1:-1] not in raw, 'SECRET_IN_CONTENT')


def prepare(request, allowed, document_file=None):
    # Validate context before reading the optional document or contacting a peer.
    request = validate_envelope(dict(request), allowed)
    raw = None
    if document_file:
        raw = read_file(document_file, MAX_DOCUMENT)
        reject_secrets(raw, request['nonce'])
        metadata = document_metadata(raw, Path(document_file).name, request)
        require('document' not in request or request['document'] == metadata, 'DOCUMENT_MISMATCH')
        request['document'] = metadata
    return validate_envelope(request, allowed), raw


def correlate(expected, reply, allowed):
    validate_envelope(expected, allowed)
    validate_envelope(reply, allowed)
    require(expected['kind'] == 'request' and reply['kind'] == 'info', 'CORRELATION')
    for key in ('msgid', 'nonce', 'reply_to', 'ttl_seconds', 'repository', 'document'):
        require(reply.get(key) == expected.get(key), 'CORRELATION')
    require(reply['target'] == expected['agent_name'] and reply['agent_name'] == expected['target'], 'CORRELATION')
    if reply['result']['status'] == 'complete' and 'document' in expected:
        require(reply['result'].get('document_sha256') == expected['document']['sha256'], 'DOCUMENT_HASH')
    if reply['result']['status'] == 'complete' and 'repository' in expected:
        require(reply['result'].get('repository') == expected['repository'], 'REPOSITORY_PROOF')
    return reply['result']['status']


def compose_reply(original, content, allowed):
    validate_envelope(original, allowed)
    require(original['kind'] == 'request', 'REQUEST_REQUIRED')
    require(isinstance(content, dict) and set(content) == {'text', 'result'}, 'REPLY_CONTENT_FIELDS')
    reply = dict(original, kind='info', reply_required=False, target=original['agent_name'],
                 agent_name=original['target'], text=content['text'], result=content['result'])
    correlate(original, reply, allowed)
    return reply


def validate_reference(reference, allowed):
    exact(reference, ('nonce', 'msgid', 'target', 'reply_to'))
    require(isinstance(reference['nonce'], str) and NONCE.fullmatch(reference['nonce']), 'INVALID_NONCE')
    for key in ('msgid', 'target'):
        require(isinstance(reference[key], str) and ID.fullmatch(reference[key]), 'INVALID_ID')
    endpoint(reference['reply_to'], allowed, '/inbox')
    reject_secrets(dumps(reference), reference['nonce'])
    return reference


def http_call(url, allowed, method, token, body=None):
    u = endpoint(url, allowed)
    connection = (http.client.HTTPSConnection if u.scheme == 'https' else http.client.HTTPConnection)(
        u.hostname, u.port, timeout=10)
    try:
        connection.request(method, u.path, body=body,
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'Connection': 'close'})
        response = connection.getresponse()
        raw = response.read(MAX_BODY + 1)
        require(len(raw) <= MAX_BODY, 'RESPONSE_TOO_LARGE')
        return response.status, response.getheader('Content-Type', ''), raw
    except (OSError, http.client.HTTPException, BridgeError):
        raise BridgeError('TRANSPORT_RECONCILE', 'reconciliation-needed') from None
    finally:
        connection.close()


def atomic_new(path_value, raw):
    path = safe_local(path_value)
    require(path.parent.is_dir() and not path.exists(), 'OUTPUT_COLLISION')
    fd, temporary = tempfile.mkstemp(prefix='.bridge-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # link publishes an entirely written file atomically, with O_EXCL semantics.
        os.link(temporary, path, follow_symlinks=False)
    except FileExistsError:
        raise BridgeError('OUTPUT_COLLISION') from None
    finally:
        os.unlink(temporary)


def download(request, allowed, staging_dir):
    require('document' in request, 'DOCUMENT_REQUIRED')
    directory = safe_local(staging_dir)
    require(directory.is_dir(), 'STAGING_REQUIRED')
    doc = request['document']
    target = safe_local(directory / doc['filename'])
    require(not target.exists(), 'OUTPUT_COLLISION')
    code, content_type, raw = http_call(doc['url'], allowed, 'GET', derive(secret(), request['nonce']))
    require(code == 200, 'DOCUMENT_HTTP')
    require(content_type.lower().replace(' ', '') in ('text/markdown;charset=utf-8', 'text/markdown'), 'DOCUMENT_TYPE')
    require(document_metadata(raw, doc['filename'], request) == doc, 'DOCUMENT_MISMATCH')
    reject_secrets(raw, request['nonce'])
    atomic_new(target, raw)
    return {'document': doc, 'staged_path': str(target)}


def fetch_request(reference, allowed, staging_dir):
    validate_reference(reference, allowed)
    directory = safe_local(staging_dir)
    require(directory.is_dir(), 'STAGING_REQUIRED')
    target = safe_local(directory / ('request-' + reference['nonce'] + '.json'))
    require(not target.exists(), 'OUTPUT_COLLISION')
    origin = urlsplit(reference['reply_to'])
    url = f'{origin.scheme}://{origin.netloc}/request/{reference["nonce"]}'
    code, content_type, raw = http_call(url, allowed, 'GET', derive(secret(), reference['nonce']))
    require(code == 200, 'REQUEST_HTTP')
    require(content_type.lower().replace(' ', '') in ('application/json', 'application/json;charset=utf-8'), 'REQUEST_TYPE')
    request = validate_envelope(parse_json(raw), allowed)
    require(request['kind'] == 'request' and all(request[key] == value for key, value in reference.items()), 'REQUEST_REFERENCE')
    reject_secrets(raw, reference['nonce'])
    atomic_new(target, dumps(request))
    return {'staged_path': str(target), 'msgid': request['msgid'], 'nonce': request['nonce'],
            'target': request['target'], 'kat': 'passed'}


def inbox(request, allowed, bind, port, output, ready_file=None, raw_document=None):
    # Snapshot the normalized envelope once; callers cannot change served bytes later.
    request = parse_json(dumps(validate_envelope(request, allowed)))
    request_bytes = dumps(request)
    require(request['kind'] == 'request', 'REQUEST_REQUIRED')
    endpoint(f'http://{bind}:{port}/inbox', allowed, '/inbox')
    callback = urlsplit(request['reply_to'])
    require(callback.hostname == bind and (callback.port or (443 if callback.scheme == 'https' else 80)) == port
            and callback.scheme == 'http', 'BIND_MISMATCH')
    require(('document' in request) == (raw_document is not None), 'DOCUMENT_REQUIRED')
    require(not safe_local(output).exists(), 'OUTPUT_COLLISION')
    token = derive(secret(), request['nonce'])
    lock = threading.Lock()
    done = threading.Event()
    stop = threading.Event()
    state = {}
    deadline = time.monotonic() + request['ttl_seconds']

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(2)

        def log_message(self, *args):
            pass

        def answer(self, status, raw=b'', content_type='application/json'):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            return hmac.compare_digest(self.headers.get('Authorization', '').encode('utf-8'),
                                       ('Bearer ' + token).encode('utf-8'))

        def do_GET(self):
            if not self.authorized():
                return self.answer(401)
            if time.monotonic() >= deadline or done.is_set():
                return self.answer(410)
            if self.path == '/request/' + request['nonce']:
                return self.answer(200, request_bytes, 'application/json; charset=utf-8')
            if self.path != '/document/' + request['nonce'] or raw_document is None:
                return self.answer(404)
            self.answer(200, raw_document, 'text/markdown; charset=utf-8')

        def do_POST(self):
            if not self.authorized():
                return self.answer(401)
            if self.path != '/inbox':
                return self.answer(404)
            try:
                require(self.headers.get('Content-Type', '').split(';')[0].strip().lower() == 'application/json')
                lengths = self.headers.get_all('Content-Length', [])
                require(len(lengths) == 1 and lengths[0].isdigit() and not self.headers.get('Transfer-Encoding'))
                length = int(lengths[0])
                require(0 < length <= MAX_BODY)
                raw = self.rfile.read(length)
                require(len(raw) == length)
                reply = parse_json(raw)
                correlate(request, reply, allowed)
                with lock:
                    if 'reply' in state or time.monotonic() >= deadline:
                        return self.answer(409)
                    atomic_new(output, dumps(reply))
                    state['reply'] = reply
                try:
                    self.answer(200, b'{"accepted":true}')
                    self.wfile.flush()
                finally:
                    done.set()
            except (BridgeError, OSError, ValueError):
                self.answer(400)

        def do_PUT(self):
            self.answer(405)

        do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = do_PUT

    class Server(ThreadingHTTPServer):
        daemon_threads = False
        block_on_close = True

        def __init__(self, *args):
            self.active_sockets = set()
            self.sockets_lock = threading.Lock()
            super().__init__(*args)

        def get_request(self):
            connection, address = super().get_request()
            with self.sockets_lock:
                self.active_sockets.add(connection)
            return connection, address

        def shutdown_request(self, connection):
            try:
                super().shutdown_request(connection)
            finally:
                with self.sockets_lock:
                    self.active_sockets.discard(connection)

        def cancel_active(self):
            # Idle timeouts cannot stop clients that continually drip bytes.
            # Wake every blocked header/body reader before joining its thread.
            with self.sockets_lock:
                connections = tuple(self.active_sockets)
            for connection in connections:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.close()

        def handle_error(self, *args):
            pass

    server = Server((bind, port), Handler)
    server.timeout = 0.1
    old_handlers = {}
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT):
            old_handlers[sig] = signal.signal(sig, lambda *_: stop.set())
    try:
        if ready_file:
            atomic_new(ready_file, dumps({'status': 'ready', 'msgid': request['msgid'],
                                         'nonce': request['nonce'], 'envelope': request}))
        while not done.is_set() and not stop.is_set() and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.cancel_active()
        server.server_close()
        for sig, previous in old_handlers.items():
            signal.signal(sig, previous)
    if not done.is_set():
        raise BridgeError('INTERRUPTED' if stop.is_set() else 'ROUND_TIMEOUT', 'incomplete')
    reply = state['reply']
    return {'reply': reply, 'proof_path': str(safe_local(output))}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise BridgeError('CLI_ARGUMENTS')


def parser():
    root = Parser(description='Bounded bridge; preflight performs no network calls.')
    subs = root.add_subparsers(dest='command', required=True, parser_class=Parser)
    for command in ('preflight', 'send', 'receive', 'verify'):
        p = subs.add_parser(command)
        p.add_argument('--request', required=True)
        p.add_argument('--allow-host', action='append', default=[])
        if command in ('preflight', 'receive'):
            p.add_argument('--workspace-root')
        if command in ('preflight', 'send', 'receive'):
            p.add_argument('--document-file')
        if command == 'send':
            p.add_argument('--target-url', required=True)
            p.add_argument('--reply-content-file')
        if command == 'receive':
            p.add_argument('--mode', required=True, choices=('inbox', 'document', 'request'))
            p.add_argument('--bind')
            p.add_argument('--port', type=int)
            p.add_argument('--output')
            p.add_argument('--ready-file')
            p.add_argument('--staging-dir')
        if command == 'verify':
            p.add_argument('--proof', required=True)
    return root


def execute(args):
    kat()
    args.allow_host = [host for item in args.allow_host for host in item.split(',')]
    source = load_request(args.request)
    if args.command == 'receive' and args.mode == 'request':
        require(args.staging_dir and not any((args.bind, args.port, args.output, args.ready_file,
                                              args.document_file, args.workspace_root)), 'CLI_ARGUMENTS')
        return 'staged', fetch_request(source, args.allow_host, args.staging_dir)
    request = validate_envelope(source, args.allow_host)
    if args.command == 'send' and args.reply_content_file:
        require(not args.document_file, 'CLI_ARGUMENTS')
        request = compose_reply(request, load_request(args.reply_content_file), args.allow_host)
    repo_proof = None
    if args.command == 'preflight' or (args.command == 'receive' and args.mode == 'document'):
        if 'repository' in request:
            repo_proof = check_repository(request['repository'], args.workspace_root)
    request, raw = prepare(request, args.allow_host, getattr(args, 'document_file', None))
    if args.command == 'preflight':
        return 'ready', {'envelope': request, 'kat': 'passed', 'repository': repo_proof}
    if args.command == 'send':
        path = '/hooks/wake' if request['kind'] == 'request' else '/inbox'
        endpoint(args.target_url, args.allow_host, path)
        if path == '/inbox':
            require(args.target_url == request['reply_to'], 'CALLBACK_MISMATCH')
        body = dumps({'text': dumps(request).decode('utf-8'), 'mode': 'now'}) if path == '/hooks/wake' else dumps(request)
        require(len(body) <= MAX_BODY, 'BODY_TOO_LARGE')
        token = secret() if path == '/hooks/wake' else derive(secret(), request['nonce'])
        code, _, _ = http_call(args.target_url, args.allow_host, 'POST', token, body)
        if code != 200:
            raise BridgeError('HTTP_NOT_ACCEPTED', 'reconciliation-needed')
        return 'accepted', {'http_status': code, 'msgid': request['msgid'], 'nonce': request['nonce']}
    if args.command == 'receive':
        if args.mode == 'document':
            require(args.staging_dir and not any((args.bind, args.port, args.output, args.ready_file, args.document_file)), 'CLI_ARGUMENTS')
            data = download(request, args.allow_host, args.staging_dir)
            data['repository'] = repo_proof
            return 'staged', data
        require(args.bind and args.port and args.output and not args.staging_dir and
                not args.workspace_root, 'CLI_ARGUMENTS')
        data = inbox(request, args.allow_host, args.bind, args.port, args.output, args.ready_file, raw)
        return data['reply']['result']['status'], data
    reply = load_request(args.proof)
    status = correlate(request, reply, args.allow_host)
    require(status == 'complete', 'ROUND_NOT_COMPLETE')
    return 'complete', {'reply': reply}


def main(argv=None):
    start = time.monotonic()
    command = (argv or sys.argv[1:] or ['unknown'])[0]
    try:
        args = parser().parse_args(argv)
        command = args.command
        status, data = execute(args)
        output = {'ok': status not in ('failed', 'blocked'), 'command': command, 'status': status, 'data': data, 'error': None}
    except BridgeError as exc:
        output = {'ok': False, 'command': command if command in ('preflight', 'send', 'receive', 'verify') else 'unknown',
                  'status': exc.status, 'data': None, 'error': {'code': exc.code}}
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError, UnicodeError):
        output = {'ok': False, 'command': command if command in ('preflight', 'send', 'receive', 'verify') else 'unknown',
                  'status': 'rejected', 'data': None, 'error': {'code': 'LOCAL_OPERATION_FAILED'}}
    output['timing'] = {'elapsedMs': round((time.monotonic() - start) * 1000, 3)}
    # User content and evidence are untrusted; do not echo a secret supplied in them.
    encoded = dumps(output)
    key = os.environ.get('OPENCLAW_HOOK_TOKEN', '')
    if key and (key.encode('utf-8') in encoded or dumps(key)[1:-1] in encoded):
        output['ok'] = False
        encoded = dumps({'ok': False, 'command': command, 'status': 'rejected', 'data': None,
                         'error': {'code': 'SECRET_IN_OUTPUT'}, 'timing': output['timing']})
    print(encoded.decode('utf-8'))
    return 0 if output['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
