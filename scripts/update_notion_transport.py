#!/usr/bin/env python3
"""Normalize Notion structured arguments for the Gateway scalar argMap contract."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harnesses/notion/harness.json"
CONTRACTS = ROOT / "harnesses/notion/command_contracts.json"
ALLOWED = {"string", "number", "integer", "boolean", "enum", "path"}


def main() -> None:
    manifest = json.loads(HARNESS.read_text())
    contracts = json.loads(CONTRACTS.read_text())
    for name, command in manifest["commands"].items():
        structured = []
        properties = command["inputSchema"].get("properties", {})
        contract = contracts["commands"][name]
        known_structured = contract.get("structuredInputSchemas", {})
        for entry in command["argMap"]:
            schema = properties.get(entry["arg"], {})
            schema_type = schema.get("type")
            if schema_type in {"object", "array"}:
                contract_schema = json.loads(json.dumps(schema))
                properties[entry["arg"]] = {
                    "type": "string",
                    "minLength": 2,
                    "maxLength": 500000,
                    "description": f"JSON-encoded {schema_type}; parsed and revalidated by notion.py",
                }
                entry["valueType"] = "string"
                structured.append(entry["arg"])
                contract.setdefault("structuredInputSchemas", {})[entry["arg"]] = contract_schema
            elif entry["arg"] in known_structured:
                entry["valueType"] = "string"
                structured.append(entry["arg"])
            if entry["valueType"] not in ALLOWED:
                raise ValueError(f"{name}.{entry['arg']} has unsupported valueType {entry['valueType']}")
        if structured:
            contract["jsonStringTransport"] = sorted(structured)
        else:
            contract.pop("jsonStringTransport", None)
            contract.pop("structuredInputSchemas", None)
    HARNESS.write_text(json.dumps(manifest, indent=2) + "\n")
    CONTRACTS.write_text(json.dumps(contracts, indent=2) + "\n")

if __name__ == "__main__":
    main()
