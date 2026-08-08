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

## Direct basic/PAT per-run binding

For direct basic/PAT sites only, keep site configuration secret-free with `emailRef: env:ATLASSIAN_EMAIL` and `tokenRef: env:ATLASSIAN_API_TOKEN`. Select authorized owner-scoped pointers and pass `{"secretRefs":{"ATLASSIAN_EMAIL":"msp_...","ATLASSIAN_API_TOKEN":"msp_..."}}` to `harness.run.prepare`, then pass the identical map to `harness.run`. Gateway resolves both only for that execution; shared manifests store no pointer or provider binding. Missing values fail closed. Do not apply this flow to OAuth 3LO: its client, private token bundle, refresh, detached worker, and auth-reuse lifecycle remain unchanged.
