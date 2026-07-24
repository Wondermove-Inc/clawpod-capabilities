#!/usr/bin/env python3
"""Manage AgentSkills and CLI Harnesses from the canonical ClawPod registry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

REPOSITORY = "Wondermove-Inc/clawpod-capabilities"
RAW_BASE = f"https://raw.githubusercontent.com/{REPOSITORY}/main"
REGISTRY_URL = f"{RAW_BASE}/registry/index.json"
PROVENANCE_FILE = ".clawpod-install.json"
BACKUP_DIR = ".clawpod-backups"
WORKFLOW_POLICY_VERSION = "1.0.0"
WORKFLOW_BEGIN = b"<!-- BEGIN CLAWPOD CAPABILITY REGISTRY POLICY -->"
WORKFLOW_END = b"<!-- END CLAWPOD CAPABILITY REGISTRY POLICY -->"
WORKFLOW_POLICY = f"""<!-- BEGIN CLAWPOD CAPABILITY REGISTRY POLICY -->
## Registry-first capability creation (managed, version {WORKFLOW_POLICY_VERSION})

Before creating or updating an AgentSkill or CLI Harness:

1. Inspect capabilities already installed in the agent environment.
2. Search only the canonical registry at `https://github.com/Wondermove-Inc/clawpod-capabilities`.
3. Assess same or similar candidates for scope, compatibility, safety, and limitations.
4. Record an evidence-backed classification: `reuse`, `refine`, `compose`, or `create`.
5. Choose `create` only when no adequate installed or canonical-registry capability exists.

