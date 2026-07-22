#!/usr/bin/env python3
"""Bootstrap the canonical capability-management Skill and CLI Harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "index.json"
BOOTSTRAP_KEYS = (("skill", "clawpod-capability-registry"), ("harness", "clawpod-capability-registry"))
BACKUP_DIR = ".clawpod-bootstrap-backups"


class BootstrapError(Exception):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_entries() -> dict[tuple[str, str], dict[str, Any]]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    entries = {(entry["type"], entry["id"]): entry for entry in data.get("capabilities", [])}
    missing = [f"{kind}:{capability_id}" for kind, capability_id in BOOTSTRAP_KEYS if (kind, capability_id) not in entries]
    if missing:
        raise BootstrapError("registry is missing bootstrap capabilities: " + ", ".join(missing))
    return entries


def root_for(entry: dict[str, Any], skills_root: Path, harnesses_root: Path) -> Path:
    return skills_root if entry["type"] == "skill" else harnesses_root


def verify_source(entry: dict[str, Any]) -> list[tuple[Path, str]]:
    package = ROOT / entry["path"]
    verified: list[tuple[Path, str]] = []
    for item in entry["files"]:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise BootstrapError(f"unsafe registry path: {item['path']}")
        source = package / relative
        if not source.is_file() or digest(source) != item["sha256"]:
            raise BootstrapError(f"source verification failed: {entry['id']}/{item['path']}")
        verified.append((relative, item["sha256"]))
    return verified


def destination_matches(destination: Path, files: list[tuple[Path, str]]) -> bool:
    return destination.is_dir() and all((destination / relative).is_file() and digest(destination / relative) == expected for relative, expected in files)


def install_one(
    entry: dict[str, Any],
    skills_root: Path,
    harnesses_root: Path,
    *,
    dry_run: bool,
    force: bool,
) -> dict[str, Any]:
    files = verify_source(entry)
    target_root = root_for(entry, skills_root, harnesses_root).expanduser().resolve()
    destination = (target_root / entry["id"]).resolve()
    if destination.parent != target_root:
        raise BootstrapError(f"destination escapes target root: {entry['id']}")

    if destination_matches(destination, files):
        return {"type": entry["type"], "id": entry["id"], "status": "already-installed", "destination": str(destination)}
    if destination.exists() and not force:
        raise BootstrapError(f"destination exists with different content: {destination}; rerun with --force to back up and replace")
    if dry_run:
        return {"type": entry["type"], "id": entry["id"], "status": "would-install", "destination": str(destination)}

    target_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{entry['id']}-", dir=target_root))
    backup: Path | None = None
    try:
        package = ROOT / entry["path"]
        for relative, _ in files:
            output = staging / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(package / relative, output)
        if destination.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            backup = target_root / BACKUP_DIR / entry["id"] / stamp
            backup.parent.mkdir(parents=True, exist_ok=True)
            destination.rename(backup)
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        if backup is not None and backup.exists() and not destination.exists():
            backup.rename(destination)
        raise

    return {
        "type": entry["type"],
        "id": entry["id"],
        "status": "installed",
        "destination": str(destination),
        "backup": str(backup) if backup else None,
        "verifiedFiles": len(files),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-root", required=True, help="AgentSkill installation root")
    parser.add_argument("--harnesses-root", required=True, help="CLI Harness installation root")
    parser.add_argument("--dry-run", action="store_true", help="Verify and print planned destinations without writing")
    parser.add_argument("--force", action="store_true", help="Back up and replace differing existing installations")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        entries = load_entries()
        results = [
            install_one(
                entries[capability_key],
                Path(args.skills_root),
                Path(args.harnesses_root),
                dry_run=args.dry_run,
                force=args.force,
            )
            for capability_key in BOOTSTRAP_KEYS
        ]
        print(json.dumps({"ok": True, "repository": "Wondermove-Inc/clawpod-capabilities", "results": results}, sort_keys=True))
        return 0
    except (BootstrapError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
