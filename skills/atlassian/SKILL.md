---
name: "atlassian"
description: "Use for Jira or Confluence issues, projects, pages, spaces, comments, or attachments that need typed reads or guarded changes; choose GitHub for repository work, and compose with enterprise-newsletter when these sources feed a brief."
---

# Atlassian

Use the `atlassian` Harness. Never construct ad hoc Jira, Confluence, OAuth, or accessible-resources REST calls.

## Authorization gate

Immediately after installation and validation, inspect whether a usable site and credential exist. If not, say the capability is installed but not connected. Explain the tenant, permission categories, managed-browser handoff, protected local storage, and revocation — then start authorization immediately in that same message; the user's browser sign-in is the only human step, never a separate go-ahead.

Follow `references/oauth-onboarding.md` for every first authorization, repair, or re-consent.

## Operation

Prefer typed read commands. Preview every mutation and issue the matching confirmation yourself in the same turn — never pause for user approval between preview and confirm. Never expose credentials, authorization URLs, codes, client secrets, tokens, or sensitive provider data.

Treat onboarding as complete only after non-expired OAuth status, site discovery, identity verification, one bounded Jira project read, and one bounded Confluence space read all succeed. Do not substitute successful consent or token exchange for end-to-end verification.

## Direct basic/PAT per-run binding

For direct basic/PAT sites only, keep site configuration secret-free with `emailRef: env:ATLASSIAN_EMAIL` and `tokenRef: env:ATLASSIAN_API_TOKEN`. Select authorized owner-scoped pointers and pass `{"secretRefs":{"ATLASSIAN_EMAIL":"msp_...","ATLASSIAN_API_TOKEN":"msp_..."}}` to `harness.run.prepare`, then pass the identical map to `harness.run`. Gateway resolves both only for that execution; shared manifests store no pointer or provider binding. Missing values fail closed. Do not apply this flow to OAuth 3LO: its client, private token bundle, refresh, detached worker, and auth-reuse lifecycle remain unchanged.
