"""Compatibility gate against the installed OpenClaw Gateway manifest parser.

This deliberately imports the live parser instead of duplicating its schema. The
repository currently pins these semantics to OpenClaw Gateway 2026.4.11; newer
installed runtimes are tested as-is so schema drift is visible immediately.
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
HARNESS_GLOB = "harnesses/*/harness.json"
RUNTIME_ROOT = Path("/usr/lib/node_modules/openclaw")
PINNED_GATEWAY_VERSION = "2026.4.11"


def _gateway_module():
    dist = RUNTIME_ROOT / "dist"
    if not dist.is_dir() or not (RUNTIME_ROOT / "package.json").is_file():
        pytest.skip("current OpenClaw Gateway runtime is not installed")
    modules = [
        path
        for path in dist.glob("system-prompt-*.js")
        if "parseCliHarnessManifest as f" in path.read_text(errors="ignore")
    ]
    if not modules:
        pytest.fail(
            f"installed OpenClaw Gateway has no discoverable parseCliHarnessManifest export under {dist}"
        )
    assert len(modules) == 1, f"ambiguous Gateway parser modules: {modules}"
    return modules[0]


def _parse_with_gateway(manifests):
    script = r"""
import(process.argv[1]).then(async m => {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const inputs = JSON.parse(chunks.join(''));
  const results = inputs.map(({name, manifest}) => ({name, result: m.f(manifest)}));
  console.log(JSON.stringify(results));
}).catch(error => { console.error(error); process.exit(2); });
"""
    result = subprocess.run(
        ["node", "-e", script, _gateway_module().as_uri()],
        input=json.dumps(manifests),
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_all_canonical_harnesses_match_live_gateway_parser():
    paths = sorted(ROOT.glob(HARNESS_GLOB))
    assert len(paths) == 18, f"expected 18 canonical Harness manifests, found {len(paths)}"
    parsed = _parse_with_gateway(
        [{"name": str(path.relative_to(ROOT)), "manifest": json.loads(path.read_text())} for path in paths]
    )
    failures = [
        f"{item['name']}: {json.dumps(item['result'].get('issues', []), ensure_ascii=False)}"
        for item in parsed
        if not item["result"].get("ok")
    ]
    assert not failures, "live Gateway parser rejected canonical manifests:\n" + "\n".join(failures)


def test_live_gateway_rejects_unsupported_top_level_key():
    manifest_path = ROOT / "harnesses" / "atlassian" / "harness.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update(json.loads((ROOT / "tests/fixtures/gateway-invalid-top-level-key.json").read_text()))
    result = _parse_with_gateway([{"name": str(manifest_path.relative_to(ROOT)), "manifest": manifest}])[0]["result"]
    assert result["ok"] is False
    assert any(issue.get("code") == "MANIFEST_SCHEMA_INVALID" for issue in result.get("issues", [])), result


def test_gateway_semantics_version_pin_documents_current_contract():
    package = json.loads((RUNTIME_ROOT / "package.json").read_text()) if RUNTIME_ROOT.is_dir() else None
    if package is None:
        pytest.skip("current OpenClaw Gateway runtime is not installed")
    assert PINNED_GATEWAY_VERSION == "2026.4.11"
    # This records the audited baseline. The compatibility tests above still run
    # against later runtimes rather than skipping or reimplementing their schema.
    assert tuple(map(int, package["version"].split("."))) >= tuple(map(int, PINNED_GATEWAY_VERSION.split(".")))
