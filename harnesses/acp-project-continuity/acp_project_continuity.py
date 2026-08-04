#!/usr/bin/env python3
"""Pure-local, fail-closed ACP project/session continuity registry."""
from __future__ import annotations

import argparse
import hashlib
import fcntl
import json
import os
import re
import subprocess
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

VERSION = "0.2.0"
SCHEMA_VERSION = 2
AGENTS = ("claude", "codex")
MAX_STATE_BYTES = 1_048_576
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
GIT_OID = re.compile(r"^[0-9a-f]{40,64}$")
VERSION_NUMBER = re.compile(r"(?:^|\s)v?(\d+)\.(\d+)\.(\d+)(?:\s|$)")
MIN_ACPX_VERSION = (0, 3, 1)
MAX_PROMPT_BYTES = 65_536
MAX_ACPX_OUTPUT_BYTES = 4_194_304
REQUIRED_SESSION_CAPABILITIES = ("loadSession", "resume", "list", "close")
SECRET_LIKE = re.compile(
    r"(?i)(authorization|bearer\s+|oauth|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|password|passwd|private[_-]?key|secret(?:\s|_|-)*[:=]|"
    r"-----BEGIN|(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9])"
)


class Failure(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def fail(code: str, message: str) -> None:
    raise Failure(code, message)


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        fail("invalid_input", "command arguments are invalid")


def text(value: Any, label: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or SECRET_LIKE.search(value):
        fail("secret_like_input" if isinstance(value, str) and SECRET_LIKE.search(value or "") else "invalid_input", f"{label} is invalid")
    if identifier and not IDENTIFIER.fullmatch(value):
        fail("invalid_input", f"{label} has invalid syntax")
    return value


def reject_secret_like_tree(value: Any) -> None:
    if isinstance(value, str):
        if SECRET_LIKE.search(value):
            fail("secret_like_state", "state contains secret-like material")
    elif isinstance(value, dict):
        for key, item in value.items():
            reject_secret_like_tree(key)
            reject_secret_like_tree(item)
    elif isinstance(value, list):
        for item in value:
            reject_secret_like_tree(item)


def safe_path(raw: str, root_raw: str, label: str, *, may_be_missing: bool = False) -> Path:
    text(raw, label)
    text(root_raw, f"{label} root")
    root_path = Path(root_raw)
    if not root_path.is_absolute() or not root_path.is_dir() or root_path.is_symlink():
        fail("path_contract", f"{label} root must be an absolute, existing, non-symlink directory")
    root = root_path.resolve(strict=True)
    candidate = Path(raw)
    if not candidate.is_absolute():
        fail("path_contract", f"{label} must be absolute")
    cursor = candidate
    while cursor != root and cursor != cursor.parent:
        if cursor.is_symlink():
            fail("symlink_rejected", f"{label} contains a symlink")
        cursor = cursor.parent
    try:
        resolved = candidate.resolve(strict=not may_be_missing)
    except (OSError, RuntimeError):
        fail("path_contract", f"{label} cannot be resolved")
    if resolved != root and root not in resolved.parents:
        fail("path_contract", f"{label} is outside its explicit root")
    return resolved


def empty_state() -> dict[str, Any]:
    return {"schemaVersion": SCHEMA_VERSION, "revision": 0, "onboarding": None, "projects": {}}


def validate_state(data: Any) -> dict[str, Any]:
    reject_secret_like_tree(data)
    if not isinstance(data, dict) or set(data) != {"schemaVersion", "revision", "onboarding", "projects"}:
        fail("malformed_state", "state structure is invalid")
    if data["schemaVersion"] != SCHEMA_VERSION or not isinstance(data["revision"], int) or isinstance(data["revision"], bool) or data["revision"] < 0:
        fail("malformed_state", "state header is invalid")
    onboarding = data["onboarding"]
    if onboarding is not None:
        if not isinstance(onboarding, dict) or set(onboarding) != {"agents", "version"} or onboarding.get("version") != VERSION:
            fail("malformed_state", "onboarding record is invalid")
        agents = onboarding.get("agents")
        if not isinstance(agents, list) or not agents or agents != sorted(set(agents)) or set(agents) - set(AGENTS):
            fail("malformed_state", "onboarding agents are invalid")
    projects = data["projects"]
    if not isinstance(projects, dict):
        fail("malformed_state", "projects must be an object")
    for project_id, project in projects.items():
        text(project_id, "stored project id", identifier=True)
        if not isinstance(project, dict) or set(project) != {"repo", "cwd", "branch", "head", "sessions", "leases"}:
            fail("malformed_state", "stored project is invalid")
        for key in ("repo", "cwd", "branch", "head"):
            text(project.get(key), f"stored {key}")
        if not GIT_OID.fullmatch(project["head"]):
            fail("malformed_state", "stored git head is invalid")
        if not isinstance(project["sessions"], dict) or set(project["sessions"]) - set(AGENTS):
            fail("malformed_state", "stored sessions are invalid")
        if not isinstance(project["leases"], dict) or set(project["leases"]) - set(AGENTS):
            fail("malformed_state", "stored leases are invalid")
        for session in project["sessions"].values():
            if not isinstance(session, dict) or set(session) != {"sessionName", "acpxRecordId", "acpxSessionId", "agentSessionId", "generation", "closed", "lastResult"}:
                fail("malformed_state", "stored session is invalid")
            for field in ("sessionName", "acpxRecordId", "acpxSessionId"):
                text(session.get(field), f"stored {field}", identifier=True)
            if session.get("agentSessionId") is not None:
                text(session["agentSessionId"], "stored agent session id", identifier=True)
            result = session.get("lastResult")
            if not isinstance(result, dict) or set(result) != {"stopReason", "completed"} or not isinstance(result.get("completed"), bool):
                fail("malformed_state", "stored result metadata is invalid")
            if result.get("stopReason") is not None:
                text(result["stopReason"], "stored stop reason", identifier=True)
            if not isinstance(session.get("generation"), int) or isinstance(session["generation"], bool) or session["generation"] < 1 or not isinstance(session.get("closed"), bool):
                fail("malformed_state", "stored session values are invalid")
        for lease in project["leases"].values():
            if not isinstance(lease, dict) or set(lease) != {"token", "expiresAt"}:
                fail("malformed_state", "stored lease is invalid")
            text(lease.get("token"), "stored lease token", identifier=True)
            if not isinstance(lease.get("expiresAt"), int) or isinstance(lease["expiresAt"], bool) or lease["expiresAt"] < 0:
                fail("malformed_state", "stored lease expiry is invalid")
    return data


class Store:
    def __init__(self, args: argparse.Namespace):
        self.path = safe_path(args.state_file, args.state_root, "state file", may_be_missing=True)
        if not self.path.parent.is_dir() or self.path.parent.is_symlink():
            fail("path_contract", "state parent must be an existing non-symlink directory")
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        if self.lock_path.exists() and self.lock_path.is_symlink():
            fail("symlink_rejected", "lock file is a symlink")

    def transact(self, write: bool, operation: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(self.lock_path, flags, 0o600)
        except OSError:
            fail("lock_error", "state lock cannot be opened safely")
        with os.fdopen(fd, "r+") as lock:
            os.fchmod(lock.fileno(), 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX if write else fcntl.LOCK_SH)
            state = self.load()
            result = operation(state)
            if write:
                self.save(state)
            return result

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return empty_state()
        if self.path.is_symlink():
            fail("symlink_rejected", "state file is a symlink")
        try:
            info = self.path.stat()
            if not stat.S_ISREG(info.st_mode):
                fail("path_contract", "state file is not regular")
            if info.st_size > MAX_STATE_BYTES:
                fail("state_too_large", "state file exceeds the size limit")
            if stat.S_IMODE(info.st_mode) & 0o077:
                fail("unsafe_permissions", "state file must not be accessible to group or others")
            raw = self.path.read_bytes()
            data = json.loads(raw.decode("utf-8"))
        except Failure:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError):
            fail("malformed_state", "state file is malformed")
        return validate_state(data)

    def save(self, state: dict[str, Any]) -> None:
        state["revision"] += 1
        validate_state(state)
        payload = (json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
        if len(payload) > MAX_STATE_BYTES:
            fail("state_too_large", "state update exceeds the size limit")
        fd, temporary = tempfile.mkstemp(prefix=".continuity-", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, payload)
            os.fsync(fd)
            os.close(fd)
            fd = -1
            os.replace(temporary, self.path)
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if fd >= 0:
                os.close(fd)
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def compare_revision(state: dict[str, Any], args: argparse.Namespace) -> None:
    if args.expected_revision != state["revision"]:
        fail("stale_revision", "expected revision is stale")


def onboarded(state: dict[str, Any], agent: str | None = None) -> None:
    record = state["onboarding"]
    if record is None:
        fail("onboarding_required", "run post-install onboard for codex, claude, or both")
    if agent is not None and agent not in record["agents"]:
        fail("agent_not_onboarded", "requested agent was not included in onboarding")


def project_context(args: argparse.Namespace, *, with_agent: bool) -> tuple[str, str | None, str, str, str, str]:
    project_id = text(args.project_id, "project id", identifier=True)
    agent = text(args.agent, "agent", identifier=True).lower() if with_agent else None
    if agent is not None and agent not in AGENTS:
        fail("invalid_input", "agent must be codex or claude")
    safe_path(args.workspace_root, args.workspace_root, "workspace")
    repo = safe_path(args.repo, args.workspace_root, "repo")
    cwd = safe_path(args.cwd, args.workspace_root, "cwd")
    if repo != cwd and repo not in cwd.parents:
        fail("path_contract", "cwd must be inside repo")
    branch = text(args.branch, "branch")
    head = text(args.head, "head").lower()
    if not GIT_OID.fullmatch(head):
        fail("invalid_input", "head must be a full git object id")
    verify_git_context(repo, cwd, branch, head)
    return project_id, agent, str(repo), str(cwd), branch, head


def git_value(repo: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(["git", "-C", str(repo), *arguments], text=True, capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        fail("git_context", "canonical git context cannot be verified")
    if result.returncode or not result.stdout.strip():
        fail("git_context", "canonical git context cannot be verified")
    return result.stdout.strip()


def verify_git_context(repo: Path, cwd: Path, branch: str, head: str) -> None:
    if Path(git_value(cwd, "rev-parse", "--show-toplevel")).resolve() != repo:
        fail("git_context", "repo is not the canonical git root for cwd")
    if git_value(repo, "branch", "--show-current") != branch or git_value(repo, "rev-parse", "HEAD").lower() != head:
        fail("context_mismatch", "canonical git branch or head drifted")


def checked_project(state: dict[str, Any], args: argparse.Namespace) -> tuple[str, str, dict[str, Any]]:
    project_id, agent, repo, cwd, branch, head = project_context(args, with_agent=True)
    assert agent is not None
    onboarded(state, agent)
    project = state["projects"].get(project_id)
    if project is None:
        fail("project_missing", "project is not registered")
    if (project["repo"], project["cwd"], project["branch"], project["head"]) != (repo, cwd, branch, head):
        fail("context_mismatch", "repo, cwd, branch, or head does not match project")
    return project_id, agent, project


def acpx_call(binary: str, argv: list[str], *, cwd: str, timeout: int, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    binary_path = Path(binary)
    if not binary_path.is_absolute() or binary_path.is_symlink() or not binary_path.is_file() or not os.access(binary_path, os.X_OK):
        fail("acpx_missing", "bundled ACPX binary is unavailable")
    if timeout < 1 or timeout > 600:
        fail("invalid_input", "ACPX timeout must be between 1 and 600 seconds")
    try:
        result = subprocess.run([binary, *argv], cwd=cwd, input=stdin, text=True, capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError:
        fail("acpx_missing", "bundled ACPX binary is unavailable")
    except subprocess.TimeoutExpired:
        fail("acpx_timeout", "bounded ACPX command timed out")
    except OSError:
        fail("acpx_unavailable", "bundled ACPX could not be executed")
    if len(result.stdout.encode()) > MAX_ACPX_OUTPUT_BYTES or len(result.stderr.encode()) > MAX_ACPX_OUTPUT_BYTES:
        fail("acpx_output_too_large", "ACPX output exceeded the safety bound")
    if result.returncode:
        combined = (result.stderr + "\n" + result.stdout).lower()
        code = "acpx_auth_failed" if any(word in combined for word in ("auth", "login", "credential", "unauthorized")) else "acpx_failed"
        fail(code, "ACPX authentication failed" if code == "acpx_auth_failed" else "ACPX command failed")
    return result


def json_documents(raw: str) -> list[Any]:
    documents = []
    try:
        for line in raw.splitlines():
            if line.strip():
                documents.append(json.loads(line))
    except json.JSONDecodeError:
        fail("acpx_malformed_output", "ACPX returned malformed JSON")
    if not documents:
        fail("acpx_malformed_output", "ACPX returned no JSON")
    return documents


def walk(value: Any):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def find_string(documents: list[Any], keys: tuple[str, ...]) -> str | None:
    for value in walk(documents):
        if isinstance(value, dict):
            for key in keys:
                item = value.get(key)
                if isinstance(item, str) and item and IDENTIFIER.fullmatch(item):
                    return item
    return None


def preflight_acpx(binary: str, agent: str, cwd: str, timeout: int) -> str:
    version_result = acpx_call(binary, ["--version"], cwd=cwd, timeout=min(timeout, 10))
    match = VERSION_NUMBER.search(version_result.stdout + " " + version_result.stderr)
    if not match or tuple(map(int, match.groups())) < MIN_ACPX_VERSION:
        fail("acpx_version", "ACPX version is missing, malformed, or unsupported")
    # A successful agent-backed session listing proves that ACPX initialized the
    # selected adapter and that protocol session discovery is available. ACPX's
    # stable JSON result intentionally omits transient initialize metadata, so
    # ensure/load and close are verified by their actual bounded operations.
    probe = acpx_call(binary, ["--format", "json", "--json-strict", "--cwd", cwd, agent, "sessions", "list"], cwd=cwd, timeout=timeout)
    documents = json_documents(probe.stdout)
    if not any(isinstance(value, dict) and value.get("source") == "agent" and isinstance(value.get("sessions"), list) for value in documents):
        fail("acpx_capability", "agent-backed ACP session listing is unavailable")
    return ".".join(match.groups())


def deterministic_name(project_id: str, agent: str, project: dict[str, Any], generation: int) -> str:
    material = "\0".join((project_id, agent, project["repo"], project["cwd"], project["branch"], project["head"], str(generation)))
    suffix = hashlib.sha256(material.encode()).hexdigest()[:12]
    return f"acpc-{project_id}-{agent}-g{generation}-{suffix}"[:128]


def parse_ensure(raw: str, expected_name: str) -> dict[str, str | None]:
    docs = json_documents(raw)
    record_id = find_string(docs, ("acpxRecordId", "recordId"))
    acpx_session_id = find_string(docs, ("acpxSessionId", "sessionId"))
    agent_session_id = find_string(docs, ("agentSessionId",))
    observed_name = find_string(docs, ("name", "sessionName"))
    if not record_id or not acpx_session_id or (observed_name and observed_name != expected_name):
        fail("acpx_malformed_output", "ACPX ensure output lacks matching session identifiers")
    return {"acpxRecordId": record_id, "acpxSessionId": acpx_session_id, "agentSessionId": agent_session_id}


def parse_prompt(raw: str) -> tuple[dict[str, Any], str]:
    docs = json_documents(raw)
    stop_reason = find_string(docs, ("stopReason",))
    if not stop_reason:
        fail("acpx_malformed_output", "ACPX prompt did not report completion")
    chunks: list[str] = []
    for document in docs:
        if not isinstance(document, dict) or document.get("method") != "session/update":
            continue
        update = document.get("params", {}).get("update", {})
        if update.get("sessionUpdate") != "agent_message_chunk":
            continue
        content = update.get("content", {})
        if isinstance(content, dict) and isinstance(content.get("text"), str):
            chunks.append(content["text"])
    response = "".join(chunks)
    if not response:
        fail("acpx_malformed_output", "ACPX prompt completed without an agent response")
    return {"stopReason": stop_reason, "completed": True}, response


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "status":
        return {"name": "acp-project-continuity", "version": VERSION, "backend": "bundled-acpx-named-sessions", "gatewayCalls": False, "storesSecrets": False, "storesPrompts": False, "storesProtocolOutput": False, "agents": list(AGENTS), "minimumAcpxVersion": ".".join(map(str, MIN_ACPX_VERSION)), "requiredAdapterCapabilities": list(REQUIRED_SESSION_CAPABILITIES)}
    store = Store(args)
    if args.command == "onboard":
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            compare_revision(state, args)
            selected = list(AGENTS) if args.agent == "both" else [args.agent]
            existing = state["onboarding"]
            combined = sorted(set(selected) | set(existing["agents"] if existing else []))
            state["onboarding"] = {"agents": combined, "version": VERSION}
            return {"agents": combined, "revision": state["revision"] + 1, "runtimeInjection": "process environment or protected runtime only", "sharedStorage": "optional; non-sensitive handoff artifacts only"}
        return store.transact(True, operation)
    if args.command == "project-list":
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            onboarded(state)
            return {"revision": state["revision"], "projects": [{"projectId": key, **{field: value[field] for field in ("repo", "cwd", "branch", "head")}} for key, value in sorted(state["projects"].items())]}
        return store.transact(False, operation)
    if args.command == "project-register":
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            compare_revision(state, args)
            onboarded(state)
            project_id, _, repo, cwd, branch, head = project_context(args, with_agent=False)
            old = state["projects"].get(project_id)
            if old and (old["repo"], old["cwd"], old["branch"], old["head"]) != (repo, cwd, branch, head):
                fail("context_mismatch", "project id is bound to another context")
            if old is None:
                state["projects"][project_id] = {"repo": repo, "cwd": cwd, "branch": branch, "head": head, "sessions": {}, "leases": {}}
            return {"projectId": project_id, "created": old is None, "revision": state["revision"] + 1}
        return store.transact(True, operation)
    if args.command == "project-inspect":
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            project_id, agent, project = checked_project(state, args)
            return {"projectId": project_id, "agent": agent, "repo": project["repo"], "cwd": project["cwd"], "branch": project["branch"], "head": project["head"], "session": project["sessions"].get(agent), "lease": project["leases"].get(agent), "revision": state["revision"]}
        return store.transact(False, operation)
    if args.command == "acpx-preflight":
        def operation(state: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
            return checked_project(state, args)
        project_id, agent, project = store.transact(False, operation)
        version = preflight_acpx(args.acpx_binary, agent, project["cwd"], args.timeout_seconds)
        return {"projectId": project_id, "agent": agent, "backend": "acpx", "acpxVersion": version, "capabilities": list(REQUIRED_SESSION_CAPABILITIES)}
    if args.command == "session-run":
        if args.prompt_file != "-":
            fail("invalid_input", "prompt must be supplied on standard input")
        prompt = sys.stdin.read(MAX_PROMPT_BYTES + 1)
        if not isinstance(prompt, str) or not prompt.strip() or "\x00" in prompt or len(prompt.encode()) > MAX_PROMPT_BYTES:
            fail("invalid_prompt", "prompt must be non-empty and within the byte bound")
        def acquire(state: dict[str, Any]) -> dict[str, Any]:
            compare_revision(state, args)
            project_id, agent, project = checked_project(state, args)
            lease = project["leases"].get(agent)
            if args.expires_at <= args.now:
                fail("invalid_input", "lease expiry must be after now")
            if lease and lease["expiresAt"] > args.now and lease["token"] != args.lease_token:
                fail("lease_conflict", "another active lease exists")
            generation = (project["sessions"].get(agent) or {}).get("generation", 1)
            if args.rotate:
                generation += 1
            name = deterministic_name(project_id, agent, project, generation)
            project["leases"][agent] = {"token": text(args.lease_token, "lease token", identifier=True), "expiresAt": args.expires_at}
            return {"projectId": project_id, "agent": agent, "project": dict(project), "generation": generation, "sessionName": name, "revision": state["revision"] + 1}
        acquired = store.transact(True, acquire)
        try:
            version = preflight_acpx(args.acpx_binary, acquired["agent"], acquired["project"]["cwd"], args.timeout_seconds)
            base = ["--format", "json", "--json-strict", "--cwd", acquired["project"]["cwd"], acquired["agent"]]
            ensured = acpx_call(args.acpx_binary, [*base, "sessions", "ensure", "--name", acquired["sessionName"]], cwd=acquired["project"]["cwd"], timeout=args.timeout_seconds)
            ids = parse_ensure(ensured.stdout, acquired["sessionName"])
            prompted = acpx_call(args.acpx_binary, [*base, "prompt", "--session", acquired["sessionName"], "--file", "-"], cwd=acquired["project"]["cwd"], timeout=args.timeout_seconds, stdin=prompt)
            result, response = parse_prompt(prompted.stdout)
            previous = acquired["project"]["sessions"].get(acquired["agent"])
            if args.rotate and previous and not previous["closed"] and previous["sessionName"] != acquired["sessionName"]:
                acpx_call(args.acpx_binary, [*base, "sessions", "close", previous["sessionName"]], cwd=acquired["project"]["cwd"], timeout=args.timeout_seconds)
            def record(state: dict[str, Any]) -> dict[str, Any]:
                project_id, agent, project = checked_project(state, args)
                lease = project["leases"].get(agent)
                if not lease or lease["token"] != args.lease_token:
                    fail("lease_conflict", "lease ownership changed before result recording")
                project["sessions"][agent] = {"sessionName": acquired["sessionName"], **ids, "generation": acquired["generation"], "closed": False, "lastResult": result}
                del project["leases"][agent]
                return {"projectId": project_id, "agent": agent, "sessionName": acquired["sessionName"], **ids, "generation": acquired["generation"], "result": result, "response": response, "acpxVersion": version, "revision": state["revision"] + 1}
            return store.transact(True, record)
        except Exception:
            def release_failed(state: dict[str, Any]) -> dict[str, Any]:
                project = state["projects"].get(acquired["projectId"])
                lease = project and project["leases"].get(acquired["agent"])
                if lease and lease["token"] == args.lease_token:
                    del project["leases"][acquired["agent"]]
                return {}
            store.transact(True, release_failed)
            raise
    if args.command in {"session-resolve", "session-validate"}:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            project_id, agent, project = checked_project(state, args)
            session = project["sessions"].get(agent)
            if not session or session["closed"]:
                fail("session_missing", "no active session is attached; no fallback is permitted")
            if args.command == "session-validate" and text(args.session_id, "session id", identifier=True) not in {session["acpxRecordId"], session["acpxSessionId"], session.get("agentSessionId")}:
                fail("session_mismatch", "session id does not match")
            return {"projectId": project_id, "agent": agent, "sessionName": session["sessionName"], "acpxRecordId": session["acpxRecordId"], "acpxSessionId": session["acpxSessionId"], "agentSessionId": session.get("agentSessionId"), "generation": session["generation"], "revision": state["revision"]}
        return store.transact(False, operation)
    if args.command == "session-close":
        def resolve_close(state: dict[str, Any]) -> tuple[str, str, str]:
            compare_revision(state, args)
            project_id, agent, project = checked_project(state, args)
            current = project["sessions"].get(agent)
            if not current or current["closed"]:
                fail("session_missing", "no active session to close")
            return project_id, agent, current["sessionName"]
        project_id, agent, name = store.transact(False, resolve_close)
        preflight_acpx(args.acpx_binary, agent, args.cwd, args.timeout_seconds)
        acpx_call(args.acpx_binary, ["--format", "json", "--json-strict", "--cwd", args.cwd, agent, "sessions", "close", name], cwd=args.cwd, timeout=args.timeout_seconds)
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            compare_revision(state, args)
            project_id, agent, project = checked_project(state, args)
            current = project["sessions"].get(agent)
            if not current or current["closed"] or current["sessionName"] != name:
                fail("session_conflict", "lineage changed while ACPX close was running")
            current["closed"] = True
            project["leases"].pop(agent, None)
            result = project["sessions"][agent]
            return {"projectId": project_id, "agent": agent, **result, "revision": state["revision"] + 1}
        return store.transact(True, operation)
    if args.command.startswith("lease-"):
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            compare_revision(state, args)
            project_id, agent, project = checked_project(state, args)
            token = text(args.lease_token, "lease token", identifier=True)
            lease = project["leases"].get(agent)
            if args.command == "lease-acquire":
                if args.expires_at <= args.now:
                    fail("invalid_input", "lease expiry must be after now")
                if lease and lease["expiresAt"] > args.now and lease["token"] != token:
                    fail("lease_conflict", "another active lease exists")
                project["leases"][agent] = {"token": token, "expiresAt": args.expires_at}
            else:
                if not lease or lease["expiresAt"] <= args.now:
                    fail("lease_missing", "no active lease exists")
                if lease["token"] != token:
                    fail("lease_conflict", "lease token does not match")
                del project["leases"][agent]
            return {"projectId": project_id, "agent": agent, "leased": args.command == "lease-acquire", "revision": state["revision"] + 1}
        return store.transact(True, operation)
    fail("invalid_command", "unknown command")


def add_store(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--state-root", required=True)


def add_context(parser: argparse.ArgumentParser, *, agent: bool = True) -> None:
    add_store(parser)
    for flag in ("project-id", "workspace-root", "repo", "cwd", "branch", "head"):
        parser.add_argument("--" + flag, required=True)
    if agent:
        parser.add_argument("--agent", required=True, choices=AGENTS)


def build_parser() -> argparse.ArgumentParser:
    root = SafeArgumentParser(prog="acp-project-continuity")
    sub = root.add_subparsers(dest="command", required=True, parser_class=SafeArgumentParser)
    sub.add_parser("status")
    command = sub.add_parser("onboard")
    add_store(command)
    command.add_argument("--agent", required=True, choices=(*AGENTS, "both"))
    command.add_argument("--expected-revision", required=True, type=int)
    command = sub.add_parser("project-list")
    add_store(command)
    command = sub.add_parser("project-register")
    add_context(command, agent=False)
    command.add_argument("--expected-revision", required=True, type=int)
    for name in ("project-inspect", "session-resolve"):
        add_context(sub.add_parser(name))
    command = sub.add_parser("session-validate")
    add_context(command)
    command.add_argument("--session-id", required=True)
    for name in ("acpx-preflight",):
        command = sub.add_parser(name)
        add_context(command)
        command.add_argument("--acpx-binary", required=True)
        command.add_argument("--timeout-seconds", type=int, default=30)
    command = sub.add_parser("session-run")
    add_context(command)
    command.add_argument("--acpx-binary", required=True)
    command.add_argument("--prompt-file", required=True, choices=("-",))
    command.add_argument("--lease-token", required=True)
    command.add_argument("--now", required=True, type=int)
    command.add_argument("--expires-at", required=True, type=int)
    command.add_argument("--timeout-seconds", type=int, default=120)
    command.add_argument("--rotate", action="store_true")
    command.add_argument("--expected-revision", required=True, type=int)
    command = sub.add_parser("session-close")
    add_context(command)
    command.add_argument("--acpx-binary", required=True)
    command.add_argument("--timeout-seconds", type=int, default=30)
    command.add_argument("--expected-revision", required=True, type=int)
    command = sub.add_parser("lease-acquire")
    add_context(command)
    command.add_argument("--lease-token", required=True)
    command.add_argument("--now", required=True, type=int)
    command.add_argument("--expires-at", required=True, type=int)
    command.add_argument("--expected-revision", required=True, type=int)
    command = sub.add_parser("lease-release")
    add_context(command)
    command.add_argument("--lease-token", required=True)
    command.add_argument("--now", required=True, type=int)
    command.add_argument("--expected-revision", required=True, type=int)
    return root


def main(argv: list[str] | None = None) -> int:
    command = "unknown"
    try:
        args = build_parser().parse_args(argv)
        command = args.command
        payload = {"ok": True, "schemaVersion": SCHEMA_VERSION, "version": VERSION, "command": command, "data": run(args)}
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 0
    except Failure as error:
        print(json.dumps({"ok": False, "schemaVersion": SCHEMA_VERSION, "version": VERSION, "command": command, "error": {"code": error.code, "message": error.message}}, sort_keys=True, separators=(",", ":")))
        return 2
    except Exception:
        print(json.dumps({"ok": False, "schemaVersion": SCHEMA_VERSION, "version": VERSION, "command": command, "error": {"code": "internal_error", "message": "local continuity operation failed"}}, sort_keys=True, separators=(",", ":")))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
