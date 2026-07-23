---
name: "atlassian"
description: "Operate Jira, Confluence, and resilient agent-local Atlassian OAuth 3LO through a guarded CLI Harness."
---

# Atlassian

Use the `atlassian` Harness. Never construct ad hoc Jira, Confluence, OAuth, or accessible-resources REST calls.

## Authorization gate

Immediately after installation and validation, inspect whether a usable site and credential exist. If not, say the capability is installed but not connected. Explain the tenant, permission categories, managed-browser handoff, protected local storage, revocation, and separate approval required for later mutations. Ask whether to start authorization. Do not open login, use credentials, or create credential state without explicit approval in the current conversation.

Follow `references/oauth-onboarding.md` for every first authorization, repair, or re-consent.

## Operation

Prefer typed read commands. Preview every mutation and require the matching confirmation. Never expose credentials, authorization URLs, codes, client secrets, tokens, or sensitive provider data.

Treat onboarding as complete only after non-expired OAuth status, site discovery, identity verification, one bounded Jira project read, and one bounded Confluence space read all succeed. Do not substitute successful consent or token exchange for end-to-end verification.
