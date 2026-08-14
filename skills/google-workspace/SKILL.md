---
name: google-workspace
description: "Use to onboard Google OAuth and manage supported Gmail mail, Calendar events and ACLs, or Drive files, permissions, comments, and shared drives; it is not Outlook or generic web automation and can feed Enterprise Newsletter."
---

# Google Workspace

Use the `google-workspace` Harness for Gmail v1, Calendar v3, Drive v3, and OAuth account work.

## Post-install and first-use authorization gate

Immediately after this capability is installed and validated, inspect whether the selected account alias already has a usable local credential. If not, do not report it as ready for use. Tell the user it is installed but not yet connected; explain the planned Google Workspace onboarding, the intended account alias, that `workspace-max` requests Gmail and Gmail Settings, Calendar, Drive, and identity access, what the user must do, what the agent will do, that the managed browser will open, protected local credential storage, and revocation. Explain that these broad scopes do not authorize later sends, shares, deletes, invitations, or other side effects. Ask whether to start authorization now. Apply the same gate before later credentialed use if onboarding is deferred. Do not invoke `auth.login`, open the browser, or create credential state until the user explicitly agrees in the current conversation. Read `references/onboarding.md` and `references/scopes.md` before consent. After approval, use `auth.onboarding.decide` to apply the audience rule, then execute the agent-complete Google Console durability runbook: inspect Audience, handle Internal versus External, prepare production publishing and scope verification, prepare Workspace Admin API Controls authorization, and stop only at login/MFA, final legal/admin confirmations, or Google review. Track pending review with a wake-guard; after approval reauthorize every agent and verify configured audience, account membership/domain, granted scopes, and Gmail, Calendar, and Drive smoke tests.

1. Identify the exact account alias. Never infer one when multiple aliases exist.
2. For a newly installed agent whose user approved onboarding, issue that agent's own credential on its managed desktop with `auth.login` and `workspace-max`. Login binds the requested short alias by default in protected pod-local state outside the replaceable packages. For later authenticated commands, pass the alias with `account`; explicit typed `credentialPath` remains the highest-precedence compatibility path. Never infer an alias when multiple bindings exist.
3. Resolve opaque resource IDs before mutation. Never mutate by a human-readable name alone.
4. For any write, run `--dry-run` or preview first. Show target IDs, principals, notification behavior, recoverability, and the effect digest.
5. Obtain explicit approval for externally visible, destructive, credential, or admin effects. Invoke external/destructive work only with the fresh matching `--confirm` digest.
6. Preserve ETags with `--if-match`, sync/history/change tokens with their original query, and report partial or ambiguous commits exactly.
7. For mail replies, distinguish draft replacement from send. For recurring events, ask series versus instance. For Drive, distinguish trash from permanent delete and file content from native-file export.
8. Never put tokens, authorization codes, client secrets, bodies, attachment bytes, OAuth URLs, or credential paths in chat, logs, free-form prompts, tests, or artifacts. A credential path may be supplied only through the Harness's typed `credentialPath` field and must never be echoed.
9. Return the Harness JSON result, confirmed effects, limitations, and recovery guidance.

Use `auth.bindings.list|status|resolve` for sanitized inspection. Import and migration are explicit preview/confirm operations and never delete legacy files. Rename/remove/permission repair also require a fresh matching effect digest; credential deletion is separate and explicit. On package rollback to 0.2.6, select the referenced credential with typed `credentialPath` because that executable cannot resolve registry aliases. Package install, update, uninstall, and rollback must never recursively touch the protected binding root.

When binding status reports permission defects, run `auth.bindings.permissions.repair --dry-run` before attempting alias resolution or credential use. Show only its opaque artifact IDs, exact current/intended modes, and effect digest. Confirm only the fresh matching digest. This operation is mode-only: it may repair process-UID-owned, chain-GID-pinned, contained, single-link files and owned protected directories to `0600`/`0700`; it never reads credentials, migrates bindings, follows links, changes ownership, or touches the exact trusted Forge `02777/02775/02775/02775` ancestor chain. Treat any unsafe type, owner/group/link/containment defect, stale snapshot, or unavailable no-follow chmod primitive as a closed failure requiring manual investigation.

Read `references/operations.md` for command families and ambiguity rules. Read `references/scopes.md` before consent. Read `references/onboarding.md` whenever an agent has no local credential.
