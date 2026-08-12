# Direct credential per-run `secretRefs` migration matrix

Classification: **refine** the four existing paired capabilities. No new capability boundary is needed.

| Capability | Current direct credential contract | Per-run Gateway binding | Preserved path | Target paired version | Verification |
|---|---|---|---|---|---|
| Notion | `NOTION_TOKEN` environment; PAT/Internal Integration token never persisted | `{"secretRefs":{"NOTION_TOKEN":"msp_..."}}` identically on prepare and run | OAuth remains planning-only; onboarding state remains secret-free | 0.1.9 | Notion unit/onboarding tests, missing-token fail closed, metadata contract |
| Synology SMB Storage | `SYNOLOGY_SMB_PASSWORD` environment or Harness stdin; backend receives `PASSWD` only | `{"secretRefs":{"SYNOLOGY_SMB_PASSWORD":"msp_..."}}` identically on prepare and run | Existing-mount no-secret no-op, stdin compatibility, fixed SMB 3.1.1 controls | 0.1.4 | SMB tests, missing-password failure, backend redaction, metadata contract |
| ClawPod Cloud Webhooks | `CLAWPOD_CLOUD_EMAIL` and `CLAWPOD_CLOUD_PASSWORD` protected environment; fresh process-memory cookie session | identical two-entry `secretRefs` map on prepare and run | RSA-OAEP login, CookieJar session, TLS and mutation guards | 0.2.0 | full local HTTPS fixture suite, missing credentials failure, onboarding contract |
| Atlassian | Site config direct `basic` uses an email and token reference; OAuth uses file-backed refresh/access lifecycle | direct basic/PAT uses `ATLASSIAN_EMAIL` and `ATLASSIAN_API_TOKEN` in identical prepare/run `secretRefs`; site config contains only `env:` names | OAuth 3LO client, token bundle, refresh, worker, and auth reuse unchanged | 0.3.1 | Atlassian and async OAuth tests, direct auth positive/missing env, OAuth regression |

Shared manifests and package metadata contain environment names and binding semantics only. They contain no owner pointer ID and no static provider binding. Fresh agents select pointers authorized in their own owner scope. Plaintext credentials are never passed in Harness input, argv, ordinary files, prompts, logs, or reports.
