# ClawPod Node 0.1.0 validation scope

The four installers were built on 2026-09-14 and transferred without rebuilding.
Their size and SHA-256 are recorded in [release.json](release.json) and checked
again before staging. `sourceCommit` identifies the bundled **Agent runtime**
source (`a4fc6c41f2bb6f442ba9182cd55279617649a378`), not the Node installer wrapper.
The wrapper was shipped by Agent PR #171; the original packaging source and
validation record live under that private repository's `node/` directory.

| Check from the installer implementation | Result | Scope |
| --- | --- | --- |
| Automated tests | PASS | 32 default tests; two opt-in integration cases executed separately |
| Bundled CLI protocol | PASS | Actual bundled runtime connected to a local protocol fixture; system.which and browser proxy status |
| Setup page | PASS | Chromium render/save/authentication clearing; no saved authentication value in status output |
| Linux offline installation | PASS | Debian 12 container without network access or preinstalled Node.js |
| Linux upgrade/removal | PASS | Active upgrade, own-service cleanup, preservation of app state and unrelated Agent state |
| POSIX crash recovery | PASS | Helper/daemon loss, child process cleanup, bounded restart without duplicate CLI |
| Four package formats | PASS | DEB, two Apple XAR PKGs, Windows NSIS EXE and target payloads |
| Native macOS/Windows lifecycle | NOT RUN | Requires machines with these operating systems |
| Desktop login startup | NOT RUN | Registration contracts tested; actual graphical login not exercised |
| Signing/notarization | NOT DONE | All four packages are unsigned |

These are inherited installer implementation results, not newly repeated native
OS tests in this distribution change. The protocol fixture is not proof of a
production Gateway pairing. The independent original implementation review was
GO within the stated scope.

The distribution change adds manifest/asset consistency, complete-before-copy
staging, packaged Harness manifest synchronization, installer selection, and
legacy compatibility tests. Its live release download check verifies bytes and
public reachability; it does not install software on a user's computer.

Before promoting to a production release, verify clean native OS installation,
actual Gateway pairing, sign out/in, stop/start, active upgrade, and removal.
Complete macOS signing/notarization and Windows signing as separate release work.
