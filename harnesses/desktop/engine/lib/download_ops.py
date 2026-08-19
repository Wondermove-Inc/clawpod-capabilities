"""Download handling: download-wait / download-move / download-quarantine.

Operates on the desktop session's download directory (DESKTOP_DOWNLOADS_DIR or
~/Downloads). `wait` blocks until a freshly written file settles (no in-progress
suffix and a stable size), then prints its path. `move` relocates a completed
download; `quarantine` relocates it into a locked-down directory with the
executable bit stripped and mode 0600 so it cannot be run in place.
"""

import os
import pathlib
import shutil
import sys
import time

# Partial-download markers used by browsers.
_PARTIAL_SUFFIXES = ('.part', '.crdownload', '.tmp', '.download')


def _downloads_dir():
    return pathlib.Path(
        os.environ.get('DESKTOP_DOWNLOADS_DIR') or os.path.expanduser('~/Downloads')
    )


def _is_partial(p):
    return p.name.endswith(_PARTIAL_SUFFIXES) or p.name.startswith('.')


def wait(timeout=None):
    """Wait for the newest download to finish; print its path.

    A file is "finished" when it has no partial suffix and its size is unchanged
    across two samples ~0.7s apart. Considers only files modified after wait
    started, so a stale file already in the directory is not mis-reported.
    """
    try:
        deadline = time.time() + (float(timeout) if timeout is not None else 60.0)
    except (TypeError, ValueError):
        print(f"ERROR: invalid timeout {timeout!r}", file=sys.stderr)
        sys.exit(1)
    downloads = _downloads_dir()
    if not downloads.is_dir():
        print(f"ERROR: downloads directory not found: {downloads}", file=sys.stderr)
        sys.exit(1)
    start = time.time()
    sizes = {}
    while time.time() < deadline:
        candidates = [
            p for p in downloads.iterdir()
            if p.is_file() and not _is_partial(p) and p.stat().st_mtime >= start - 1
        ]
        # If any partial download is in flight, keep waiting.
        partial_active = any(
            p.is_file() and p.name.endswith(_PARTIAL_SUFFIXES) for p in downloads.iterdir()
        )
        if candidates and not partial_active:
            newest = max(candidates, key=lambda p: p.stat().st_mtime)
            size = newest.stat().st_size
            if sizes.get(newest) == size and size > 0:
                print(str(newest))
                return
            sizes[newest] = size
        time.sleep(0.7)
    print("ERROR: no completed download within timeout", file=sys.stderr)
    sys.exit(2)


def inspect():
    """List the download directory as JSON (download.inspect): each file with
    size, mtime, and whether it is still an in-progress partial download."""
    import json
    downloads = _downloads_dir()
    if not downloads.is_dir():
        print(json.dumps({'directory': str(downloads), 'files': []}, separators=(',', ':')))
        return
    files = []
    for p in sorted(downloads.iterdir(), key=lambda q: q.name):
        if not p.is_file():
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        files.append({
            'name': p.name,
            'size': st.st_size,
            'mtime': int(st.st_mtime),
            'partial': p.name.endswith(_PARTIAL_SUFFIXES),
        })
    print(json.dumps({'directory': str(downloads), 'files': files}, separators=(',', ':')))


def _validated_src(src):
    if not src:
        print("ERROR: source path required", file=sys.stderr)
        sys.exit(1)
    p = pathlib.Path(src)
    if not p.is_file():
        print(f"ERROR: source is not a file: {src}", file=sys.stderr)
        sys.exit(1)
    return p


def move(src, dst):
    src_p = _validated_src(src)
    if not dst:
        print("ERROR: download-move requires <src> <dst>", file=sys.stderr)
        sys.exit(1)
    dst_p = pathlib.Path(dst)
    if dst_p.is_dir():
        dst_p = dst_p / src_p.name
    if not dst_p.parent.is_dir():
        print(f"ERROR: destination directory does not exist: {dst_p.parent}", file=sys.stderr)
        sys.exit(1)
    shutil.move(str(src_p), str(dst_p))
    print(str(dst_p))


def quarantine(src):
    src_p = _validated_src(src)
    qdir = pathlib.Path(
        os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))
    ) / 'desktop' / 'quarantine'
    qdir.mkdir(parents=True, exist_ok=True)
    os.chmod(qdir, 0o700)
    dst_p = qdir / src_p.name
    shutil.move(str(src_p), str(dst_p))
    # Strip executable bits and restrict to owner read/write so it cannot run.
    os.chmod(dst_p, 0o600)
    print(str(dst_p))
