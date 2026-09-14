#!/usr/bin/env python3
"""Verify and stage Node installers; never build, install, or publish them."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "node/release.json"
BUNDLED = ROOT / "harnesses/clawpod-node-host/installer-manifest.json"
RELEASES = "https://github.com/Wondermove-Inc/clawpod-capabilities/releases"
TARGETS = {
    ("linux", "x64"): ("linux-x64", "deb"),
    ("macos", "arm64"): ("darwin-arm64", "pkg"),
    ("macos", "x64"): ("darwin-x64", "pkg"),
    ("windows", "x64"): ("win32-x64", "exe"),
}


def load_manifest(path: Path = MANIFEST) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise ValueError("Expected release manifest schemaVersion 1")
    version = data.get("version", "")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Expected an exact installer version")
    tag = "node-v" + version
    if data.get("releaseTag") != tag or data.get("releaseUrl") != f"{RELEASES}/tag/{tag}":
        raise ValueError("Release tag/URL differs from installer version")
    if data.get("channel") != "preview" or data.get("signed") is not False:
        raise ValueError("This staging flow is for unsigned preview installers")
    if not re.fullmatch(r"[a-f0-9]{40}", data.get("sourceCommit", "")):
        raise ValueError("Missing bundled Agent source commit")
    for key in ("runtimeVersion", "nodeVersion"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise ValueError(f"Missing {key}")
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != len(TARGETS):
        raise ValueError("Expected four installer artifacts")
    found = set()
    for item in artifacts:
        if not isinstance(item, dict):
            raise ValueError("Invalid artifact")
        target = (item.get("platform"), item.get("arch"))
        if target not in TARGETS or target in found:
            raise ValueError("Unsupported or duplicate installer target")
        found.add(target)
        suffix, extension = TARGETS[target]
        filename = f"ClawPod-Node-{version}-{suffix}.{extension}"
        if item.get("filename") != filename or item.get("url") != f"{RELEASES}/download/{tag}/{filename}":
            raise ValueError("Artifact filename/URL differs from its target")
        if not re.fullmatch(r"[a-f0-9]{64}", item.get("sha256", "")):
            raise ValueError("Missing artifact SHA-256")
        if type(item.get("bytes")) is not int or item["bytes"] <= 0:
            raise ValueError("Invalid artifact size")
    return data


def verify_artifacts(source: Path, manifest: dict) -> None:
    # Validate the complete set before copying any installer to the staging area.
    for item in manifest["artifacts"]:
        file = source / item["filename"]
        if not file.is_file() or file.is_symlink():
            raise ValueError(f"Missing regular installer: {file.name}")
        if file.stat().st_size != item["bytes"]:
            raise ValueError(f"Size mismatch: {file.name}")
        with file.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {file.name}")


def metadata_files(manifest: dict) -> dict[str, bytes]:
    # Do not distribute raw build reports: those include private staging paths.
    files = {"release.json": (json.dumps(manifest, indent=2) + "\n").encode()}
    for item in manifest["artifacts"]:
        files[item["filename"] + ".sha256"] = f'{item["sha256"]}  {item["filename"]}\n'.encode()
    return files


def verify_stage(destination: Path, manifest: dict) -> None:
    verify_artifacts(destination, manifest)
    metadata = metadata_files(manifest)
    expected = set(metadata) | {item["filename"] for item in manifest["artifacts"]}
    if {file.name for file in destination.iterdir()} != expected:
        raise ValueError("Staging contains missing or extra release files")
    for name, value in metadata.items():
        file = destination / name
        if file.is_symlink() or file.read_bytes() != value:
            raise ValueError(f"Staged metadata mismatch: {name}")


def stage(source: Path, destination: Path, manifest: dict) -> None:
    verify_artifacts(source, manifest)
    if destination.exists():
        verify_stage(destination, manifest)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A failed copy must not leave a directory that looks ready for publication.
    with tempfile.TemporaryDirectory(prefix=".node-stage-", dir=destination.parent) as temporary:
        candidate = Path(temporary) / "ready"
        candidate.mkdir()
        for item in manifest["artifacts"]:
            shutil.copyfile(source / item["filename"], candidate / item["filename"])
        for name, value in metadata_files(manifest).items():
            (candidate / name).write_bytes(value)
        verify_stage(candidate, manifest)
        candidate.rename(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "sync", "stage"))
    parser.add_argument("--source", type=Path, help="Existing installer directory; source is read-only")
    args = parser.parse_args()
    manifest = load_manifest()
    canonical = MANIFEST.read_bytes()
    if args.action == "sync":
        BUNDLED.write_bytes(canonical)
    elif not BUNDLED.is_file() or BUNDLED.read_bytes() != canonical:
        raise ValueError("Packaged manifest drift: run python3 node/prepare_release.py sync")
    if args.action == "stage":
        if args.source is None:
            parser.error("stage requires --source")
        destination = ROOT / "node/releases" / manifest["version"]
        stage(args.source, destination, manifest)
        print(f"Verified release files: {destination.relative_to(ROOT)}")
    else:
        if args.source is not None:
            verify_artifacts(args.source, manifest)
        print("OK: Node release metadata" + (" and installer bytes" if args.source else ""))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError) as exc:
        raise SystemExit(f"Node release preparation failed: {exc}") from exc
