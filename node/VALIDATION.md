# ClawPod Node 0.2.0 validation scope

This distribution promotes the exact four installers verified in the Agent
repository. No installer is rebuilt or re-signed here. Both `sourceCommit` and
`installerSourceCommit` identify `9c1e6b08c72c8e9f024a2570892556febad87676` for this
build: the bundled Agent source and integrated installer wrapper are from that
same commit. They remain separate provenance fields. Later Agent commits through
`9e5c736af2` changed documentation only.

The installer sizes and hashes in [release.json](release.json) come from the
original build reports and are rechecked against all four binary files. Raw build
reports contain machine-local paths and are not public assets.

## Implementation and installed-package evidence

| Check | Result | Scope |
| --- | --- | --- |
| Agent full test suite | PASS | 61 shards, 4,369 files, 40,679 tests; one file/16 tests skipped. A first heap-limited run was rerun with sufficient heap. |
| Agent build, type, and checks | PASS | Final implementation and packaging surfaces, recorded in Agent `node/VALIDATION.md`. |
| Node app tests | PASS | 46 default tests; seven opt-in cases skipped in that run. |
| Final setup page | PASS | Four Chromium UI tests against the final payload. |
| macOS Apple Silicon | PASS | Actual installed app permissions, screenshot, Korean/English/emoji input, 24/24 targeted clicks, drag, cancellation/release cleanup. |
| Mac upgrade/configuration | PASS | 0.1.1-to-0.2.0 preserved settings, identity, and requested running state; installed IPC setup response verified. |
| Linux X11 | PASS | Final DEB installed in Debian 12 containers; native input/capture and actual Node protocol fixture. |
| macOS Intel | PACKAGE VERIFIED | Native compile, PKG extraction, full-app ad-hoc signature and executable/inventory checks; no actual Intel GUI execution. |
| Windows | PACKAGE VERIFIED | EXE extraction and native payload/inventory checks; no actual Windows GUI execution. |
| Wayland | FIXTURE VERIFIED | Private D-Bus fixture; no actual compositor session. |
| Desktop sign-out/sign-in | NOT RUN | Full native graphical login-startup lifecycle is not established. |
| Production Gateway pairing | NOT ESTABLISHED | Protocol fixtures and app readiness are not proof of a production pairing. |
| Public signing | NOT DONE | Mac app ad-hoc signing is verified; no Developer ID/notarization or Windows publisher signing. |

The compact manifest retains `nativeMacOS: not-run` because complete native Mac
coverage across both architectures has not run. It does not negate the specific
Apple Silicon checks above. `nativeWindows` and `desktopLoginStartup` also remain
`not-run`; Linux offline installation is `passed`. Do not interpret these coarse
flags as a per-architecture result or label the preview production-validated.

The Linux helper needs glibc 2.36+ and an interactive desktop. X11 clipboard
preservation requires a clipboard manager; Wayland paste requires Clipboard
portal support. OS setup details are in [the download guide](README.md).

## Distribution checks

Distribution preparation passed 197 scoped Harness/distribution tests (one optional
runtime test skipped in that run), then the actual Agent-source harness preparation
and execution checks passed separately (two tests, including 12 successful command
runs). The repository suite passed 67 tests with six optional checks skipped;
Registry suites passed 20 unit and five end-to-end tests. The pinned routing
expectation was updated to match the new desktop-permission description.
Registry generation, package versions, manifest synchronization, exact four-file
size/hash/provenance checks, and whitespace checks passed. Independent Astra high
review returned GO, followed by the author's source and artifact review.

The existing staging tool checks the complete set before copying and verifies
copied bytes again. Staging contains only four installers, four basename-only SHA-256 files,
and sanitized `release.json`. It excludes raw private build reports.

After publication, download all nine assets without authentication and verify
exact bytes against the staged manifest. Public download verification proves
reachability and artifact integrity, not native installation or Gateway pairing.
Keep old published versions immutable; new installers use `node-v0.2.0`.
