#!/usr/bin/env python3
"""Generate registry/index.json from package-local metadata and package files."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$")
RISKS = {"read-only", "write-safe", "externally-visible", "destructive", "credential-related"}
PACKAGE_METADATA_KEYS = {"$schema", "schemaVersion", "version", "description", "compatibility", "safety", "linkedHarness"}
IGNORED_PARTS = {"tests", "__pycache__", ".git"}
IGNORED_FILES = {"capability.json", ".DS_Store"}


class SyncError(ValueError):
    pass


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SyncError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SyncError(f"invalid JSON in {path}: {exc}") from exc


def parse_skill_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise SyncError(f"{path} must start with YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise SyncError(f"{path} has unclosed YAML frontmatter") from exc

    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise SyncError(f"{path} has malformed frontmatter: {line}")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"\'')
    if set(metadata) != {"name", "description"}:
        raise SyncError(f"{path} frontmatter must contain only name and description")
    return metadata


def validate_package_metadata(path: Path, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SyncError(f"{path} must contain an object")
    required = {"schemaVersion", "version", "description", "compatibility", "safety"}
    missing = required - value.keys()
    extra = value.keys() - PACKAGE_METADATA_KEYS
    if missing:
        raise SyncError(f"{path} missing fields: {', '.join(sorted(missing))}")
    if extra:
        raise SyncError(f"{path} has unknown fields: {', '.join(sorted(extra))}")
    if value["schemaVersion"] != 1:
        raise SyncError(f"{path} schemaVersion must equal 1")

    version = value["version"]
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise SyncError(f"{path} version must be semantic version text")
    description = value["description"]
    if not isinstance(description, str) or not 10 <= len(description) <= 240:
        raise SyncError(f"{path} description must contain 10-240 characters")

    compatibility = value["compatibility"]
    if not isinstance(compatibility, dict) or set(compatibility) - {"openclaw", "platforms"}:
        raise SyncError(f"{path} compatibility has invalid fields")
    if not isinstance(compatibility.get("openclaw"), str) or not compatibility["openclaw"]:
        raise SyncError(f"{path} compatibility.openclaw is required")
    platforms = compatibility.get("platforms")
    if platforms is not None and (
        not isinstance(platforms, list)
        or not all(isinstance(item, str) and item for item in platforms)
        or len(platforms) != len(set(platforms))
    ):
        raise SyncError(f"{path} compatibility.platforms must contain unique non-empty strings")

    safety = value["safety"]
    if not isinstance(safety, dict) or set(safety) != {"risk", "approvalRequired"}:
        raise SyncError(f"{path} safety requires only risk and approvalRequired")
    if safety["risk"] not in RISKS or not isinstance(safety["approvalRequired"], bool):
        raise SyncError(f"{path} safety contains invalid values")
    linked = value.get("linkedHarness")
    if linked is not None and (not isinstance(linked, str) or not NAME.fullmatch(linked)):
        raise SyncError(f"{path} linkedHarness must be a lowercase hyphenated id")
    return value


def package_files(package: Path) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for path in sorted(package.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(package)
        if path.name in IGNORED_FILES or path.suffix == ".pyc":
            continue
        if any(part in IGNORED_PARTS or part.startswith(".") for part in relative.parts):
            continue
        files.append(
            {
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    if not files:
        raise SyncError(f"{package} contains no distributable files")
    return files


def build_entry(root: Path, capability_type: str, package: Path) -> dict[str, object]:
    capability_id = package.name
    if not NAME.fullmatch(capability_id):
        raise SyncError(f"package name must be lowercase hyphenated text: {package}")

    metadata_path = package / "capability.json"
    metadata = validate_package_metadata(metadata_path, load_json(metadata_path))

    if capability_type == "skill":
        interface_path = package / "SKILL.md"
        interface = parse_skill_frontmatter(interface_path)
        if interface["name"] != capability_id:
            raise SyncError(f"{interface_path} name must match package directory")
    else:
        interface_path = package / "harness.json"
        interface = load_json(interface_path)
        if not isinstance(interface, dict) or interface.get("name") != capability_id:
            raise SyncError(f"{interface_path} name must match package directory")
        if interface.get("version") != metadata["version"]:
            raise SyncError(f"{interface_path} version must match capability.json")
        entrypoint = interface.get("entrypoint")
        if not isinstance(entrypoint, str) or not (package / entrypoint).is_file():
            raise SyncError(f"{interface_path} entrypoint is missing")

    if capability_type != "skill" and metadata.get("linkedHarness") is not None:
        raise SyncError(f"{metadata_path} linkedHarness is valid only for skills")
    entry = {
        "id": capability_id,
        "type": capability_type,
        "version": metadata["version"],
        "description": metadata["description"],
        "path": package.relative_to(root).as_posix(),
        "compatibility": metadata["compatibility"],
        "safety": metadata["safety"],
        "files": package_files(package),
    }
    if metadata.get("linkedHarness") is not None:
        entry["linkedHarness"] = metadata["linkedHarness"]
    return entry


def package_directories(root: Path, collection: str) -> list[Path]:
    base = root / collection
    if not base.is_dir():
        raise SyncError(f"missing package directory: {base}")
    return sorted(path for path in base.iterdir() if path.is_dir() and not path.name.startswith("."))


def generate_registry(root: Path) -> dict[str, object]:
    capabilities: list[dict[str, object]] = []
    for capability_type, collection in (("skill", "skills"), ("harness", "harnesses")):
        for package in package_directories(root, collection):
            capabilities.append(build_entry(root, capability_type, package))
    capabilities.sort(key=lambda item: (0 if item["type"] == "skill" else 1, item["id"], item["version"]))
    available = {(item["type"], item["id"], item["version"]) for item in capabilities}
    for item in capabilities:
        linked = item.get("linkedHarness")
        if linked and ("harness", linked, item["version"]) not in available:
            raise SyncError(f"linked harness {linked}@{item['version']} is missing for skill {item['id']}")
    return {
        "$schema": "../schemas/registry.schema.json",
        "schemaVersion": 1,
        "capabilities": capabilities,
    }


def render_registry(registry: dict[str, object]) -> str:
    return json.dumps(registry, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="fail when registry/index.json is stale")
    parser.add_argument("--stdout", action="store_true", help="print generated registry without writing")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    index = root / "registry" / "index.json"
    try:
        rendered = render_registry(generate_registry(root))
    except (OSError, SyncError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.stdout:
        print(rendered, end="")
        return 0

    current = index.read_text(encoding="utf-8") if index.exists() else ""
    if args.check:
        if current == rendered:
            print("OK: registry/index.json is synchronized")
            return 0
        print("ERROR: registry/index.json is stale; run python3 scripts/sync_registry.py", file=sys.stderr)
        diff = difflib.unified_diff(
            current.splitlines(), rendered.splitlines(), fromfile="registry/index.json", tofile="generated"
        )
        print("\n".join(diff), file=sys.stderr)
        return 1

    index.parent.mkdir(parents=True, exist_ok=True)
    if current == rendered:
        print("OK: registry/index.json already synchronized")
    else:
        index.write_text(rendered, encoding="utf-8")
        print(f"UPDATED: {index.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
