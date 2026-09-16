# ClawPod Node 0.2.2 validation scope

The user launchers clear `CLAWPOD_NODE_NO_BROWSER` only when opening settings.
macOS initial launch and Finder reopen, Windows app shortcut, and Linux desktop
launch therefore open the default browser. Quiet installer/service startup and
non-open control commands retain their existing behavior. An existing setup
server is reused; opening settings does not restart the paired worker.

Installer/launcher source: `55e6a76857d2391763fc795dfd775cbcf49fe0e2`.
Bundled Agent runtime source: `f55bbd3bdde877b2be2e66fa4e58ba7ad28f0d33`.
The unchanged runtime was reused; Mac native launchers were rebuilt for both
architectures. Build reports keep these two source identities separate.

- `pnpm check` and `pnpm build`: PASS.
- Capabilities repository suite: 67 tests, six skipped, no failures. Harness
  suite: 184 passed. Actual Agent parser/prepare/run integration: two passed.
- Node suite: 49 passed, eight platform/opt-in tests skipped, zero failures.
- macOS app-delegate regression: old source reproduces inherited quiet mode;
  patched source passes initial launch, explicit open, repeated Finder reopen,
  retained native-app PID, and quiet non-open commands. This uses a separate
  AppKit fixture identity; it is not a production desktop IPC or GUI-input test.
- Linux final DEB: offline install/reinstall/remove and real bundled CLI fixture
  PASS. Two installed-launcher calls with inherited quiet mode each invoke the
  browser shim; both reuse the same authenticated, working setup endpoint.
- macOS final ARM package: deep/strict signature and bundled CLI fixture PASS.
  Existing production app, pairing and GUI permission entries were not replaced.
- Both Mac packages and Windows EXE: extraction, source/version identity and
  every prepared payload file's contents checked against the extracted package.
- Windows and Intel Mac native execution, actual Linux graphical browser launch,
  login-startup and production Gateway pairing are not claimed. Browser invocation
  on Linux was captured by an `xdg-open` shim.

Both Mac installers were replaced on 2026-09-16 at the operator's request with
Developer ID signed, Apple-notarized packages with stapled tickets. Windows
publisher signing is not included. Gateway token/authentication errors are a
separate issue and are not fixed by this launcher patch. Installing the updated
Node app is required; an Agent image rollout alone does not update a user's app.

Artifact hashes:

| Target | Bytes | SHA-256 |
| --- | ---: | --- |
| darwin-arm64 | 263428683 | `a6374d3d716fe13405ba290ecd611ed3dbf36899c77e7681e20fe224e2e0d2c4` |
| darwin-x64 | 231233396 | `7332387d85059aa14ad3c27906df22064ee7e0778fe7122124f6798e70f5591f` |
| linux-x64 | 176241640 | `630fb5c0adbac2fb991ce6a7c14f4cfe415c87b53f9d222c2101d7574f682ee9` |
| win32-x64 | 203317999 | `6e4ad2b28231dc4dcdc46a9f3750317700b41076b8b0775fc151abb1d6385727` |

The manifest's broad `nativeMacOS` field remains `not-run`: both architectures
have not been executed natively. Apple Silicon coverage is reported above.

The staged public release contains four installers, four basename-only checksum
files and sanitized `release.json`. Local build reports are not public assets.
The public release tag identifies a reviewed capabilities commit, separately
from the Agent runtime and installer source commits above. Public downloads
must be checked without authentication after publication.

## Mac signing replacement verification (2026-09-16)

- Both PKGs: Apple notarization Accepted with no issues, staple validation PASS,
  and Gatekeeper install assessment accepted as Notarized Developer ID.
- Staged apps: strict nested signature checks and Gatekeeper execution assessment
  PASS; native helper hashes match both embedded manifests.
- Runtime checks: Apple Silicon native and Intel under Rosetta PASS (JIT, Wasm,
  workers, native modules, PTY). App launch and setup IPC PASS for both builds.
- Source content comparison and package readback PASS. Changes are signing and
  the dependent native executable digests; application behavior is unchanged.
- No installation over the user's current app, live GUI input/capture with the
  new signing identity, or physical Intel Mac validation is claimed.
- Installer version remains 0.2.2. Previously downloaded Mac files and capability
  manifests have old checksums: re-download the installer and update the
  clawpod-node-host Skill/Harness to 0.7.3.

Superseded Mac hashes (retained only as replacement history):

- arm64: `2e0473e0ba0837003a39e1a9eb1c24f28948002d700c83785916e9d2acc46eae`
- x64: `0be1038284a7c419f85ddf1bf01d45d8034450e9cc91265324e8b14227484276`

The current hashes are in the table above and release.json. The release tag was
not moved; this signed asset replacement does not change the original source provenance.
