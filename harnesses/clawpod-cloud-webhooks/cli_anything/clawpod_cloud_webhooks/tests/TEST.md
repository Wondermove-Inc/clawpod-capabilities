# ClawPod Cloud Webhooks Test Plan

Written before test code and implementation. All backend tests use a local mock HTTP server; live portal access and real secrets are prohibited.

## Inventory

- `test_core.py`: 19 unit tests planned.
- `test_full_e2e.py`: 11 mock-backend and installed-subprocess tests planned.

## Unit plan

- `core/safety.py`: recursive redaction of sensitive names, cookies, authorization, signatures, URL tokens, and secret-like URLs; deterministic effect digests; 1 MiB exact boundary/overflow; unsupported operators and `message_template`; agent-target proof guard (9).
- `core/contracts.py`: mutation preview typing, stable idempotency requirement, Source full-object merge/preservation, tenant/target preflight, event terminal interpretation with non-empty error failure, rotation/regeneration lifecycle warnings (7).
- `utils/backend.py`: retry classification, bounded timeout validation, auth contract shape (3).

Edge cases include malformed JSON, empty idempotency, unknown mutable fields, cross-tenant targets, `delivered` plus error, and overlap expiry retained after regeneration.

## E2E plan

A local threaded HTTP backend simulates portal/API contracts without credentials:

1. Read workflow: version, permissions, presets, Source, Playbook, Rule, and Event typed reads.
2. RSA-OAEP login contract discovery and protected cookie-session status without exposing cookie data.
3. Read-before-write Source update: GET full Source, preview digest, PUT full preserved object, GET verification.
4. Mutation idempotency: matching preview digest and idempotency key are mandatory.
5. Event inspection recursively redacts sensitive headers and URL-token paths.
6. Event verification rejects non-empty errors even when backend says delivered.
7. Auth failure returns deterministic redacted error.
8. Backend 503 retries safe reads, then succeeds.
9. Timeout has bounded deterministic failure and mutation is not blindly retried.
10. Partial update/read-back mismatch is reported failed with retry-safety metadata.
11. Installed subprocess path executes `system version --json` and malformed input exits nonzero with JSON error.

## Realistic workflow scenarios

### Safely update a Source

- Simulates: changing activation while preserving nullable Playbook configuration.
- Operations: tenant preflight, GET current Source, merge allowed change, preview effect digest, execute full PUT, read back.
- Verifies: unchanged fields survive, digest binds intent, mismatch/partial failure is explicit.

### Diagnose webhook delivery

- Simulates: inspecting a credential-bearing Event after sender delivery.
- Operations: fetch Event, redact recursively, verify status/error/destination evidence.
- Verifies: no sensitive value or URL token is emitted; delivered-with-error fails.

### Prepare secret lifecycle action

- Simulates: rotation/regeneration planning without using a real secret.
- Operations: preview guarded mutation, execute against mock, read expiry metadata.
- Verifies: outputs never contain returned secret material and warn that previous credentials can remain valid.

## Output checks

Every command emits one stable JSON object on stdout in JSON mode, errors use typed codes, key ordering is deterministic, sensitive substrings are absent, network calls have bounded timeout/retry behavior, and subprocess tests run from outside the source directory.

## Test Results

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /workspace/harnesses/clawpod-cloud-webhooks
plugins: anyio-4.14.2
collecting ... collected 37 items

cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_redacts_headers_recursively PASSED [  2%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_redacts_url_token PASSED [  5%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_redacts_bearer_in_string PASSED [  8%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_digest_deterministic PASSED [ 10%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_payload_exact_cap PASSED [ 13%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_payload_over_cap PASSED [ 16%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_broken_operators_rejected[gt] PASSED [ 18%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_broken_operators_rejected[gte] PASSED [ 21%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_broken_operators_rejected[in] PASSED [ 24%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_broken_operators_rejected[lt] PASSED [ 27%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_broken_operators_rejected[lte] PASSED [ 29%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_broken_operators_rejected[not_in] PASSED [ 32%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_template_rejected PASSED [ 35%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_agent_target_requires_proof PASSED [ 37%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_idempotency_required PASSED [ 40%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_source_full_merge_preserves_nullable PASSED [ 43%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_source_unknown_field_rejected PASSED [ 45%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_tenant_preflight_rejects_target PASSED [ 48%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_preview_has_approval_and_digest PASSED [ 51%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_delivered_with_error_fails PASSED [ 54%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_destination_proof_required PASSED [ 56%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_secret_warning_retains_expiry PASSED [ 59%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_timeout_bounds PASSED [ 62%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_rsa_contract PASSED [ 64%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_backend_retries_get PASSED [ 67%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_auth_failure_typed_and_no_body_leak PASSED [ 70%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_bounded_timeout_and_retry_safety PASSED [ 72%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_subprocess_version_from_outside PASSED [ 75%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_typed_reads PASSED [ 78%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_auth_contract PASSED [ 81%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_auth_status_cookie_safe PASSED [ 83%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_event_redaction PASSED [ 86%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_event_error_fails PASSED [ 89%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_malformed_input_json_error PASSED [ 91%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_broken_feature_guard PASSED [ 94%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_source_read_before_write_and_partial_detection PASSED [ 97%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_secret_warning_redacted PASSED [100%]

============================== 37 passed in 1.64s ==============================
```

## Summary

37/37 passed (100%) in 1.64 seconds using the installed subprocess path and local mock HTTP backend. No live portal or secrets were used.

## Coverage notes

Mock coverage includes reads, malformed input, auth failure, bounded timeout, safe-read retry, partial mutation verification failure, recursive redaction, unsupported feature guards, protected session status, and secret lifecycle warnings. Live TLS, portal endpoint drift, and destination-side agent delivery remain intentionally untested.

## Remediation Test Results (2026-07-28)

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /workspace/harnesses/clawpod-cloud-webhooks
plugins: anyio-4.14.2
collecting ... collected 40 items

cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_redacts_headers_recursively PASSED [  2%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_redacts_url_token PASSED [  5%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_redacts_bearer_in_string PASSED [  7%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_digest_deterministic PASSED [ 10%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_payload_exact_cap PASSED [ 12%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_payload_over_cap PASSED [ 15%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_broken_operators_rejected[gt] PASSED [ 17%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_broken_operators_rejected[gte] PASSED [ 20%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_broken_operators_rejected[in] PASSED [ 22%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_broken_operators_rejected[lt] PASSED [ 25%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_broken_operators_rejected[lte] PASSED [ 27%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_broken_operators_rejected[not_in] PASSED [ 30%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_template_rejected PASSED [ 32%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_agent_target_requires_proof PASSED [ 35%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_idempotency_required PASSED [ 37%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_source_full_merge_preserves_nullable PASSED [ 40%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_source_unknown_field_rejected PASSED [ 42%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_tenant_preflight_rejects_target PASSED [ 45%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_preview_has_approval_and_digest PASSED [ 47%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_delivered_with_error_fails PASSED [ 50%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_destination_proof_required PASSED [ 52%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_secret_warning_retains_expiry PASSED [ 55%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_timeout_bounds PASSED [ 57%]
cli_anything/clawpod_cloud_webhooks/tests/test_core.py::test_rsa_contract PASSED [ 60%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_backend_retries_get PASSED [ 62%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_auth_failure_typed_and_no_body_leak PASSED [ 65%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_bounded_timeout_and_retry_safety PASSED [ 67%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_subprocess_version_from_outside PASSED [ 70%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_typed_reads PASSED [ 72%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_auth_contract PASSED [ 75%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_rsa_login_and_real_proxy_paths PASSED [ 77%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_missing_protected_env_fails_but_no_auth_commands_work PASSED [ 80%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_auth_status_cookie_safe PASSED [ 82%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_event_redaction PASSED [ 85%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_event_error_fails PASSED [ 87%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_malformed_input_json_error PASSED [ 90%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_broken_feature_guard PASSED [ 92%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_source_read_before_write_and_partial_detection PASSED [ 95%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_secret_warning_redacted PASSED [ 97%]
cli_anything/clawpod_cloud_webhooks/tests/test_full_e2e.py::test_manifest_adapter_command_parity PASSED [100%]

============================== 40 passed in 2.04s ==============================
```

40/40 passed (100%) in 2.04 seconds. Added synthetic RSA-OAEP login/decryption, verified proxy path, missing protected environment, no-auth command, manifest schema/argMap, adapter parity, and secret warning mapping coverage. Gateway lifecycle validation/trust and live portal access were intentionally not run; parent owns those steps.

## Internal-network TLS Results (0.1.5)

The isolated installed candidate's full Harness suite passed **63/63**. Local synthetic HTTPS coverage verifies strict self-signed rejection, custom-CA trust, doubly affirmed insecure TLS, pre-network approval and input failures, HTTP rejection, path/secret redaction, and existing onboarding identity/tenant/permission/no-mutation behavior. Repository and registry verification is recorded in the package-level `TEST.md`. No live portal or real secret was used.
