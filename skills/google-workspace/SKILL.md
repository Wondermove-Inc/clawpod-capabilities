---
name: google-workspace
description: Operate Gmail, Google Calendar, Google Drive, and broad one-consent OAuth through the typed Google Workspace Harness. Use for mail, event, file, account, scope, and agent-local credential onboarding tasks.
---

# Google Workspace

Use the `google-workspace` Harness for Gmail v1, Calendar v3, Drive v3, and OAuth account work.

## First-use authorization gate

Before any credentialed operation, inspect whether the selected account alias already has a usable local credential. If not, stop and tell the user that Google login and permission grant are required; identify the intended account alias; explain that `workspace-max` requests Gmail and Gmail Settings, Calendar, Drive, and identity access; state that the agent's managed browser will open and that the resulting credential stays in that agent's protected local storage. Explain that these broad scopes do not authorize later sends, shares, deletes, invitations, or other side effects. Ask whether to start authorization now. Do not invoke `auth.login`, open the browser, or create credential state until the user explicitly agrees in the current conversation. Read `references/onboarding.md` and `references/scopes.md` before consent.

1. Identify the exact account alias. Never infer one when multiple aliases exist.
2. For a newly installed agent whose user approved onboarding, issue that agent's own credential on its managed desktop with `auth.login` and `workspace-max`.
3. Resolve opaque resource IDs before mutation. Never mutate by a human-readable name alone.
4. For any write, run `--dry-run` or preview first. Show target IDs, principals, notification behavior, recoverability, and the effect digest.
5. Obtain explicit approval for externally visible, destructive, credential, or admin effects. Invoke external/destructive work only with the fresh matching `--confirm` digest.
6. Preserve ETags with `--if-match`, sync/history/change tokens with their original query, and report partial or ambiguous commits exactly.
7. For mail replies, distinguish draft replacement from send. For recurring events, ask series versus instance. For Drive, distinguish trash from permanent delete and file content from native-file export.
8. Never put tokens, authorization codes, client secrets, bodies, attachment bytes, OAuth URLs, or credential paths in chat, logs, prompts, tests, or artifacts.
9. Return the Harness JSON result, confirmed effects, limitations, and recovery guidance.

Read `references/operations.md` for command families and ambiguity rules. Read `references/scopes.md` before consent. Read `references/onboarding.md` whenever an agent has no local credential.
