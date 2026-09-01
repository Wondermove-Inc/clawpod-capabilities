#!/usr/bin/env python3
"""Fail-closed controller for accountless Cloudflare Quick Tunnel previews."""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import fcntl
import hashlib
import ipaddress
import json
import math
import os
import re
import select
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

VERSION = "0.1.6"
SUPERVISOR_EXECUTABLE = os.path.realpath(sys.executable)
STATE_VERSION = 1
MAX_READ_LOG = 16_384
MAX_DIAGNOSTIC = 512
STATE_KEYS = {
    "schemaVersion", "instanceId", "pid", "pidStart", "binary",
    "supervisorPid", "supervisorStart", "supervisorBinary", "url",
    "target", "createdAt", "expiresAt", "logName",
}
BINARY_KEYS = {"path", "sha256", "device", "inode"}
AUTH_ENV_NAMES = (
    "TUNNEL_TOKEN", "TUNNEL_ORIGIN_CERT", "CF_TUNNEL_TOKEN",
    "CLOUDFLARED_CONFIG",
)


class Fail(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(131_072), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_binary(value: str) -> dict:
    path = Path(value)
    if not path.is_absolute():
        raise Fail("UNSAFE_BINARY", "cloudflared must be an absolute path")
    try:
        metadata = os.lstat(path)
    except OSError:
        raise Fail("UNSAFE_BINARY", "cloudflared is unavailable")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise Fail("UNSAFE_BINARY", "cloudflared must be a regular non-symlink")
    if not os.access(path, os.X_OK) or metadata.st_mode & 0o022:
        raise Fail("UNSAFE_BINARY", "cloudflared must be executable and not group/world writable")
    return {
        "path": str(path),
        "sha256": sha256(path),
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
    }


def secure_root(value: str | Path, create: bool = False) -> Path:
    path = Path(value)
    if create:
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
    try:
        metadata = os.lstat(path)
    except OSError:
        raise Fail("STATE_UNAVAILABLE", "state root is unavailable")
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o777 != 0o700
    ):
        raise Fail("UNSAFE_STATE", "state root must be owner-owned with mode 0700 access bits")
    return path


def secure_regular(path: Path, label: str) -> None:
    try:
        metadata = os.lstat(path)
    except OSError:
        raise Fail("STATE_UNAVAILABLE", f"{label} is unavailable")
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise Fail("UNSAFE_STATE", f"{label} must be owner-owned mode 0600")


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextlib.contextmanager
def state_lock(root_value: str | Path, create: bool = False):
    root = secure_root(root_value, create=create)
    lock_path = root / "lock"
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
    existed = lock_path.exists()
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError:
        raise Fail("UNSAFE_STATE", "cannot open state lock safely")
    try:
        if existed:
            secure_regular(lock_path, "lock file")
        else:
            os.fchmod(descriptor, 0o600)
            secure_regular(lock_path, "lock file")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield root
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def valid_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    hostname = parsed.hostname or ""
    label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    return (
        parsed.scheme == "https"
        and port is None
        and parsed.username is None
        and parsed.password is None
        and parsed.path in ("", "/")
        and not parsed.query
        and not parsed.fragment
        and re.fullmatch(label + r"\.trycloudflare\.com", hostname) is not None
    )


def validated_target(host: str, port: int, connect: bool = True) -> str:
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65_535:
        raise Fail("INVALID_PORT", "port must be an integer from 1 through 65535")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise Fail("UNSAFE_TARGET", "host must be a loopback IP literal")
    if not address.is_loopback:
        raise Fail("UNSAFE_TARGET", "target must be loopback-only")
    if connect:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                pass
        except OSError:
            raise Fail("TARGET_UNAVAILABLE", "local target is unavailable")
    rendered_host = f"[{host}]" if address.version == 6 else host
    return f"http://{rendered_host}:{port}"


