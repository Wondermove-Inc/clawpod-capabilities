# ClawPod Cloud Webhooks

CLI-Anything harness for guarded ClawPod Cloud Webhooks portal/API operations through a real bounded HTTP client.

## Safety contract

- Never prints authorization, cookies, URL tokens, signing secrets, provider signatures, or sensitive header values.
- The agent proactively asks for the base URL and non-secret account identifier/prerequisite. It never asks for or accepts a plaintext password/token in chat, searches protected secret pointers first, and stores newly supplied credentials through protected secret input/storage.
- `auth onboard --approve-login` performs the complete non-mutating sequence: protected credential injection, RSA-OAEP login, identity and tenant discovery, sole-tenant selection (or typed ambiguity), Webhook Manager permission verification, and process-memory-only session readback.
- Authenticated commands read `CLAWPOD_CLOUD_EMAIL` and `CLAWPOD_CLOUD_PASSWORD` only from protected process environment injection. The user is never asked to configure environment variables or run commands.
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

TLS verification is strict by default and HTTP base URLs are rejected. For an internal CA, prefer `--ca-cert /path/to/ca.pem`; the readable regular PEM is used only to construct this process's client SSL context and is never copied, persisted, or emitted. Only for an explicitly approved internal network, use both `--insecure-skip-tls-verify` and `--i-understand-insecure-tls-risk`. The flags disable certificate verification only, never HTTPS, cannot be combined with `--ca-cert`, and do not authorize login or mutation. Mutation preview and execution approvals remain separate.

`system version` and `auth contract` require no authentication. Every portal read or mutation fails clearly unless protected credential environment injection is present. Portal resources use the verified `/api/proxy/auth/*` and `/api/proxy/webhook-*` paths; auth setup uses `/api/auth/public-key`, `/api/auth/login`, `/api/auth/refresh`, and `/api/auth/logout`.

OpenClaw platform limitation: Gateway `harness.run` currently has command input plus approval-intent binding but no memory-secret injection field. Therefore authenticated onboarding and every later authenticated one-shot command use the approved `exec.useSecrets` execution lane to inject protected pointers into the installed CLI process. The agent reuses those pointers automatically; the user does not configure environment variables or repeat credentials. Secrets never enter chat, argv, files, or Harness input. This is not session persistence; each command uses a fresh process-memory session.

Use `mutation-preview` first. Supply its exact effect digest, stable idempotency key, and explicit `--approve` to `source-update`. Reads may retry bounded transient failures. Mutations are never blindly retried.

## Tests

```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/clawpod_cloud_webhooks/tests -v --tb=no
```

Tests use only a local mock HTTPS server with synthetic certificates and credentials. No live portal or secrets are accessed.
