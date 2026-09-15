# ClawPod Node 0.1.1 validation scope

The four installers were built on 2026-09-15 and transferred without rebuilding.
Their size and SHA-256 are recorded in [release.json](release.json) and checked
again before staging. `sourceCommit` identifies the bundled **Agent runtime**
source (`a4fc6c41f2bb6f442ba9182cd55279617649a378`), not the Node installer wrapper.
`installerSourceCommit` separately identifies the Node installer wrapper source
(`caace97495e617bf2696f2ef048d83e37e64d2ce`). The original packaging source and
validation record live under the private Agent repository's `node/` directory.

| Check from the installer implementation | Result | Scope |
| --- | --- | --- |
| Automated tests | PASS | 36 default tests; two opt-in integration cases executed separately |
| Bundled CLI protocol | PASS | Actual bundled runtime connected over private IPv4 and IPv4-mapped IPv6; existing protocol checks retained |
| Setup page | PASS | Chromium render/save/authentication clearing; no saved authentication value in status output |
| Linux offline installation | PASS | Fresh 0.1.1 DEB installation in a Debian 12 container without network access or preinstalled Node.js |
| Linux upgrade/removal | PASS | Active upgrade, own-service cleanup, preservation of app state and unrelated Agent state |
| POSIX crash recovery | PASS | Helper/daemon loss, child process cleanup, bounded restart without duplicate CLI |
| Four package formats | PASS | DEB, two Apple XAR PKGs, Windows NSIS EXE and target payloads |
| Native macOS/Windows lifecycle | NOT RUN | Requires machines with these operating systems |
| Desktop login startup | NOT RUN | Registration contracts tested; actual graphical login not exercised |
| Signing/notarization | NOT DONE | All four packages are unsigned |

The Agent implementation tests cover the new installer behavior. The Linux
installation, active upgrade, and removal smoke was repeated for these exact
0.1.1 bytes during distribution preparation. Native macOS/Windows lifecycle
tests were not repeated. The protocol fixture is not proof of production
Gateway pairing.

Distribution validation includes:

- 184 Node Harness tests, including address boundaries, IPv4-mapped addresses,
  installer selection, manifest provenance, and legacy compatibility.
- 65 repository tests (five optional runtime checks skipped), 20 registry core
  tests, and five registry end-to-end tests.
- Registry generation and validation, packaged-manifest synchronization, and
  skill format checks.
- A 160-URL comparison between the Harness selector and the actual Node app:
  acceptance and normalized addresses agree for all cases.
- Complete-before-copy staging of four installers, four checksums, and the
  public manifest. Raw private build reports are excluded.

Publication verification downloads all nine assets without authentication and
compares their bytes with the staged release. This checks public reachability
and artifact integrity; it does not install software on a user's computer.

Before promoting to a production release, verify clean native OS installation,
actual Gateway pairing, sign out/in, stop/start, active upgrade, and removal.
Complete macOS signing/notarization and Windows signing as separate release work.
