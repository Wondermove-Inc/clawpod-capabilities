# ClawPod Node 0.2.1 validation scope

This preview contains the Node CLI lifecycle patch. Both bundled runtime
`sourceCommit` and installer wrapper `installerSourceCommit` identify
`f55bbd3bdde877b2be2e66fa4e58ba7ad28f0d33` in the Agent repository.
The public release tag identifies the separately reviewed capabilities commit.

## Release checks

| Check | Result | Scope |
| --- | --- | --- |
| Agent type, lint, source build and Control UI build | PASS | Committed release source; the private build snapshot contains its own dependency copy. |
| Node app tests | PASS | 48 tests, seven opt-in tests skipped in the default run. Bundled-runtime tests run separately below. |
| Source lifecycle regression | PASS | Repeated/mixed shutdown signals, pending spawn, process-tree termination, PTY input, output decoding and worker continuation. |
| Agent full suite | MIXED | 40,711 passed, two failures (Gateway port collision and plugin cache identity). Both failing files passed separate reruns. This is not an all-green full-suite claim. |
| Release distribution and Harness tests | PASS | Repository suite: 67 tests, six skipped. Harness suite: 184 passed. |

The packaged-runtime fixture uses the real Node setup server, worker wrapper,
bundled CLI and a local Gateway protocol fixture. It checks advertised commands,
stdout/stderr and nonzero exit, Korean/English output, managed stdin/EOF, PTY
input/output, command timeout, and app Stop while a child and grandchild are
active. The test verifies that the grandchild cannot write a delayed marker.
It does not contact a provider or change production pairing/settings.

A release candidate failed the app Stop test: group SIGTERM plus CLI signal
forwarding delivered a repeated signal that interrupted asynchronous cleanup.
Persistent signal handlers fixed the race; all installers were rebuilt from the
corrected commit. The failed candidate is not distributed.

## Platform scope

| Platform | Result | Scope |
| --- | --- | --- |
| Linux x64 | PASS | Final DEB installed in Debian 12 with networking disabled; real bundled Gateway protocol/CLI fixture passed, including active-grandchild cleanup. |
| macOS Apple Silicon | PASS | Final PKG expanded with pkgutil; full-app deep/strict signature, version and source identity verified. Its bundled runtime passed the CLI fixture on Mac Studio, including PTY input and active-grandchild cleanup. The installed production app/settings were not replaced. |
| macOS Intel | PACKAGE VERIFIED | Final PKG extraction, deep/strict signature, target/version/provenance and PTY package checked. No native Intel runtime test. |
| Windows x64 | PACKAGE VERIFIED | Final EXE extracted; every payload file compared to the prepared target, with version/source identity and native PTY inclusion verified. No Windows runtime test. |

Exact artifact sizes and SHA-256 hashes are in [release.json](release.json).
Windows and Intel Mac native execution, GUI/login-startup revalidation, actual
Wayland compositor behavior, and production Gateway pairing are not claimed.
The unchanged native helpers are reused only after current source digest,
architecture, executable and dependency inventory checks for all four targets.
Previous 0.2.0 GUI verification is historical evidence, not a new 0.2.1 test.

Mac apps are ad-hoc signed. Developer ID signing, notarization and Windows
publisher signing are not included. The manifest's broad `nativeMacOS` field
remains `not-run` because both architectures have not been tested natively;
specific Apple Silicon CLI coverage is reported separately. An ad-hoc app update
may require refreshing the existing macOS GUI permission entry.

## Compatibility and distribution

Update both the controlling Agent and Node app for managed CLI. Older nodes
retain synchronous execution; new Node installation alone does not update the
Agent's tool/runtime behavior. The capability package only provides instructions
and installer metadata. It does not install either runtime automatically.

The staged release contains exactly four installers, four basename-only SHA-256
files, and sanitized `release.json`. Raw reports with build-machine paths are
excluded. All four embedded source identities, versions, runtime dependencies and
artifact bytes must match the manifest. Public downloads are checked without
authentication after publication. Existing published releases remain immutable.
