# Command selection

## OAuth and sites

`auth.oauth.login` performs one agent-local managed-browser 3LO consent and writes a protected rotating credential plus site alias. `auth.oauth.status` reports only sanitized metadata. `auth.oauth.refresh` atomically rotates both access and refresh tokens. `auth.sites.list` and `auth.whoami` inspect configured aliases and identity. Read `oauth-onboarding.md` before login.

## Jira

`jira.issues.search|get|create|update|delete`, `jira.issues.transitions.list`, `jira.issues.transition`, `jira.issues.comments.list|create|update|delete`, `jira.issues.attachments.add`, and `jira.projects.list|get` use Jira Cloud REST API v3.

## Confluence

`confluence.pages.list|get|create|update|delete`, `confluence.spaces.list|get`, and `confluence.attachments.list` use REST API v2. `confluence.search` and `confluence.attachments.add` use v1 because v2 does not provide equivalent functionality.

Pass query values as a JSON object to `--params`, request documents to `--body`, and path identifiers with their typed flags. Every mutation requires dry-run and a matching fresh confirmation digest.