def validate_target_string(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
        address = ipaddress.ip_address(parsed.hostname or "")
    except (ValueError, TypeError):
        return False
    return (
        parsed.scheme == "http"
        and address.is_loopback
        and isinstance(port, int)
        and 1 <= port <= 65_535
        and parsed.username is None
        and parsed.password is None
        and parsed.path in ("", "/")
        and not parsed.query
        and not parsed.fragment
    )


def reject_auth_state() -> None:
    for name in AUTH_ENV_NAMES:
        if os.environ.get(name):
            raise Fail("AUTH_STATE_PRESENT", "Cloudflare credential/config environment is not allowed")
    directory = Path.home() / ".cloudflared"
    for name in ("config.yml", "config.yaml", "cert.pem", "credentials.json"):
        if (directory / name).exists():
            raise Fail("AUTH_STATE_PRESENT", "Cloudflare config/auth state is present")


def process_start(pid: int) -> str | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[19]
    except (OSError, IndexError):
        return None


def validate_binary_state(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != BINARY_KEYS:
        raise Fail("MALFORMED_STATE", "binary metadata shape is invalid")
    if not isinstance(value["path"], str) or not Path(value["path"]).is_absolute():
        raise Fail("MALFORMED_STATE", "binary path is invalid")
    if not isinstance(value["sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is None:
        raise Fail("MALFORMED_STATE", "binary digest is invalid")
    for name in ("device", "inode"):
        if isinstance(value[name], bool) or not isinstance(value[name], int) or value[name] < 0:
            raise Fail("MALFORMED_STATE", f"binary {name} is invalid")
    return value


def validate_state(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != STATE_KEYS:
        raise Fail("MALFORMED_STATE", "state shape is invalid")
    if value["schemaVersion"] != STATE_VERSION:
        raise Fail("MALFORMED_STATE", "state schema version is invalid")
    if not isinstance(value["instanceId"], str) or re.fullmatch(r"[0-9a-f]{32}", value["instanceId"]) is None:
        raise Fail("MALFORMED_STATE", "instance ID is invalid")
    if isinstance(value["pid"], bool) or not isinstance(value["pid"], int) or value["pid"] <= 1:
        raise Fail("MALFORMED_STATE", "PID is invalid")
    if not isinstance(value["pidStart"], str) or re.fullmatch(r"[1-9][0-9]*", value["pidStart"]) is None:
        raise Fail("MALFORMED_STATE", "PID start identity is invalid")
    validate_binary_state(value["binary"])
    if isinstance(value["supervisorPid"], bool) or not isinstance(value["supervisorPid"], int) or value["supervisorPid"] <= 1:
        raise Fail("MALFORMED_STATE", "supervisor PID is invalid")
    if not isinstance(value["supervisorStart"], str) or re.fullmatch(r"[1-9][0-9]*", value["supervisorStart"]) is None:
        raise Fail("MALFORMED_STATE", "supervisor start identity is invalid")
    validate_binary_state(value["supervisorBinary"])
    if not valid_url(value["url"]):
        raise Fail("MALFORMED_STATE", "public URL is invalid")
    if not validate_target_string(value["target"]):
        raise Fail("MALFORMED_STATE", "target URL is invalid")
    for name in ("createdAt", "expiresAt"):
        number = value[name]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number <= 0:
            raise Fail("MALFORMED_STATE", f"{name} is invalid")
    if value["expiresAt"] <= value["createdAt"] or value["expiresAt"] - value["createdAt"] > 86_401:
        raise Fail("MALFORMED_STATE", "state time range is invalid")
    expected_log = f"cloudflared-{value['instanceId']}.log"
    if value["logName"] != expected_log:
        raise Fail("MALFORMED_STATE", "log identity is invalid")
    return value


def load_state(root: Path, optional: bool = False) -> dict | None:
    path = root / "state.json"
    if not path.exists():
        if optional:
            return None
        raise Fail("NOT_RUNNING", "no tunnel state")
    secure_regular(path, "state file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise Fail("MALFORMED_STATE", "state is not valid UTF-8 JSON")
    return validate_state(value)


def save_state(root: Path, state: dict) -> None:
    validate_state(state)
    descriptor, temporary = tempfile.mkstemp(prefix=".state-", dir=root)
    os.fchmod(descriptor, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(state, stream, separators=(",", ":"), sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, root / "state.json")
        fsync_directory(root)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def remove_artifacts(root: Path, state: dict) -> None:
    (root / "state.json").unlink(missing_ok=True)
    (root / state["logName"]).unlink(missing_ok=True)
    fsync_directory(root)


def identity_is_owned(pid: int, pid_start: str, binary: dict, label: str) -> bool:
    current_start = process_start(pid)
    if current_start is None:
        return False
    if current_start != pid_start:
        raise Fail("FOREIGN_PID", f"{label} PID identity changed")
    try:
        executable = os.readlink(f"/proc/{pid}/exe")
    except OSError:
        raise Fail("FOREIGN_PID", f"{label} executable cannot be verified")
    if executable.endswith(" (deleted)") or os.path.realpath(executable) != os.path.realpath(binary["path"]):
        raise Fail("FOREIGN_PID", f"{label} executable differs from state")
    if inspect_binary(binary["path"]) != binary:
        raise Fail("BINARY_CHANGED", f"{label} binary changed")
    return True


def process_is_owned(state: dict) -> bool:
    return identity_is_owned(state["pid"], state["pidStart"], state["binary"], "cloudflared")


def supervisor_is_owned(state: dict) -> bool:
    return identity_is_owned(state["supervisorPid"], state["supervisorStart"], state["supervisorBinary"], "supervisor")


def wait_until_dead(pid: int, pid_start: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = process_start(pid)
        if current is None or current != pid_start:
            return True
        time.sleep(0.05)
    current = process_start(pid)
    return current is None or current != pid_start


def terminate_owned(state: dict) -> bool:
    child_live = process_is_owned(state)
    supervisor_live = supervisor_is_owned(state)
    if not child_live and not supervisor_live:
        return False
    if supervisor_live:
        os.kill(state["supervisorPid"], signal.SIGTERM)
        wait_until_dead(state["supervisorPid"], state["supervisorStart"], 4.0)
    if process_is_owned(state):
        os.kill(state["pid"], signal.SIGTERM)
        if not wait_until_dead(state["pid"], state["pidStart"], 3.0) and process_is_owned(state):
            os.kill(state["pid"], signal.SIGKILL)
            if not wait_until_dead(state["pid"], state["pidStart"], 2.0):
                raise Fail("TERMINATION_FAILED", "owned cloudflared process did not exit")
    if supervisor_is_owned(state):
        os.kill(state["supervisorPid"], signal.SIGKILL)
        if not wait_until_dead(state["supervisorPid"], state["supervisorStart"], 2.0):
            raise Fail("TERMINATION_FAILED", "owned supervisor did not exit")
    return True


def cleanup_spawned(process: subprocess.Popen, pid_start: str | None) -> None:
    if process.poll() is not None:
        process.wait(timeout=0)
        return
    process.terminate()
    try:
        process.wait(timeout=3)
        return
    except subprocess.TimeoutExpired:
        process.kill()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if pid_start and process_start(process.pid) == pid_start:
            raise Fail("TERMINATION_FAILED", "spawned process could not be cleaned up")


def read_discovery_log(path: Path) -> str:
    secure_regular(path, "tunnel log")
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(max(0, size - MAX_READ_LOG))
        raw = stream.read(MAX_READ_LOG)
    return raw.decode("utf-8", "replace")


def sanitized_diagnostic(text: str) -> str:
    text = re.sub(
        r"(?i)(token|secret|password|authorization)(\s*[=:]\s*)\S+",
        r"\1\2[REDACTED]",
        text,
    )
    text = re.sub(r"https://[^\s]+", "[URL]", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "?", text)
    return text[-MAX_DIAGNOSTIC:]


def result(command: str, data: dict, effects: list[str] | None = None) -> dict:
    return {
        "ok": True,
        "schemaVersion": 1,
        "command": command,
        "data": data,
        "effects": effects or [],
    }


def reconcile_dead(root: Path, state: dict) -> bool:
    child_live = process_is_owned(state)
    supervisor_live = supervisor_is_owned(state)
    if child_live and supervisor_live:
        return False
    if child_live or supervisor_live:
        terminate_owned(state)
    remove_artifacts(root, state)
    return True


def command_status(args) -> dict:
    if not Path(args.state_root).exists():
        return result("status", {"state": "absent", "version": VERSION})
    with state_lock(args.state_root) as root:
        state = load_state(root, optional=True)
        if state is None:
            return result("status", {"state": "stopped", "version": VERSION})
        running = process_is_owned(state) and supervisor_is_owned(state)
        return result("status", {
            "state": "running" if running else "stale",
            "expired": time.time() >= state["expiresAt"],
            "url": state["url"] if running else None,
            "expiresAt": state["expiresAt"],
            "version": VERSION,
        })


def command_preflight(args) -> dict:
    with state_lock(args.state_root, create=True):
        reject_auth_state()
        binary = inspect_binary(args.cloudflared)
        target = validated_target(args.host, args.port, not args.skip_connect)
    return result("preflight", {"ready": True, "binary": binary, "target": target})


def command_inspect(args) -> dict:
    with state_lock(args.state_root) as root:
        state = load_state(root)
        running = process_is_owned(state) and supervisor_is_owned(state)
        return result("inspect", {
            "state": "running" if running else "stale",
            "url": state["url"] if running else None,
            "target": state["target"],
            "createdAt": state["createdAt"],
            "expiresAt": state["expiresAt"],
            "expired": time.time() >= state["expiresAt"],
        })


def command_stop(args) -> dict:
    if not Path(args.state_root).exists():
        return result("stop", {"state": "stopped", "changed": False})
    with state_lock(args.state_root) as root:
        state = load_state(root, optional=True)
        if state is None:
            return result("stop", {"state": "stopped", "changed": False})
        if reconcile_dead(root, state):
            return result("stop", {"state": "stopped", "changed": False, "reconciled": True})
        terminate_owned(state)
        remove_artifacts(root, state)
        return result("stop", {"state": "stopped", "changed": True}, ["owned tunnel terminated"])


def _parent_death_signal() -> None:
    # Linux-only capability: ensure cloudflared receives SIGTERM if its supervisor dies.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_PDEATHSIG) failed")
    if os.getppid() == 1:
        os.kill(os.getpid(), signal.SIGTERM)


def _sanitize_log_tail(tail: bytes) -> bytes:
    text = tail.decode("utf-8", "replace")
    text = re.sub(r"(?i)(token|secret|password|authorization)(\s*[=:]\s*)\S+", r"\1\2[REDACTED]", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "?", text)
    return text.encode("utf-8", "replace")[-MAX_READ_LOG:]


def _write_bounded_log(path: Path, tail: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".log-", dir=path.parent)
    os.fchmod(descriptor, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_sanitize_log_tail(tail))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def command_supervise(args) -> dict:
    root = secure_root(args.state_root)
    binary = inspect_binary(args.cloudflared)
    reject_auth_state()
    if not validate_target_string(args.target):
        raise Fail("UNSAFE_TARGET", "supervisor target must be a loopback HTTP URL")
    if re.fullmatch(r"cloudflared-[0-9a-f]{32}\.log", args.log_name) is None:
        raise Fail("UNSAFE_STATE", "supervisor log identity is invalid")
    log_path = root / args.log_name
    if log_path.exists():
        secure_regular(log_path, "tunnel log")
    stop_requested = False
    def request_stop(_signum, _frame):
        nonlocal stop_requested
        stop_requested = True
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    child = subprocess.Popen(
        [binary["path"], "tunnel", "--no-autoupdate", "--config", "/dev/null", "--url", args.target],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        close_fds=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(root), "LANG": "C.UTF-8"},
        preexec_fn=_parent_death_signal,
    )
    child_start = process_start(child.pid)
    if child_start is None:
        child.wait()
        raise Fail("EARLY_DEATH", "cloudflared exited before identity capture")
    event_sent = False
    tail = b""
    try:
        os.set_blocking(child.stdout.fileno(), False)
        while True:
            if stop_requested and child.poll() is None:
                child.terminate()
            ready, _, _ = select.select([child.stdout], [], [], 0.1)
            if ready:
                chunk = os.read(child.stdout.fileno(), 65_536)
                if chunk:
                    tail = (tail + chunk)[-MAX_READ_LOG:]
                    _write_bounded_log(log_path, tail)
                    if not event_sent:
                        text = tail.decode("utf-8", "replace")
                        for candidate in re.findall(r"https://[^\s]+", text):
                            if valid_url(candidate):
                                print(json.dumps({"url": candidate, "pid": child.pid, "pidStart": child_start}), flush=True)
                                event_sent = True
                                break
            code = child.poll()
            if code is not None:
                # Drain the final bounded chunk.
                try:
                    chunk = os.read(child.stdout.fileno(), 65_536)
                except BlockingIOError:
                    chunk = b""
                if chunk:
                    tail = (tail + chunk)[-MAX_READ_LOG:]
                    _write_bounded_log(log_path, tail)
                return result("_supervise", {"exitCode": code})
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait(timeout=2)


def _read_supervisor_event(process: subprocess.Popen, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    diagnostic = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise Fail("EARLY_DEATH", "supervisor exited before URL discovery")
        ready, _, _ = select.select([process.stdout], [], [], min(0.1, deadline - time.monotonic()))
        if ready:
            line = process.stdout.readline(4096)
            try:
                event = json.loads(line)
            except (UnicodeError, json.JSONDecodeError):
                diagnostic = sanitized_diagnostic(line)
                continue
            if set(event) == {"url", "pid", "pidStart"} and valid_url(event["url"]) and isinstance(event["pid"], int) and isinstance(event["pidStart"], str):
                return event
    raise Fail("DISCOVERY_TIMEOUT", f"valid Quick Tunnel URL not discovered: {diagnostic}")


def command_start(args) -> dict:
    if not 30 <= args.ttl <= 86_400:
        raise Fail("INVALID_TTL", "ttl must be from 30 through 86400 seconds")
    if not 1 <= args.discovery_timeout <= 30:
        raise Fail("INVALID_TIMEOUT", "discovery timeout must be from 1 through 30 seconds")
    with state_lock(args.state_root, create=True) as root:
        old_state = load_state(root, optional=True)
        if old_state is not None:
            if not reconcile_dead(root, old_state):
                raise Fail("ALREADY_RUNNING", "an owned tunnel is already running")
        binary = inspect_binary(args.cloudflared)
        supervisor_binary = inspect_binary(SUPERVISOR_EXECUTABLE)
        reject_auth_state()
        target = validated_target(args.host, args.port)
        instance_id = uuid.uuid4().hex
        log_name = f"cloudflared-{instance_id}.log"
        supervisor = None
        supervisor_start = None
        state_saved = False
        try:
            supervisor = subprocess.Popen(
                [SUPERVISOR_EXECUTABLE, str(Path(__file__).resolve()), "_supervise",
                 "--state-root", str(root), "--cloudflared", binary["path"],
                 "--target", target, "--log-name", log_name],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, start_new_session=True, close_fds=True,
            )
            supervisor_start = process_start(supervisor.pid)
            if supervisor_start is None:
                raise Fail("EARLY_DEATH", "supervisor exited before identity capture")
            event = _read_supervisor_event(supervisor, args.discovery_timeout)
            supervisor.stdout.close()
            # The child executable and immutable binary identity must still match after discovery.
            child_identity = {"pid": event["pid"], "pidStart": event["pidStart"], "binary": binary}
            if not process_is_owned(child_identity):
                raise Fail("EARLY_DEATH", "cloudflared exited during URL discovery")
            now = time.time()
            state = {
                "schemaVersion": STATE_VERSION, "instanceId": instance_id,
                "pid": event["pid"], "pidStart": event["pidStart"], "binary": binary,
                "supervisorPid": supervisor.pid, "supervisorStart": supervisor_start,
                "supervisorBinary": supervisor_binary, "url": event["url"], "target": target,
                "createdAt": now, "expiresAt": now + args.ttl, "logName": log_name,
            }
            save_state(root, state); state_saved = True
            subprocess.Popen(
                [SUPERVISOR_EXECUTABLE, str(Path(__file__).resolve()), "_reap", "--state-root", str(root),
                 "--expected-instance", instance_id, "--expected-pid", str(event["pid"]),
                 "--expected-pid-start", event["pidStart"], "--expected-supervisor-pid", str(supervisor.pid),
                 "--expected-supervisor-start", supervisor_start, "--expires-at", str(state["expiresAt"])],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True, close_fds=True,
            )
            return result("start", {"state": "running", "url": event["url"], "expiresAt": state["expiresAt"]},
                          ["external tunnel created", "bounded log supervisor started", "TTL reaper started"])
        except Exception:
            if supervisor is not None:
                if supervisor.stdout is not None and not supervisor.stdout.closed:
                    supervisor.stdout.close()
                cleanup_spawned(supervisor, supervisor_start)
            if state_saved:
                (root / "state.json").unlink(missing_ok=True)
            (root / log_name).unlink(missing_ok=True)
            fsync_directory(root)
            raise

def command_reap(args) -> dict:
    delay = max(0.0, args.expires_at - time.time())
    time.sleep(delay)
    if not Path(args.state_root).exists():
        return result("_reap", {"changed": False})
    with state_lock(args.state_root) as root:
        state = load_state(root, optional=True)
        if state is None:
            return result("_reap", {"changed": False})
        expected = (args.expected_instance, args.expected_pid, args.expected_pid_start, args.expected_supervisor_pid, args.expected_supervisor_start)
        actual = (state["instanceId"], state["pid"], state["pidStart"], state["supervisorPid"], state["supervisorStart"])
        if actual != expected or state["expiresAt"] != args.expires_at:
            return result("_reap", {"changed": False})
        if time.time() < state["expiresAt"]:
            return result("_reap", {"changed": False})
        if process_is_owned(state) or supervisor_is_owned(state):
            terminate_owned(state)
        remove_artifacts(root, state)
        return result("_reap", {"changed": True})


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser()
    commands = top.add_subparsers(dest="command", required=True)
    for name in ("status", "inspect", "stop"):
        command = commands.add_parser(name)
        command.add_argument("--state-root", required=True)
    for name in ("preflight", "start"):
        command = commands.add_parser(name)
        command.add_argument("--state-root", required=True)
        command.add_argument("--cloudflared", required=True)
        command.add_argument("--host", default="127.0.0.1")
        command.add_argument("--port", required=True, type=int)
        if name == "preflight":
            command.add_argument("--skip-connect", action="store_true")
        else:
            command.add_argument("--ttl", type=int, default=3600)
            command.add_argument("--discovery-timeout", type=float, default=10)
    supervise = commands.add_parser("_supervise", help=argparse.SUPPRESS)
    supervise.add_argument("--state-root", required=True)
    supervise.add_argument("--cloudflared", required=True)
    supervise.add_argument("--target", required=True)
    supervise.add_argument("--log-name", required=True)
    reap = commands.add_parser("_reap", help=argparse.SUPPRESS)
    reap.add_argument("--state-root", required=True)
    reap.add_argument("--expected-instance", required=True)
    reap.add_argument("--expected-pid", required=True, type=int)
    reap.add_argument("--expected-pid-start", required=True)
    reap.add_argument("--expected-supervisor-pid", required=True, type=int)
    reap.add_argument("--expected-supervisor-start", required=True)
    reap.add_argument("--expires-at", required=True, type=float)
    return top


def execute(args) -> dict:
    handlers = {
        "status": command_status,
        "preflight": command_preflight,
        "start": command_start,
        "inspect": command_inspect,
        "stop": command_stop,
        "_supervise": command_supervise,
        "_reap": command_reap,
    }
    return handlers[args.command](args)


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        response = execute(args)
        code = 0
    except Fail as error:
        response = {
            "ok": False,
            "schemaVersion": 1,
            "command": args.command,
            "error": {"code": error.code, "message": error.message},
            "effects": [],
        }
        code = 2
    print(json.dumps(response, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
