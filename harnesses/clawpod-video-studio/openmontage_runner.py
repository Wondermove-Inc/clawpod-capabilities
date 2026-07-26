#!/usr/bin/env python3
"""Isolated stdin/stdout bridge to the pinned OpenMontage ToolRegistry.

The parent process controls approval, timeout, cancellation, secret injection,
and path boundaries. This bridge never reads argv payloads and refuses a
runtime containing .env.
"""
from __future__ import annotations
import dataclasses, enum, hashlib, json, os, sys
from pathlib import Path


def emit(value):
    def default(v):
        if dataclasses.is_dataclass(v): return dataclasses.asdict(v)
        if isinstance(v, enum.Enum): return v.value
        if isinstance(v, Path): return str(v)
        raise TypeError(type(v).__name__)
    sys.stdout.write(json.dumps(value, default=default, sort_keys=True, separators=(",", ":")))


def main():
    runtime = Path(os.environ.get("OPENMONTAGE_RUNTIME", "")).resolve()
    if not runtime.is_dir() or not (runtime / "tools").is_dir():
        emit({"ok": False, "error": {"code": "RUNTIME_NOT_FOUND"}}); return 8
    if (runtime / ".env").exists():
        emit({"ok": False, "error": {"code": "PLAINTEXT_SECRET_FILE_FORBIDDEN"}}); return 9
    raw = sys.stdin.buffer.read(1_000_001)
    if len(raw) > 1_000_000:
        emit({"ok": False, "error": {"code": "INPUT_TOO_LARGE"}}); return 2
    try:
        req = json.loads(raw or b"{}")
        if not isinstance(req, dict): raise ValueError("object required")
        sys.path.insert(0, str(runtime))
        from tools.tool_registry import ToolRegistry
        ToolRegistry._load_dotenv = staticmethod(lambda: None)
        registry = ToolRegistry(); registry.discover()
        operation = req.get("operation")
        if operation == "list":
            emit({"ok": True, "data": {"names": sorted(registry.list_all()), "count": len(registry.list_all())}}); return 0
        name = req.get("tool")
        tool = registry.get(name)
        if tool is None:
            emit({"ok": False, "error": {"code": "TOOL_NOT_FOUND", "tool": name}}); return 3
        if operation == "inspect":
            emit({"ok": True, "data": tool.get_info()}); return 0
        if operation != "run" or not isinstance(req.get("input"), dict):
            emit({"ok": False, "error": {"code": "INVALID_ARGUMENT"}}); return 2
        result = tool.execute(req["input"])
        # Never cross the isolation boundary with arbitrary provider payloads.
        # Preserve only the stable execution evidence needed by the parent.
        artifacts = [str(x) for x in (getattr(result, "artifacts", None) or []) if isinstance(x, (str, Path))]
        safe = {
            "success": bool(getattr(result, "success", False)),
            "artifacts": artifacts,
            "cost_usd": float(getattr(result, "cost_usd", 0.0) or 0.0),
            "duration_seconds": float(getattr(result, "duration_seconds", 0.0) or 0.0),
            "seed": getattr(result, "seed", None) if isinstance(getattr(result, "seed", None), (int, type(None))) else None,
            "model": str(getattr(result, "model", ""))[:200] or None,
            "data_digest": "sha256:" + hashlib.sha256(json.dumps(getattr(result, "data", {}), default=str, sort_keys=True).encode()).hexdigest(),
            "error_type": type(getattr(result, "error", None)).__name__ if getattr(result, "error", None) else None,
        }
        emit({"ok": safe["success"], "data": safe})
        return 0 if safe["success"] else 7
    except Exception as exc:
        # Exception values can contain provider response text, so expose only type.
        emit({"ok": False, "error": {"code": "UPSTREAM_EXCEPTION", "type": type(exc).__name__}})
        return 7


if __name__ == "__main__":
    raise SystemExit(main())
