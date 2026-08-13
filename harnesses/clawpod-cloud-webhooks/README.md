# ClawPod Cloud Webhooks

Version 0.2.6 adds `lifecycle.execute`, a bounded plan command for full lifecycle workflows without per-command relogin. It accepts 1 to 30 allowlisted steps (maximum 131072 JSON bytes), logs in exactly once, and reuses one in-memory CookieJar. No cookie or session is persisted. Each mutation retains independent approval, stable idempotency, and exact effect-digest verification. Safe scalar references use `$steps.<name>.readback.id`; arbitrary evaluation is not supported. Execution stops on first failure and reports redacted completed work, uncertain state, and only resources created by this plan as cleanup-required. Cleanup must be explicitly planned and approved.

Rule payload evidence uses numeric `source_id`, `playbook_id`, and `target_room_ids` values. Playbook activation remains unsupported.

CLI-Anything harness for guarded ClawPod Cloud Webhooks portal/API operations through a real bounded HTTP client.

## Safety contract

- Never prints authorization, cookies, URL tokens, signing secrets, provider signatures, or sensitive header values.
- The agent proactively asks for the base URL and non-secret account identifier/prerequisite. It never asks for or accepts a plaintext password/token in chat, searches protected secret pointers first, and stores newly supplied credentials through protected secret input/storage.
- `auth onboard --approve-login` performs the complete non-mutating sequence: protected credential injection, RSA-OAEP login, legacy or current identity and tenant discovery, conservative tenant selection (or typed ambiguity), tenant-admin or Webhook Manager policy verification with legacy permission fallback, and process-memory-only session readback.
- Authenticated commands read `CLAWPOD_CLOUD_EMAIL` and `CLAWPOD_CLOUD_PASSWORD` only from protected process environment injection. The user is never asked to configure environment variables or run commands.
- Rejects inbound bodies above 1,048,576 bytes.
- Requires stable idempotency and effect-digest approval for mutations.
- Source, Playbook, and Rule creates and full-object updates GET-verify typed fields; deletes verify authoritative-list absence.
- Source/Rule enable/disable and Rule reorder use full-object update/readback. Playbook activation is unsupported because authoritative item readback exposes no activation field. Source rotate/regenerate use the evidenced action routes and redact returned secrets.
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

Authenticated onboarding and every later authenticated one-shot Gateway command use identical owner-scoped `secretRefs` maps for prepare and run. The agent reuses those pointers automatically; the user does not configure environment variables or repeat credentials. Secrets never enter chat, argv, files, or Harness input. This is not session persistence; each command uses a fresh process-memory session.

Use `mutation-preview --action create|update|delete|action` first. Supply its exact effect digest, stable idempotency key, and explicit `--approve` to the matching typed command. The full surface is `source|playbook|rule create|get|list|update|delete`, enable/disable for Sources and Rules, `rule-reorder`, `source-rotate-secret`, and `source-regenerate`. Event evidence supports only list/get, redacted inspection, and verification; no replay/retry/delete route is invented. Reads may retry bounded transient failures. Mutations are never blindly retried.

## Tests

```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/clawpod_cloud_webhooks/tests -v --tb=no
```

Tests use only a local mock HTTPS server with synthetic certificates and credentials. No live portal or secrets are accessed.

Per-run Gateway credential contract: select owner-authorized pointers and pass the identical `secretRefs` environment-name map to prepare and run. Expected environment: `CLAWPOD_CLOUD_EMAIL and CLAWPOD_CLOUD_PASSWORD`. The shared Harness stores no pointer/provider binding and fails closed when a required direct credential is unavailable.
