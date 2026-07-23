---
name: atlassian
description: Operate Jira Cloud and Confluence Cloud through typed, approval-gated commands. Use for issue, project, workflow, comment, page, space, search, or attachment work across configured Atlassian sites.
---

# Atlassian

Use the `atlassian` harness, never construct ad hoc REST calls.

## Post-install and first-use authorization gate

Immediately after this capability is installed and validated, inspect whether a usable site and credential already exist. If authorization is missing, do not report it as ready for use. Tell the user it is installed but not yet connected; explain the planned Atlassian onboarding, which tenant and Jira/Confluence permission categories are requested, what the user must do, what the agent will do, that the managed browser will open, and that the resulting credential stays in that agent's protected local storage and can be revoked. Ask whether to start authorization now. Apply the same gate before later credentialed use if onboarding is still pending. Do not invoke `auth.oauth.login`, open the browser, or create credential files until the user explicitly agrees in the current conversation. Follow `references/oauth-onboarding.md` for the exact notice and flow.

1. Identify the site alias and intended Jira or Confluence operation.
2. If the agent has no credential and the user approved onboarding, use the organization-managed 3LO app so that agent grants access in its own managed browser and stores its own rotating credential locally.
3. Inspect first with a read command. Read `references/commands.md` when selecting a command.
4. For every mutation, run the exact command with `--dry-run`, review its redacted request, then obtain explicit approval and rerun unchanged with the returned `--confirm` digest within five minutes.
5. Treat credential use, human-account actions, and external effects as approval-gated. Never request, print, or persist plaintext credentials.
6. For attachments, use a narrow `--transfer-root`; reject path traversal and symlinks.
7. If `ambiguousCommit` is true, inspect provider state before retrying. Use an idempotency key where the workflow supports one.
8. Report the typed envelope, effects, provider error code, and audit provenance.

Site configuration contains aliases, HTTPS base URLs, and only `env:` or mode-0600 `file:` credential references. See `references/configuration.md`.
