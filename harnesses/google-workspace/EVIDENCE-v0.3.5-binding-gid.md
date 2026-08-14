# Google Workspace 0.3.5 binding-GID evidence

All validation is local and uses synthetic credentials and scripted HTTP only. No provider writes, live credentials, service restart, installation, publication, or network access is part of this release evidence.

## Generic proof

The table-driven regression suite varies protected-store GIDs, aliases, process GIDs, supplementary groups, and setgid inheritance. It checks the root, credential directory, backup directory, lock, registry, credential, staging, and temporary creation paths. The implementation derives identity only from verified store/root-parent snapshots and never gives process EGID or supplementary membership authority. Descriptor-level tests prove unavailable and denied `fchown` fail closed even on filesystems that cannot represent arbitrary synthetic numeric groups.

Failure injection covers directory/file ownership, missing ownership primitives, partial write, registry replacement, symlink/hardlink and path-swap defenses, fsync/permission repair rollback, repeat invocation, legacy-source preservation, revision stability, backup stability, and cleanup of uncommitted credential files. Repository Gateway tests exercise the installed manifest's prepare-to-run path over scripted HTTP and verify repeated credential-free runs do not bootstrap protected state.

## Deployment-specific live evidence

The generic proof does not depend on Forge, a captain account, or GID 1000. A live Forge captain/GID-1000 reinstall and read-only binding verification remains separate orchestrator evidence and is not claimed by these local tests.

Final command results are recorded in the committing agent's handoff and `tests/TEST.md`; the required protected/manual Google acceptance suite remains intentionally out of scope.

## Local validation record

- Google Workspace package excluding loopback-socket OAuth tests: `180 passed, 13 skipped, 164 subtests passed`. The skips are the deployment-shape test plus twelve table rows requiring synthetic numeric GIDs that this sandbox's user namespace cannot represent; descriptor-level ownership and cleanup tests pass independently.
- Binding-GID transaction, pod-local alias, and permission-bootstrap suites: `87 passed, 13 skipped`.
- Registry generation check and repository schema validation passed for all 36 entries.
- The standard repository unittest suite passed 43 of 44 tests. Its sole unrelated failure is the pre-existing `clawpod-video-studio` credential-free self-report returning status 12 in this environment.
- Unfiltered pytest collection is unavailable because the environment resolves three ClawPod Cloud Webhooks tests against an older installed `cli_anything` package. Loopback OAuth tests are unavailable because local socket binding is prohibited. Neither limitation exercises the modified protected-binding implementation.
