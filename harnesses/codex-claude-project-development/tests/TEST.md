# Codex & Claude Project Development test evidence

The core suite uses a deterministic fake ACPX executable and real temporary git repositories. It covers successful named-session ensure/prompt, repeat reuse, rotation, stable identifier/result recording, missing and old binaries, missing adapter capabilities, authentication failure, timeout, malformed JSON and identifiers, stale-lease recovery, branch/cwd/HEAD drift, and prompt/protocol/secret non-persistence. Existing state, permission, symlink, CAS, onboarding, and lineage validation remains fail closed.

The E2E suite installs the generated Registry pair into temporary roots and verifies the installed 0.2.1 Harness boundary and owner-only onboarding state. Repository tests validate synchronized package metadata and supported Gateway Harness schemas; the capability-registry core/E2E suites provide representative Gateway lifecycle validation. No live provider credentials or sessions are used by automated tests. The previously supplied live cross-process evidence remains external evidence: Codex `ACPX-CODEX-8462` and Claude `ACPX-CLAUDE-2741`.

Commands are reported in the completion summary.
