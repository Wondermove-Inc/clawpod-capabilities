---
name: atlassian
description: Operate Jira Cloud and Confluence Cloud through typed, approval-gated commands. Use for issue, project, workflow, comment, page, space, search, or attachment work across configured Atlassian sites.
---

# Atlassian Cloud

Use the `atlassian` harness, never construct ad hoc REST calls.

1. Identify the site alias and intended Jira or Confluence operation.
2. Inspect first with a read command. Read `references/commands.md` when selecting a command.
3. For every mutation, run the exact command with `--dry-run`, review its redacted request, then obtain explicit approval and rerun unchanged with the returned `--confirm` digest within five minutes.
4. Treat credential use, human-account actions, and external effects as approval-gated. Never request, print, or persist plaintext credentials.
5. For attachments, use a narrow `--transfer-root`; reject path traversal and symlinks.
6. If `ambiguousCommit` is true, inspect provider state before retrying. Use an idempotency key where the workflow supports one.
7. Report the typed envelope, effects, provider error code, and audit provenance.

Site configuration contains aliases, HTTPS base URLs, and only `env:` or mode-0600 `file:` credential references. See `references/configuration.md`.
