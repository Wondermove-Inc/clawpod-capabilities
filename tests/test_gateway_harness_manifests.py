"""Compatibility gate against the installed OpenClaw Gateway manifest parser.

This deliberately imports the live parser instead of duplicating its schema. The
repository currently pins these semantics to OpenClaw Gateway 2026.4.11; newer
installed runtimes are tested as-is so schema drift is visible immediately.
"""

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
HARNESS_GLOB = "harnesses/*/harness.json"
RUNTIME_ROOT = Path("/usr/lib/node_modules/openclaw")
PINNED_GATEWAY_VERSION = "2026.4.11"


class GatewayHarnessManifestTests(unittest.TestCase):
    def _gateway_module(self):
        dist = RUNTIME_ROOT / "dist"
        if not dist.is_dir() or not (RUNTIME_ROOT / "package.json").is_file():
            self.skipTest("current OpenClaw Gateway runtime is not installed")
        modules = [
            path
            for path in dist.glob("system-prompt-*.js")
            if "parseCliHarnessManifest as f" in path.read_text(errors="ignore")
        ]
        if not modules:
            self.fail(
                f"installed OpenClaw Gateway has no discoverable parseCliHarnessManifest export under {dist}"
            )
        self.assertEqual(len(modules), 1, f"ambiguous Gateway parser modules: {modules}")
        return modules[0]

    def _parse_with_gateway(self, manifests):
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
            ["node", "-e", script, self._gateway_module().as_uri()],
            input=json.dumps(manifests),
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def _gateway_runner_module(self):
        modules = list((RUNTIME_ROOT / "dist").glob("pi-embedded-runner-*.js"))
        modules = [path for path in modules if "buildCliHarnessRunIntent as d" in path.read_text(errors="ignore")]
        if len(modules) != 1:
            self.fail(f"expected one installed Gateway runner module, found {modules}")
        return modules[0]

    def test_all_canonical_harnesses_match_live_gateway_parser(self):
        paths = sorted(ROOT.glob(HARNESS_GLOB))
        self.assertEqual(len(paths), 18, f"expected 18 canonical Harness manifests, found {len(paths)}")
        parsed = self._parse_with_gateway(
            [{"name": str(path.relative_to(ROOT)), "manifest": json.loads(path.read_text())} for path in paths]
        )
        failures = [
            f"{item['name']}: {json.dumps(item['result'].get('issues', []), ensure_ascii=False)}"
            for item in parsed
            if not item["result"].get("ok")
        ]
        self.assertFalse(failures, "live Gateway parser rejected canonical manifests:\n" + "\n".join(failures))

    def test_live_gateway_rejects_unsupported_top_level_key(self):
        manifest_path = ROOT / "harnesses" / "atlassian" / "harness.json"
        manifest = json.loads(manifest_path.read_text())
        manifest.update(json.loads((ROOT / "tests/fixtures/gateway-invalid-top-level-key.json").read_text()))
        result = self._parse_with_gateway(
            [{"name": str(manifest_path.relative_to(ROOT)), "manifest": manifest}]
        )[0]["result"]
        self.assertIs(result["ok"], False)
        self.assertTrue(
            any(issue.get("code") == "MANIFEST_SCHEMA_INVALID" for issue in result.get("issues", [])),
            result,
        )

    def test_gateway_semantics_version_pin_documents_current_contract(self):
        package = json.loads((RUNTIME_ROOT / "package.json").read_text()) if RUNTIME_ROOT.is_dir() else None
        if package is None:
            self.skipTest("current OpenClaw Gateway runtime is not installed")
        self.assertEqual(PINNED_GATEWAY_VERSION, "2026.4.11")
        # This records the audited baseline. The compatibility tests above still run
        # against later runtimes rather than skipping or reimplementing their schema.
        self.assertGreaterEqual(
            tuple(map(int, package["version"].split("."))),
            tuple(map(int, PINNED_GATEWAY_VERSION.split("."))),
        )

    def test_google_workspace_live_gateway_prepare_and_run_pagination(self):
        if not RUNTIME_ROOT.is_dir():
            self.skipTest("current OpenClaw Gateway runtime is not installed")
        script = r"""
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const discovery = await import(process.argv[1]);
const runner = await import(process.argv[2]);
const workspace = process.argv[3];
const report = discovery.d({workspaceDir: workspace, roots: [path.join(workspace, 'harnesses')]});
const entry = report.entries.find(item => item.name === 'google-workspace');
if (!entry || !entry.validation.ok) throw new Error('google-workspace harness was not discoverable and valid');
entry.trust.trustState = 'trusted';
entry.runEligible = true;
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gw-gateway-'));
const mock = path.join(dir, 'mock.json');
const cases = [
  ['gmail.messages.list', {pageSize: 10}, {messages: []}],
  ['calendar.events.list', {pageSize: 10, params: JSON.stringify({calendarId: 'primary'})}, {items: []}],
  ['drive.files.list', {pageSize: 10}, {files: []}],
  ['gmail.messages.list', {params: JSON.stringify({maxResults: 10})}, {messages: []}],
  ['calendar.events.list', {params: JSON.stringify({calendarId: 'primary', maxResults: 10})}, {items: []}],
  ['drive.files.list', {params: JSON.stringify({pageSize: 10})}, {files: []}],
];
const results = [];
try {
  for (const [command, input, response] of cases) {
    fs.writeFileSync(mock, JSON.stringify([{body: response}]));
    const intent = runner.d({entry, commandName: command, input, workspaceDir: workspace});
    const executed = runner.f(intent, {secretEnv: {GOOGLE_WORKSPACE_MOCK_HTTP: mock}});
    results.push({command, input, argv: intent.argv, exitCode: executed.exitCode, output: JSON.parse(executed.stdout)});
  }
  let rejected = 0;
  for (const invalid of [10.5, '10', true]) {
    try { runner.d({entry, commandName: 'drive.files.list', input: {pageSize: invalid}, workspaceDir: workspace}); }
    catch { rejected += 1; }
  }
  console.log(JSON.stringify({results, rejected}));
} finally {
  fs.rmSync(dir, {recursive: true, force: true});
}
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script, self._gateway_module().as_uri(), self._gateway_runner_module().as_uri(), str(ROOT)],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual(evidence["rejected"], 3)
        self.assertEqual(len(evidence["results"]), 6)
        for item in evidence["results"]:
            self.assertEqual(item["exitCode"], 0, item)
            self.assertTrue(item["output"]["ok"], item)
        for item in evidence["results"][:3]:
            self.assertIn("--page-size", item["argv"])
            self.assertEqual(item["argv"][item["argv"].index("--page-size") + 1], "10")


if __name__ == "__main__":
    unittest.main()
