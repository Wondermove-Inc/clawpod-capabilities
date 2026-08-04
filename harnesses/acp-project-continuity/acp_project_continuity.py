#!/usr/bin/env python3
"""Pure-local, fail-closed ACP project/session continuity registry."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

VERSION = "0.1.0"
SCHEMA_VERSION = 1
AGENTS = ("claude", "codex")
MAX_STATE_BYTES = 1_048_576
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
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
        if not isinstance(project, dict) or set(project) != {"repo", "cwd", "branch", "sessions", "leases"}:
            fail("malformed_state", "stored project is invalid")
        for key in ("repo", "cwd", "branch"):
            text(project.get(key), f"stored {key}")
        if not isinstance(project["sessions"], dict) or set(project["sessions"]) - set(AGENTS):
            fail("malformed_state", "stored sessions are invalid")
        if not isinstance(project["leases"], dict) or set(project["leases"]) - set(AGENTS):
            fail("malformed_state", "stored leases are invalid")
        for session in project["sessions"].values():
            if not isinstance(session, dict) or set(session) != {"sessionId", "generation", "closed"}:
                fail("malformed_state", "stored session is invalid")
            text(session.get("sessionId"), "stored session id", identifier=True)
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


def project_context(args: argparse.Namespace, *, with_agent: bool) -> tuple[str, str | None, str, str, str]:
    project_id = text(args.project_id, "project id", identifier=True)
    agent = text(args.agent, "agent", identifier=True).lower() if with_agent else None
    if agent is not None and agent not in AGENTS:
        fail("invalid_input", "agent must be codex or claude")
    safe_path(args.workspace_root, args.workspace_root, "workspace")
    repo = safe_path(args.repo, args.workspace_root, "repo")
    cwd = safe_path(args.cwd, args.workspace_root, "cwd")
    if repo != cwd and repo not in cwd.parents:
        fail("path_contract", "cwd must be inside repo")
    return project_id, agent, str(repo), str(cwd), text(args.branch, "branch")


def checked_project(state: dict[str, Any], args: argparse.Namespace) -> tuple[str, str, dict[str, Any]]:
    project_id, agent, repo, cwd, branch = project_context(args, with_agent=True)
    assert agent is not None
    onboarded(state, agent)
    project = state["projects"].get(project_id)
    if project is None:
        fail("project_missing", "project is not registered")
    if (project["repo"], project["cwd"], project["branch"]) != (repo, cwd, branch):
        fail("context_mismatch", "repo, cwd, or branch does not match project")
    return project_id, agent, project


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "status":
        return {"name": "acp-project-continuity", "version": VERSION, "pureLocal": True, "network": False, "gatewayCalls": False, "acpCalls": False, "vendorCalls": False, "storesSecrets": False, "agents": list(AGENTS)}
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
            return {"revision": state["revision"], "projects": [{"projectId": key, **{field: value[field] for field in ("repo", "cwd", "branch")}} for key, value in sorted(state["projects"].items())]}
        return store.transact(False, operation)
    if args.command == "project-register":
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            compare_revision(state, args)
            onboarded(state)
            project_id, _, repo, cwd, branch = project_context(args, with_agent=False)
            old = state["projects"].get(project_id)
            if old and (old["repo"], old["cwd"], old["branch"]) != (repo, cwd, branch):
                fail("context_mismatch", "project id is bound to another context")
            if old is None:
                state["projects"][project_id] = {"repo": repo, "cwd": cwd, "branch": branch, "sessions": {}, "leases": {}}
            return {"projectId": project_id, "created": old is None, "revision": state["revision"] + 1}
        return store.transact(True, operation)
    if args.command == "project-inspect":
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            project_id, agent, project = checked_project(state, args)
            return {"projectId": project_id, "agent": agent, "repo": project["repo"], "cwd": project["cwd"], "branch": project["branch"], "session": project["sessions"].get(agent), "lease": project["leases"].get(agent), "revision": state["revision"]}
        return store.transact(False, operation)
    if args.command in {"session-resolve", "session-validate"}:
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            project_id, agent, project = checked_project(state, args)
            session = project["sessions"].get(agent)
            if not session or session["closed"]:
                fail("session_missing", "no active session is attached; no fallback is permitted")
            if args.command == "session-validate" and text(args.session_id, "session id", identifier=True) != session["sessionId"]:
                fail("session_mismatch", "session id does not match")
            return {"projectId": project_id, "agent": agent, "resumeSessionId": session["sessionId"], "generation": session["generation"], "revision": state["revision"]}
        return store.transact(False, operation)
    if args.command.startswith("session-"):
        def operation(state: dict[str, Any]) -> dict[str, Any]:
            compare_revision(state, args)
            project_id, agent, project = checked_project(state, args)
            current = project["sessions"].get(agent)
            if args.command == "session-attach":
                session_id = text(args.session_id, "session id", identifier=True)
                if current and not current["closed"] and current["sessionId"] != session_id:
                    fail("session_conflict", "an active session is already attached")
                if current and current["closed"]:
                    fail("session_closed", "rotate explicitly instead of reopening")
                if current is None:
                    project["sessions"][agent] = {"sessionId": session_id, "generation": 1, "closed": False}
            elif args.command == "session-rotate":
                if not current or current["closed"]:
                    fail("session_missing", "no active session to rotate")
                session_id = text(args.session_id, "session id", identifier=True)
                if session_id == current["sessionId"]:
                    fail("invalid_input", "rotation requires a different session id")
                project["sessions"][agent] = {"sessionId": session_id, "generation": current["generation"] + 1, "closed": False}
            else:
                if not current or current["closed"]:
                    fail("session_missing", "no active session to close")
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
    for flag in ("project-id", "workspace-root", "repo", "cwd", "branch"):
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
    for name in ("session-attach", "session-rotate"):
        command = sub.add_parser(name)
        add_context(command)
        command.add_argument("--session-id", required=True)
        command.add_argument("--expected-revision", required=True, type=int)
    command = sub.add_parser("session-close")
    add_context(command)
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
