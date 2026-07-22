---
name: google-workspace
description: Route Gmail, Google Calendar, Google Drive, and Google OAuth account tasks through typed previews, least-privilege scopes, and the google-workspace CLI Harness.
---

# Google Workspace

Use this Skill for Gmail v1, Calendar v3, Drive v3, and local OAuth-account status work.

1. Identify the exact account alias. Never infer one when multiple aliases exist.
2. Choose the least-privilege scope profile from `references/scopes.md` and run `auth.scopes.check` when uncertain.
3. Resolve opaque resource IDs before mutation. Never mutate by a human-readable name alone.
4. For any write, run `--preview` first. Show target IDs, principals, notification behavior, recoverability, and the effect digest.
5. Obtain explicit approval for externally visible, destructive, credential, or admin effects. Invoke external/destructive work only with the fresh matching `--confirm` digest.
6. Use `--dry-run` to verify scopes and preconditions without mutation. Do not describe policy refusal as missing feature support.
7. Preserve ETags with `--if-match`, sync/history/change tokens with their original query, and report partial or ambiguous commits exactly.
8. For mail replies, distinguish draft replacement from send. For recurring events, ask series versus instance. For Drive, distinguish trash from permanent delete and file content from native-file export.
9. Never put tokens, authorization codes, client secrets, bodies, attachment bytes, or credential paths in chat, logs, or artifacts.
10. Run `auth.login` only on the account owner's PC with a Google Desktop/installed client JSON and explicit transfer-root-relative mode-0600 input/output paths. It uses a temporary `127.0.0.1` loopback receiver; never relay its browser URL through a remote host.
11. Return the harness JSON result, confirmed effects, limitations, and recovery guidance.

Read `references/operations.md` for command families and ambiguity rules. Read `references/scopes.md` before requesting consent or broad scopes.
