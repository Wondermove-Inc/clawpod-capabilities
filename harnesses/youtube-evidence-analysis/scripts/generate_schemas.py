#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
commands = {
    "status": ({}, [], False),
    "preflight": ({}, [], False),
    "video.normalize": ({"video": "string"}, ["video"], False),
    "metadata.oembed": ({"video": "string", "timeout": "integer", "maxBytes": "integer"}, ["video"], False),
    "caption.fallback": ({"video": "string"}, ["video"], False),
    "transcript.import": ({"inputRoot": "string", "input": "string", "video": "string", "language": "string", "sourceKind": "string", "outputRoot": "string", "output": "string", "overwrite": "boolean"}, ["inputRoot", "input", "video", "language", "sourceKind"], True),
    "description.links": ({"inputRoot": "string", "input": "string", "outputRoot": "string", "output": "string", "overwrite": "boolean"}, ["inputRoot", "input"], True),
    "bundle.validate": ({"inputRoot": "string", "input": "string"}, ["inputRoot", "input"], False),
}
flags = {"video": "--video", "inputRoot": "--input-root", "input": "--input", "outputRoot": "--output-root", "output": "--output", "language": "--language", "sourceKind": "--source-kind", "timeout": "--timeout", "maxBytes": "--max-bytes", "overwrite": "--overwrite"}
out = {"type": "object", "required": ["ok", "schemaVersion", "command", "requestId", "effects", "provenance"], "properties": {"ok": {"type": "boolean"}, "schemaVersion": {"type": "integer"}, "command": {"type": "string"}, "requestId": {"type": "string"}, "data": {}, "effects": {"type": "array"}, "provenance": {"type": "object"}, "error": {"type": "object"}}, "additionalProperties": False}
hcommands, contracts = {}, {"schemaVersion": 1, "commands": {}}
for name, (props, required, mutation) in commands.items():
    schema = {"type": "object", "required": required, "properties": {key: {"type": kind} for key, kind in props.items()}, "additionalProperties": False}
    amap = []
    for key, kind in props.items():
        role = "input" if key == "inputRoot" else ("output" if key == "outputRoot" else None)
        entry = {"arg": key, "type": "option", "flag": flags[key], "valueType": "path" if role else kind, "optional": key not in required}
        if role: entry["pathRole"] = role
        amap.append(entry)
    hcommands[name] = {"description": f"Deterministic {name} operation.", "baseArgv": [name], "safetyClasses": ["writeSafe" if mutation else "readOnly"], "inputSchema": schema, "outputSchema": out, "argMap": amap}
    contracts["commands"][name] = {"backend": "python-stdlib", "mutation": mutation, "required": required, "rootPathArgs": sorted(key for key in props if key in ("inputRoot", "outputRoot")), "relativeChildArgs": sorted(key for key in props if key in ("input", "output")), "inputSchema": schema, "outputSchema": out}
harness = {"schemaVersion": 1, "kind": "openclaw.harness.v1", "name": "youtube-evidence-analysis", "title": "YouTube Evidence Analysis", "description": "Normalize YouTube references, import explicit transcripts, extract safe links, and validate timestamped evidence deterministically.", "version": "0.1.0", "entrypoint": "./youtube_evidence_analysis.py", "packageRoot": ".", "execution": {"cwd": ".", "timeoutMs": 25000, "requiresJson": True}, "whenToUse": ["Prepare deterministic records for evidence-led analysis of a YouTube video"], "capabilities": ["youtube-url-normalization", "public-oembed", "transcript-import", "timestamp-evidence-validation"], "authModel": {"type": "none", "storesSecrets": False, "requiresHumanAccount": False}, "commands": hcommands}
(root / "harness.json").write_text(json.dumps(harness, ensure_ascii=False, indent=2) + "\n")
(root / "command_contracts.json").write_text(json.dumps(contracts, ensure_ascii=False, indent=2) + "\n")
print("OK: schemas synchronized")
