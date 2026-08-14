# Google Workspace 0.3.5 binding-GID evidence

All validation is local and uses synthetic credentials and scripted HTTP only. No provider writes, live credentials, service restart, installation, publication, or network access is part of this release evidence.

The regression suite models a protected `/workspace` boundary whose store GID is 1000 while the process default GID differs, and checks the root, credential directory, backup directory, lock, registry, credential, and temporary creation paths. Filesystems whose user namespace cannot represent GID 1000 report that one environmental skip while descriptor-level ownership/failure tests continue.

Failure injection covers explicit chown, partial write, registry replacement, symlink/hardlink and path-swap defenses, fsync/permission repair rollback, repeat invocation, legacy-source preservation, revision stability, backup stability, and cleanup of uncommitted credential files. Repository Gateway tests exercise the installed manifest's prepare-to-run path over scripted HTTP and verify repeated credential-free runs do not bootstrap protected state.

Final command results are recorded in the committing agent's handoff and `tests/TEST.md`; the required protected/manual Google acceptance suite remains intentionally out of scope.

## Local validation record

- Google Workspace package excluding loopback-socket OAuth tests: `176 passed, 1 skipped, 164 subtests passed`. The skip is the GID-1000 ownership test because this sandbox's user namespace rejects that numeric group; the same test runs where GID 1000 is representable.
- Binding/permission/release/Gateway representative suite: `113 passed, 1 skipped`.
- Installed Gateway parser and prepare-to-run plus registry synchronization/version gates: `22 passed`.
- Focused command, redaction, onboarding, failure, and idempotency suite: `67 passed, 164 subtests passed`.
- Registry generation check and repository schema validation passed for all 36 entries; the standard repository unittest suite passed 43 of 44 tests. Its sole unrelated failure is the pre-existing `clawpod-video-studio` credential-free self-report returning status 12 in this environment.
- Unfiltered pytest collection is unavailable because the environment resolves three ClawPod Cloud Webhooks tests against an older installed `cli_anything` package. Loopback OAuth tests are unavailable because local socket binding is prohibited. Neither limitation exercises the modified protected-binding implementation.
