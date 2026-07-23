#!/usr/bin/env python3
"""Validate the ClawPod capability registry with no external dependencies."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "registry" / "index.json"
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
RISKS = {"read-only", "write-safe", "externally-visible", "destructive", "credential-related"}
ALLOWED_KEYS = {"id", "type", "version", "description", "path", "sha256", "compatibility", "safety", "files"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing file: {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")


def parse_skill_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        fail(f"{path.relative_to(ROOT)} must start with YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        fail(f"{path.relative_to(ROOT)} has unclosed YAML frontmatter")

    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            fail(f"{path.relative_to(ROOT)} has malformed frontmatter: {line}")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"\'')
    if set(metadata) != {"name", "description"}:
        fail(f"{path.relative_to(ROOT)} frontmatter must contain only name and description")
    if "TODO" in path.read_text(encoding="utf-8"):
        fail(f"{path.relative_to(ROOT)} contains an unresolved TODO")
    return metadata


def validate_entry(entry: object, position: int, seen: set[tuple[str, str, str]]) -> None:
    label = f"capabilities[{position}]"
    if not isinstance(entry, dict):
        fail(f"{label} must be an object")

    required = {"id", "type", "version", "description", "path", "compatibility", "safety", "files"}
    missing = required - entry.keys()
    extra = entry.keys() - ALLOWED_KEYS
    if missing:
        fail(f"{label} missing fields: {', '.join(sorted(missing))}")
    if extra:
        fail(f"{label} has unknown fields: {', '.join(sorted(extra))}")

    capability_id = entry["id"]
    capability_type = entry["type"]
    version = entry["version"]
    description = entry["description"]
    package_path = entry["path"]

    if not isinstance(capability_id, str) or not NAME.fullmatch(capability_id):
        fail(f"{label}.id must be lowercase hyphenated text")
    if capability_type not in {"skill", "harness"}:
        fail(f"{label}.type must be skill or harness")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        fail(f"{label}.version must be semantic version text")
    if not isinstance(description, str) or not 10 <= len(description) <= 240:
        fail(f"{label}.description must contain 10-240 characters")

    expected_path = f"{'skills' if capability_type == 'skill' else 'harnesses'}/{capability_id}"
    if package_path != expected_path:
        fail(f"{label}.path must be {expected_path}")
    path = ROOT / package_path
    if not path.is_dir():
        fail(f"{label}.path does not exist: {package_path}")
    required_file = path / ("SKILL.md" if capability_type == "skill" else "harness.json")
    if not required_file.is_file():
        fail(f"{label} missing {required_file.name}")
    if capability_type == "skill":
        metadata = parse_skill_frontmatter(required_file)
        if metadata["name"] != capability_id:
            fail(f"{label} id does not match SKILL.md name")
        if not 20 <= len(metadata["description"]) <= 500:
            fail(f"{label} SKILL.md description must contain 20-500 characters")
    else:
        manifest = load_json(required_file)
        if not isinstance(manifest, dict) or manifest.get("name") != capability_id:
            fail(f"{label} id does not match harness.json name")
        entrypoint = manifest.get("entrypoint")
        if not isinstance(entrypoint, str) or not (path / entrypoint).is_file():
            fail(f"{label} harness entrypoint is missing")
        execution = manifest.get("execution")
        if not isinstance(execution, dict):
            fail(f"{label} harness execution must be an object")
        if not isinstance(execution.get("cwd"), str) or not execution["cwd"]:
            fail(f"{label} harness execution.cwd must be non-empty text")
        timeout_ms = execution.get("timeoutMs")
        if not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool) or timeout_ms <= 0:
            fail(f"{label} harness execution.timeoutMs must be a positive integer")
        if execution.get("requiresJson") is not True:
            fail(f"{label} harness execution.requiresJson must be true")

    files = entry["files"]
    if not isinstance(files, list) or not files:
        fail(f"{label}.files must be a non-empty array")
    listed_paths: set[str] = set()
    for file_position, item in enumerate(files):
        file_label = f"{label}.files[{file_position}]"
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            fail(f"{file_label} requires only path and sha256")
        relative = item["path"]
        if not isinstance(relative, str) or relative.startswith("/") or ".." in relative.split("/"):
            fail(f"{file_label}.path is unsafe")
        digest = item["sha256"]
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            fail(f"{file_label}.sha256 is invalid")
        file_path = path / relative
        if not file_path.is_file():
            fail(f"{file_label}.path does not exist")
        actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual != digest:
            fail(f"{file_label}.sha256 does not match file content")
        if relative in listed_paths:
            fail(f"{file_label}.path is duplicated")
        listed_paths.add(relative)
    if required_file.name not in listed_paths:
        fail(f"{label}.files must include {required_file.name}")

    key = (capability_type, capability_id, version)
    if key in seen:
        fail(f"duplicate capability version: {capability_type}:{capability_id}@{version}")
    seen.add(key)

    digest = entry.get("sha256")
    if digest is not None and (not isinstance(digest, str) or not SHA256.fullmatch(digest)):
        fail(f"{label}.sha256 must be a lowercase SHA-256 digest")

    compatibility = entry["compatibility"]
    if not isinstance(compatibility, dict) or not isinstance(compatibility.get("openclaw"), str):
        fail(f"{label}.compatibility.openclaw is required")
    if set(compatibility) - {"openclaw", "platforms"}:
        fail(f"{label}.compatibility has unknown fields")
    platforms = compatibility.get("platforms")
    if platforms is not None and (
        not isinstance(platforms, list)
        or not all(isinstance(item, str) and item for item in platforms)
        or len(platforms) != len(set(platforms))
    ):
        fail(f"{label}.compatibility.platforms must contain unique non-empty strings")

    safety = entry["safety"]
    if not isinstance(safety, dict) or set(safety) != {"risk", "approvalRequired"}:
        fail(f"{label}.safety requires only risk and approvalRequired")
    if safety["risk"] not in RISKS or not isinstance(safety["approvalRequired"], bool):
        fail(f"{label}.safety contains invalid values")


def main() -> None:
    for schema in ("registry.schema.json", "capability.schema.json", "package-metadata.schema.json"):
        load_json(ROOT / "schemas" / schema)

    registry = load_json(INDEX)
    if not isinstance(registry, dict):
        fail("registry/index.json must contain an object")
    if set(registry) - {"$schema", "schemaVersion", "capabilities"}:
        fail("registry/index.json contains unknown fields")
    if registry.get("schemaVersion") != 1:
        fail("registry schemaVersion must equal 1")
    capabilities = registry.get("capabilities")
    if not isinstance(capabilities, list):
        fail("registry capabilities must be an array")

    seen: set[tuple[str, str, str]] = set()
    for position, entry in enumerate(capabilities):
        validate_entry(entry, position, seen)

    print(f"OK: validated {len(capabilities)} capability entries")


if __name__ == "__main__":
    main()