Installation does not authorize risky invocation. Preserve approval boundaries for credentials,
external side effects, destructive actions, privilege expansion, publication, deployment, and
production changes.
<!-- END CLAWPOD CAPABILITY REGISTRY POLICY -->""".encode("utf-8")


class CapabilityError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def emit(command: str, data: Any, *, ok: bool = True) -> None:
    print(json.dumps({"ok": ok, "command": command, "data": data}, ensure_ascii=False, sort_keys=True))


def emit_error(command: str, error: CapabilityError) -> None:
    print(
        json.dumps(
            {"ok": False, "command": command, "error": {"code": error.code, "message": error.message}},
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def fetch_bytes(url: str, *, timeout: int = 20) -> bytes:
    if not url.startswith(RAW_BASE + "/"):
        raise CapabilityError("untrusted_source", "refusing to access a non-canonical registry URL")
    request = urllib.request.Request(url, headers={"User-Agent": "clawpod-capability-registry/0.1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise CapabilityError("registry_http_error", f"registry request failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise CapabilityError("registry_unavailable", f"registry request failed: {exc.reason}") from exc


def load_registry() -> dict[str, Any]:
    try:
        registry = json.loads(fetch_bytes(REGISTRY_URL).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CapabilityError("invalid_registry", "registry/index.json is not valid UTF-8 JSON") from exc
    if not isinstance(registry, dict) or registry.get("schemaVersion") != 1:
        raise CapabilityError("invalid_registry", "unsupported or malformed registry schema")
    capabilities = registry.get("capabilities")
    if not isinstance(capabilities, list):
        raise CapabilityError("invalid_registry", "registry capabilities must be an array")
    return registry


def entries() -> list[dict[str, Any]]:
    return list(load_registry()["capabilities"])


def choose(capability_id: str, version: str | None = None, capability_type: str | None = None) -> dict[str, Any]:
    matches = [entry for entry in entries() if entry.get("id") == capability_id]
    if version is not None:
        matches = [entry for entry in matches if entry.get("version") == version]
    if capability_type is not None:
        if capability_type not in {"skill", "harness"}:
            raise CapabilityError("invalid_input", "type must be skill or harness")
        matches = [entry for entry in matches if entry.get("type") == capability_type]
    if not matches:
        suffix = f"@{version}" if version else ""
        raise CapabilityError("not_found", f"capability not found: {capability_id}{suffix}")
    types = {entry.get("type") for entry in matches}
    if capability_type is None and len(types) > 1:
        raise CapabilityError("ambiguous_type", "capability id exists as both skill and harness; pass --type")
    return sorted(matches, key=lambda entry: tuple(int(part) for part in entry["version"].split("-")[0].split(".")), reverse=True)[0]


def public_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if key != "files"} | {"fileCount": len(entry.get("files", []))}


def validate_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise CapabilityError("invalid_registry", f"unsafe package file path: {value}")
    return path


def package_files(entry: dict[str, Any]) -> list[dict[str, str]]:
    files = entry.get("files")
    if not isinstance(files, list) or not files:
        raise CapabilityError("invalid_registry", f"{entry['id']} has no installable file manifest")
    result: list[dict[str, str]] = []
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise CapabilityError("invalid_registry", f"{entry['id']} contains malformed file metadata")
        validate_relative_path(item["path"])
        digest = item["sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise CapabilityError("invalid_registry", f"{entry['id']} contains an invalid SHA-256 digest")
        result.append({"path": item["path"], "sha256": digest})
    return result


def package_destination(target_root: str, capability_id: str) -> tuple[Path, Path]:
    root = Path(target_root).expanduser().resolve()
    destination = (root / capability_id).resolve()
    if destination.parent != root:
        raise CapabilityError("invalid_target", "capability destination escapes target root")
    return root, destination


def workflow_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if path.name != "WORKFLOW.md":
        raise CapabilityError("invalid_workflow_path", "--workflow-path must identify an existing WORKFLOW.md")
    return path


def workflow_path_hash(path: Path) -> str:
    return hashlib.sha256(os.fsencode(str(path))).hexdigest()


def inspect_workflow_policy(value: str) -> dict[str, Any]:
    path = workflow_path(value)
    evidence = {
        "policyStatus": "absent",
        "policyVersion": None,
        "managedPolicyVersion": WORKFLOW_POLICY_VERSION,
        "workflowPathHash": workflow_path_hash(path),
        "changed": False,
        "recovery": "Run workflow-activate with this explicit path after correcting any marker error.",
    }
    if not path.is_file():
        return evidence | {
            "policyStatus": "workflow_missing",
            "recovery": "Create and approve the agent-owned WORKFLOW.md, then run workflow-activate explicitly.",
        }
    content = path.read_bytes()
    begins, ends = content.count(WORKFLOW_BEGIN), content.count(WORKFLOW_END)
    if begins == 0 and ends == 0:
        return evidence
    if begins != 1 or ends != 1:
        return evidence | {
            "policyStatus": "malformed",
            "recovery": "Repair duplicate, missing, or unbalanced exact managed markers; no write was made.",
        }
    start, finish = content.index(WORKFLOW_BEGIN), content.index(WORKFLOW_END)
    if finish < start or WORKFLOW_BEGIN in content[start + len(WORKFLOW_BEGIN):finish]:
        return evidence | {
            "policyStatus": "malformed",
            "recovery": "Repair nested or reversed exact managed markers; no write was made.",
        }
    finish += len(WORKFLOW_END)
    block = content[start:finish]
    if block == WORKFLOW_POLICY:
        return evidence | {
            "policyStatus": "active",
            "policyVersion": WORKFLOW_POLICY_VERSION,
            "recovery": "No recovery required; rerunning workflow-activate is idempotent.",
        }
    version_match = re.search(rb"managed, version ([0-9]+\.[0-9]+\.[0-9]+)", block)
    return evidence | {
        "policyStatus": "outdated",
        "policyVersion": version_match.group(1).decode("ascii") if version_match else "unknown",
        "recovery": "Run workflow-activate to replace only the exact managed block atomically.",
    }


def atomic_write(path: Path, payload: bytes) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, path.stat().st_mode)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def activate_workflow_policy(value: str) -> dict[str, Any]:
    path = workflow_path(value)
    status = inspect_workflow_policy(value)
    if status["policyStatus"] == "workflow_missing":
        raise CapabilityError("workflow_missing", status["recovery"])
    if status["policyStatus"] == "malformed":
        raise CapabilityError("malformed_workflow_markers", status["recovery"])
    if status["policyStatus"] == "active":
        return status
    original = path.read_bytes()
    if status["policyStatus"] == "absent":
        separator = b"" if not original or original.endswith(b"\n") else b"\n"
        updated = original + separator + WORKFLOW_POLICY + b"\n"
    else:
        start = original.index(WORKFLOW_BEGIN)
        finish = original.index(WORKFLOW_END, start) + len(WORKFLOW_END)
        updated = original[:start] + WORKFLOW_POLICY + original[finish:]
    atomic_write(path, updated)
    return inspect_workflow_policy(value) | {"changed": True, "previousPolicyStatus": status["policyStatus"]}


def download_package(entry: dict[str, Any], staging: Path) -> list[dict[str, str]]:
    verified: list[dict[str, str]] = []
    base_path = entry["path"].rstrip("/")
    for item in package_files(entry):
        relative = validate_relative_path(item["path"])
        payload = fetch_bytes(f"{RAW_BASE}/{base_path}/{relative.as_posix()}")
        actual = hashlib.sha256(payload).hexdigest()
        if actual != item["sha256"]:
            raise CapabilityError("digest_mismatch", f"digest mismatch for {relative.as_posix()}")
        output = staging.joinpath(*relative.parts)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
        verified.append({"path": relative.as_posix(), "sha256": actual})
    return verified


def provenance(entry: dict[str, Any], verified: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "repository": f"https://github.com/{REPOSITORY}",
        "id": entry["id"],
        "type": entry["type"],
        "version": entry["version"],
        "sourcePath": entry["path"],
        "installedAt": datetime.now(timezone.utc).isoformat(),
        "files": verified,
    }


def ensure_harness_entrypoint_executable(entry: dict[str, Any], staging: Path) -> None:
    if entry.get("type") != "harness":
        return
    manifest_path = staging / "harness.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entrypoint = validate_relative_path(manifest["entrypoint"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise CapabilityError("invalid_package", "harness entrypoint metadata is invalid") from exc
    entrypoint_path = staging.joinpath(*entrypoint.parts)
    if not entrypoint_path.is_file():
        raise CapabilityError("invalid_package", "harness entrypoint file is missing")
    entrypoint_path.chmod(entrypoint_path.stat().st_mode | 0o111)


def install_entry(entry: dict[str, Any], target_root: str, *, replace: bool, backup: bool) -> dict[str, Any]:
    root, destination = package_destination(target_root, entry["id"])
    root.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not replace:
        raise CapabilityError("already_exists", f"destination already exists: {destination}")

    staging = Path(tempfile.mkdtemp(prefix=f".{entry['id']}-", dir=root))
    backup_path: Path | None = None
    try:
        verified = download_package(entry, staging)
        ensure_harness_entrypoint_executable(entry, staging)
        (staging / PROVENANCE_FILE).write_text(
            json.dumps(provenance(entry, verified), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if destination.exists():
            if backup:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
                backup_path = root / BACKUP_DIR / entry["id"] / stamp
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                destination.rename(backup_path)
            else:
                shutil.rmtree(destination)
        staging.rename(destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if backup_path is not None and backup_path.exists() and not destination.exists():
            backup_path.rename(destination)
        raise

    return {
        "id": entry["id"],
        "version": entry["version"],
        "destination": str(destination),
        "backup": str(backup_path) if backup_path else None,
        "verifiedFiles": len(verified),
    }


def linked_entries(entry: dict[str, Any]) -> list[dict[str, Any]]:
    linked = entry.get("linkedHarness")
    if not linked:
        return [entry]
    if entry.get("type") != "skill":
        raise CapabilityError("invalid_registry", "only skills may declare a linked harness")
    if not isinstance(linked, dict) or set(linked) != {"id", "version"}:
        raise CapabilityError("invalid_registry", "linkedHarness must contain id and version")
    return [entry, choose(linked["id"], linked["version"], "harness")]


def install_unit(entry: dict[str, Any], skills_root: str | None, harnesses_root: str | None, *, replace: bool) -> dict[str, Any]:
    unit = linked_entries(entry)
    if len(unit) == 1:
        root = skills_root if entry["type"] == "skill" else harnesses_root
        if not root:
            raise CapabilityError("invalid_target", "the matching explicit target root is required")
        return {"unit": [install_entry(entry, root, replace=replace, backup=replace)]}
    if not skills_root or not harnesses_root:
        raise CapabilityError("linked_install_blocked", "linked Skill installation requires both --skills-root and --harnesses-root")
    roots = {"skill": skills_root, "harness": harnesses_root}
    snapshots: list[tuple[Path, Path | None]] = []
    temp = Path(tempfile.mkdtemp(prefix=".clawpod-unit-"))
    try:
        for item in unit:
            _, dest = package_destination(roots[item["type"]], item["id"])
            snap = temp / item["type"]
            if dest.exists(): shutil.copytree(dest, snap)
            snapshots.append((dest, snap if snap.exists() else None))
        results=[]
        for item in unit:
            results.append(install_entry(item, roots[item["type"]], replace=replace, backup=replace))
        return {"transactional": True, "unit": results}
    except Exception:
        for dest, snap in snapshots:
            if dest.exists(): shutil.rmtree(dest)
            if snap is not None: shutil.copytree(snap, dest)
        raise
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def install_unit_with_onboarding(
    entry: dict[str, Any], skills_root: str | None, harnesses_root: str | None, *, replace: bool, workflow: str | None
) -> dict[str, Any]:
    if entry["id"] != "clawpod-capability-registry":
        return install_unit(entry, skills_root, harnesses_root, replace=replace)
    if not workflow:
        raise CapabilityError(
            "workflow_path_required",
            "installing or updating clawpod-capability-registry requires an explicit --workflow-path to an existing WORKFLOW.md",
        )
    path = workflow_path(workflow)
    if not path.is_file():
        raise CapabilityError("workflow_missing", "WORKFLOW.md does not exist; no file was created and no capability was installed")
    # Validate markers before any package mutation.
    preflight = inspect_workflow_policy(workflow)
    if preflight["policyStatus"] == "malformed":
        raise CapabilityError("malformed_workflow_markers", preflight["recovery"])
    original_workflow = path.read_bytes()
    roots = {"skill": skills_root, "harness": harnesses_root}
    temp = Path(tempfile.mkdtemp(prefix=".clawpod-onboarding-"))
    snapshots: list[tuple[Path, Path | None]] = []
    try:
        for item in linked_entries(entry):
            root = roots[item["type"]]
            if not root:
                raise CapabilityError("invalid_target", "the matching explicit target root is required")
            _, destination = package_destination(root, item["id"])
            snapshot = temp / item["type"]
            if destination.exists():
                shutil.copytree(destination, snapshot)
            snapshots.append((destination, snapshot if snapshot.exists() else None))
        installed = install_unit(entry, skills_root, harnesses_root, replace=replace)
        installed["workflowPolicy"] = activate_workflow_policy(workflow)
        installed["onboardingComplete"] = True
        return installed
    except Exception:
        for destination, snapshot in snapshots:
            if destination.exists():
                shutil.rmtree(destination)
            if snapshot is not None:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(snapshot, destination)
        if path.is_file() and path.read_bytes() != original_workflow:
            atomic_write(path, original_workflow)
        raise
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def validate_unit(entry: dict[str, Any], skills_root: str | None, harnesses_root: str | None) -> dict[str, Any]:
    unit=linked_entries(entry)
    if len(unit)>1 and (not skills_root or not harnesses_root):
        raise CapabilityError("linked_install_blocked", "linked Skill validation requires both --skills-root and --harnesses-root")
    roots={"skill":skills_root,"harness":harnesses_root}
    results=[]
    for item in unit:
        root=roots[item["type"]]
        if not root: raise CapabilityError("invalid_target", "the matching explicit target root is required")
        results.append(validate_installation(item,root))
    return {"unit":results}


def validate_installation(entry: dict[str, Any], target_root: str) -> dict[str, Any]:
    _, destination = package_destination(target_root, entry["id"])
    if not destination.is_dir():
        raise CapabilityError("not_installed", f"capability is not installed: {destination}")
    checked: list[str] = []
    mismatches: list[str] = []
    for item in package_files(entry):
        relative = validate_relative_path(item["path"])
        path = destination.joinpath(*relative.parts)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            mismatches.append(relative.as_posix())
        else:
            checked.append(relative.as_posix())
    if mismatches:
        raise CapabilityError("validation_failed", "missing or modified files: " + ", ".join(mismatches))
    return {"id": entry["id"], "version": entry["version"], "destination": str(destination), "checked": checked}


def rollback_installation(capability_id: str, target_root: str, backup_value: str | None) -> dict[str, Any]:
    root, destination = package_destination(target_root, capability_id)
    backups_root = root / BACKUP_DIR / capability_id
    if backup_value:
        candidate = Path(backup_value).expanduser().resolve()
        if candidate.parent != backups_root.resolve():
            raise CapabilityError("invalid_backup", "backup must be a direct child of the capability backup directory")
    else:
        candidates = sorted((path for path in backups_root.glob("*") if path.is_dir()), reverse=True)
        if not candidates:
            raise CapabilityError("backup_not_found", f"no backup found for {capability_id}")
        candidate = candidates[0].resolve()
    displaced: Path | None = None
    if destination.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        displaced = backups_root / f"rollback-{stamp}"
        displaced.parent.mkdir(parents=True, exist_ok=True)
        destination.rename(displaced)
    candidate.rename(destination)
    return {
        "id": capability_id,
        "destination": str(destination),
        "restoredBackup": str(candidate),
        "displacedCurrent": str(displaced) if displaced else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clawpod-capability-registry")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List registered capabilities")

    search = sub.add_parser("search", help="Search capability ids and descriptions")
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=20)

    inspect = sub.add_parser("inspect", help="Inspect one capability")
    inspect.add_argument("--id", required=True)
    inspect.add_argument("--version")
    inspect.add_argument("--type", choices=("skill", "harness"))

    workflow_status = sub.add_parser("workflow-status", help="Inspect the registry-first managed WORKFLOW policy")
    workflow_status.add_argument("--workflow-path", required=True)

    workflow_activate = sub.add_parser("workflow-activate", help="Append or update only the registry-first managed WORKFLOW block")
    workflow_activate.add_argument("--workflow-path", required=True)

    for name in ("install", "update", "validate"):
        command = sub.add_parser(name, help=f"{name.title()} a capability")
        command.add_argument("--id", required=True)
        command.add_argument("--version")
        command.add_argument("--type", choices=("skill", "harness"), required=True)
        command.add_argument("--target-root")
        command.add_argument("--skills-root")
        command.add_argument("--harnesses-root")
        if name in {"install", "update"}:
            command.add_argument("--workflow-path")

    rollback = sub.add_parser("rollback", help="Restore a previous local backup")
    rollback.add_argument("--id", required=True)
    rollback.add_argument("--target-root", required=True)
    rollback.add_argument("--backup")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "list":
        return {"repository": REPOSITORY, "capabilities": [public_entry(entry) for entry in entries()]}
    if args.command == "search":
        if args.limit < 1 or args.limit > 100:
            raise CapabilityError("invalid_input", "limit must be between 1 and 100")
        query = args.query.casefold().strip()
        if not query:
            raise CapabilityError("invalid_input", "query must not be empty")
        matches = [
            public_entry(entry)
            for entry in entries()
            if query in entry["id"].casefold() or query in entry["description"].casefold()
        ]
        return {"query": args.query, "count": min(len(matches), args.limit), "capabilities": matches[: args.limit]}
    if args.command == "inspect":
        return public_entry(choose(args.id, args.version, args.type))
    if args.command == "workflow-status":
        return inspect_workflow_policy(args.workflow_path)
    if args.command == "workflow-activate":
        return activate_workflow_policy(args.workflow_path)
    if args.command in {"install", "update", "validate"}:
        entry=choose(args.id,args.version,args.type)
        skills_root=args.skills_root or (args.target_root if args.type=="skill" else None)
        harnesses_root=args.harnesses_root or (args.target_root if args.type=="harness" else None)
        if args.command=="install":
            return install_unit_with_onboarding(entry,skills_root,harnesses_root,replace=False,workflow=args.workflow_path)
        if args.command=="update":
            roots={"skill":skills_root,"harness":harnesses_root}
            for item in linked_entries(entry):
                root=roots[item["type"]]
                if not root: raise CapabilityError("invalid_target", "the matching explicit target root is required")
                _,destination=package_destination(root,item["id"])
                if not destination.exists(): raise CapabilityError("not_installed",f"capability is not installed: {destination}")
            return install_unit_with_onboarding(entry,skills_root,harnesses_root,replace=True,workflow=args.workflow_path)
        return validate_unit(entry,skills_root,harnesses_root)
    if args.command == "rollback":
        return rollback_installation(args.id, args.target_root, args.backup)
    raise CapabilityError("invalid_command", f"unsupported command: {args.command}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        emit(args.command, run(args))
        return 0
    except CapabilityError as exc:
        emit_error(args.command, exc)
        return 1
    except Exception as exc:  # prevent non-JSON failures
        emit_error(args.command, CapabilityError("internal_error", str(exc)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
