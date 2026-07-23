# ClawPod Capability Registry test evidence

Validated locally without network, installation into live roots, publication, or credentials.

## Coverage

- Explicit type selection and same-id ambiguity rejection.
- Standalone Skill and Harness install, validation, update, and rollback.
- Typed linked Harness metadata with independent exact Harness version.
- Linked Skill plus Harness transactional install and validation using explicit roots.
- Digest mismatch and partial-failure rollback.
- Blocked linked install when either root is absent.
- Harness entrypoint executable mode and provenance secret-field exclusion.
- Deterministic local list and not-found behavior without canonical-registry network access.
- Repository synchronization enforces exact linked Harness existence for every currently paired Skill, including pairs whose Skill and Harness versions differ.

## Commands

See the repository and GitHub Harness `TEST.md` evidence for the final focused/full suite commands and counts. All tests use temporary roots and mocked payloads; no capability is installed into live agent state.
