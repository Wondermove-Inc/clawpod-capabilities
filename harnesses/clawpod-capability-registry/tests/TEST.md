# Test Plan

## Inventory

- `test_core.py`: registry selection, path safety, digest validation, installation, update, and rollback unit tests.
- `test_full_e2e.py`: subprocess JSON behavior and real canonical-registry read test.

## Unit Coverage

- Reject non-canonical network URLs.
- Select latest compatible registry entry and exact versions.
- Reject unsafe relative paths and malformed file manifests.
- Install declared files only after SHA-256 verification.
- Reject duplicate installation.
- Detect modified installed files.
- Update with a local backup.
- Roll back to the previous local version.

## End-to-End Coverage

- Invoke the entrypoint through subprocess and verify JSON success and error envelopes.
- Fetch the real public canonical registry and verify its repository identity and schema.
- Confirm the installed CLI Harness lifecycle can discover and run read-only commands.

## Safety Checks

- No credentials are required or stored.
- Network access is restricted to the canonical raw GitHub path.
- Package paths cannot escape the explicit target root.
- Updates preserve a rollback backup before replacement.

## Test Results

```text
test_core.py: 6 tests passed
- canonical source restriction
- version selection
- path traversal rejection
- install/validate/update/rollback workflow
- modified-file detection
- provenance secret-field check

test_full_e2e.py: 2 tests passed
- real canonical registry list through subprocess
- structured JSON not-found failure through subprocess
```

Total: 8 tests, 100% passed. The end-to-end read test uses the real public GitHub backend. Write-path tests use temporary local directories and deterministic mocked package payloads.
