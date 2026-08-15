import json, subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
RUNTIME = Path('/usr/lib/node_modules/openclaw')


def modules():
    discovery = [p for p in (RUNTIME/'dist').glob('system-prompt-*.js') if 'parseCliHarnessManifest as f' in p.read_text(errors='ignore')]
    runner = [p for p in (RUNTIME/'dist').glob('pi-embedded-runner-*.js') if 'buildCliHarnessRunIntent as d' in p.read_text(errors='ignore')]
    assert len(discovery) == len(runner) == 1
    return discovery[0], runner[0]


def test_every_desktop_command_prepares_with_live_gateway_parser():
    discovery, runner = modules()
    script = r"""
import path from 'node:path';
const discovery = await import(process.argv[1]);
const runner = await import(process.argv[2]);
const root = process.argv[3];
const report = discovery.d({workspaceDir: root, roots: [path.join(root, 'harnesses')]});
const entry = report.entries.find(item => item.name === 'desktop');
if (!entry || !entry.validation.ok) throw new Error('desktop harness invalid');
entry.trust.trustState = 'trusted'; entry.runEligible = true;
const rows = [];
for (const command of Object.keys(entry.manifest.commands)) {
  const schema = entry.manifest.commands[command].inputSchema;
  const input = {};
  const values = {input: '{}', requestId: 'gateway-test', timeoutMs: 1000, idempotencyKey: 'gateway-key', expectedRevision: 0, approvalFile: '/tmp/approval.json', dryRun: true, runRoot: '/workspace/desktop-runs/gateway-test'};
  for (const name of schema.required || []) input[name] = values[name];
  if (schema.properties.input) input.input = '{}';
  const intent = runner.d({entry, commandName: command, input, workspaceDir: root});
  rows.push({command, argv: intent.argv});
}
let rejected = 0;
for (const bad of [{timeoutMs: '30'}, {dryRun: 'true'}, {expectedRevision: 1.5}, {unknown: true}]) {
  try { runner.d({entry, commandName: 'ui.observe', input: bad, workspaceDir: root}); } catch { rejected++; }
}
console.log(JSON.stringify({rows, rejected}));
"""
    result = subprocess.run(['node', '--input-type=module', '-e', script, discovery.as_uri(), runner.as_uri(), str(ROOT)], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(result.stdout)
    contracts = json.loads((ROOT/'harnesses/desktop/command_contracts.json').read_text())['commands']
    assert len(evidence['rows']) == len(contracts) == 67
    assert {row['command'] for row in evidence['rows']} == set(contracts)
    assert evidence['rejected'] == 4
    for row in evidence['rows']:
        assert row['argv'][0] == row['command']
        assert '--input' in row['argv'] and row['argv'][row['argv'].index('--input') + 1] == '{}'
