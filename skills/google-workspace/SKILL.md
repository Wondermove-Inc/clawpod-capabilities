---
name: google-workspace
description: Operate Gmail, Google Calendar, Google Drive, and broad one-consent OAuth through the typed Google Workspace Harness. Use for mail, event, file, account, scope, and agent-local credential onboarding tasks.
---

# Google Workspace

Use the `google-workspace` Harness for Gmail v1, Calendar v3, Drive v3, and OAuth account work.

1. Identify the exact account alias. Never infer one when multiple aliases exist.
2. For a newly installed agent, issue that agent's own credential on its managed desktop. Read `references/onboarding.md` and use `auth.login` with `workspace-max`.
3. Resolve opaque resource IDs before mutation. Never mutate by a human-readable name alone.
4. For any write, run `--dry-run` or preview first. Show target IDs, principals, notification behavior, recoverability, and the effect digest.
5. Obtain explicit approval for externally visible, destructive, credential, or admin effects. Invoke external/destructive work only with the fresh matching `--confirm` digest.
6. Preserve ETags with `--if-match`, sync/history/change tokens with their original query, and report partial or ambiguous commits exactly.
7. For mail replies, distinguish draft replacement from send. For recurring events, ask series versus instance. For Drive, distinguish trash from permanent delete and file content from native-file export.
8. Never put tokens, authorization codes, client secrets, bodies, attachment bytes, OAuth URLs, or credential paths in chat, logs, prompts, tests, or artifacts.
9. Return the Harness JSON result, confirmed effects, limitations, and recovery guidance.

Read `references/operations.md` for command families and ambiguity rules. Read `references/scopes.md` before consent. Read `references/onboarding.md` whenever an agent has no local credential.
