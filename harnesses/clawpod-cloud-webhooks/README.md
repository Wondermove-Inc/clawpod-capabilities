# ClawPod Cloud Webhooks

CLI-Anything harness for guarded ClawPod Cloud Webhooks portal/API operations through a real bounded HTTP client.

## Safety contract

- Never prints authorization, cookies, URL tokens, signing secrets, provider signatures, or sensitive header values.
- Authenticated one-shot commands read `CLAWPOD_CLOUD_EMAIL` and `CLAWPOD_CLOUD_PASSWORD` only from protected environment injection, fetch `/api/auth/public-key`, encrypt `{password,timestamp}` with RSA-OAEP/SHA-256, POST `/api/auth/login`, and retain cookies only in process memory. Credentials are never persisted, printed, or logged. Login/credential use requires explicit approval.
- Rejects inbound bodies above 1,048,576 bytes.
- Requires stable idempotency and effect-digest approval for mutations.
- Source update always GETs the full object, PUTs preserved mutable fields, then GET-verifies.
- Rejects `in`, `not_in`, `gt`, `lt`, `gte`, `lte`, and `message_template` until backend fixes are proven.
- Blocks agent targets without destination-evidence requirements.
- Treats any non-empty Event `error_message` as failure.
- Rotation/regeneration warnings state that prior credentials may remain valid.

## Install and use

```bash
pip install -e .
cli-anything-clawpod-cloud-webhooks --json system version
cli-anything-clawpod-cloud-webhooks --base-url https://portal.example --json source list --tenant-id TENANT
```

`system version` and `auth contract` require no authentication. Every portal read or mutation fails clearly unless protected credential environment injection is present. Portal resources use the verified `/api/proxy/auth/*` and `/api/proxy/webhook-*` paths; auth setup uses `/api/auth/public-key`, `/api/auth/login`, `/api/auth/refresh`, and `/api/auth/logout`.

Use `mutation-preview` first. Supply its exact effect digest, stable idempotency key, and explicit `--approve` to `source-update`. Reads may retry bounded transient failures. Mutations are never blindly retried.

## Tests

```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/clawpod_cloud_webhooks/tests -v --tb=no
```

Tests use only a local mock HTTP server. No live portal or secrets are accessed.
