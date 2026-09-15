// Optional cross-repository integration: invoke the actual Agent parser and
// prepare/run/output validator against a temporary installed package. No Gateway
// or production trust state is touched; only installer.info is executed.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [source, repository] = process.argv.slice(2);
const { parseCliHarnessManifest } = await import(pathToFileURL(path.join(source,
  "src/agents/harness-lifecycle/manifest.ts")).href);
const { buildCliHarnessRunIntent, executeCliHarnessRunIntent } = await import(
  pathToFileURL(path.join(source, "src/agents/harness-lifecycle/run-intent.ts")).href);
const workspace = fs.mkdtempSync(path.join(os.tmpdir(), "node-harness-runtime-"));
try {
  const root = path.join(workspace, "harnesses/clawpod-node-host");
  const registry = JSON.parse(fs.readFileSync(path.join(repository, "registry/index.json"), "utf8"));
  const pack = registry.capabilities.find(item => item.type === "harness" && item.id === "clawpod-node-host");
  for (const item of pack.files) {
    const target = path.join(root, item.path);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.copyFileSync(path.join(repository, pack.path, item.path), target);
  }
  const manifestPath = path.join(root, "harness.json");
  const raw = fs.readFileSync(manifestPath, "utf8");
  const parsed = parseCliHarnessManifest(JSON.parse(raw));
  assert.equal(parsed.ok, true, JSON.stringify(parsed.issues));
  const entrypoint = fs.realpathSync(path.join(root, parsed.manifest.entrypoint));
  fs.chmodSync(entrypoint, 0o755);
  const hash = bytes => `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
  const entry = {
    name: parsed.manifest.name, root, manifestPath, manifest: parsed.manifest,
    trust: { trustState: "trusted", manifestDigest: hash(raw),
      resolvedEntrypointPath: entrypoint, resolvedEntrypointDigest: hash(fs.readFileSync(entrypoint)) },
    runEligible: true,
  };
  const prepare = (input, commandName = "installer.info") =>
    buildCliHarnessRunIntent({ entry, commandName, input, workspaceDir: workspace });
  // Preparation checks all three real schemas. Never run Tailscale commands.
  prepare({}, "agent.status");
  prepare({}, "agent.login");
  prepare({ platform: "macos", arch: "arm64" });
  let successfulRuns = 0;
  for (const [platform, arch] of [["macos", "arm64"], ["macos", "x64"], ["linux", "x64"], ["windows", "x64"]]) {
    for (const gatewayUrl of [undefined, "ws://100.64.1.2:18789", "wss://gateway.example.com"]) {
      const intent = prepare({ platform, arch, ...(gatewayUrl ? { gatewayUrl } : {}) });
      assert.equal(intent.approvalRequired, false);
      const run = executeCliHarnessRunIntent(intent);
      assert.equal(run.exitCode, 0, run.stderr);
      const output = JSON.parse(run.stdout);
      assert.equal(output.ok, true);
      assert.equal(output.installer.platform, platform);
      assert.equal(output.installer.arch, arch);
      assert.equal(output.installer.remoteAvailability, "unchecked");
      assert.deepEqual(output.effects, []);
      if (gatewayUrl) assert.deepEqual(output.gateway, { url: gatewayUrl, privateWsOptInRequired: false });
      successfulRuns++;
    }
  }
  const valid = { platform: "macos", arch: "arm64" };
  for (const [input, message] of [
    [{}, /input.platform is required/],
    [{ platform: "macos" }, /input.arch is required/],
    [{ arch: "arm64" }, /input.platform is required/],
    [{ ...valid, gatewayUrl: 42 }, /input.gatewayUrl must match schema type string/],
    [{ ...valid, unexpected: true }, /input.unexpected is not allowed/],
  ]) assert.throws(() => prepare(input), message);

  // Restore the exact 0.5.0 incompatibility in memory: discovery accepts it, but
  // execution preparation rejects it even when the optional value is omitted.
  const broken = structuredClone(parsed.manifest);
  broken.commands["installer.info"].inputSchema.properties.gatewayUrl.description = "Gateway root URL.";
  assert.equal(parseCliHarnessManifest(broken).ok, true);
  entry.manifest = broken;
  for (const input of [valid, { ...valid, gatewayUrl: "ws://100.64.1.2:18789" }]) {
    assert.throws(() => prepare(input), /input.gatewayUrl uses unsupported schema keyword description/);
  }
  console.log(JSON.stringify({ preparedCommands: 3, successfulRuns, legacyRejected: 2, invalidRejected: 5 }));
} finally {
  fs.rmSync(workspace, { recursive: true, force: true });
}
