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

## Calling the Harness

Call the Harness through the `cli_harness` tool: `{"action":"harness.run.prepare","name":"atlassian","command":"<command>","input":{...}}`, then the identical call with `"action":"harness.run"` and the returned `approvalIntentHash`. Each line below is `<command>  <input>`, where `command` is the manifest key. `site` is the configured site alias. `params` (query string) and `body` (request body) are JSON **strings** in the Jira Cloud v3 / Confluence Cloud v2 field names. A write is `dryRun: true` first, then the same input with `confirm` set to the returned digest, chained in the same turn.

```text
jira.issues.search  {"site":"work","params":"{\"jql\":\"project = OPS AND statusCategory != Done ORDER BY updated DESC\",\"fields\":\"summary,status,assignee\",\"maxResults\":20}"}
jira.issues.get  {"site":"work","issueIdOrKey":"OPS-123","params":"{\"fields\":\"summary,status,description,comment\"}"}
jira.issues.create  {"site":"work","body":"{\"fields\":{\"project\":{\"key\":\"OPS\"},\"issuetype\":{\"name\":\"Task\"},\"summary\":\"배포 체크리스트 정리\"}}","dryRun":true}
jira.issues.comments.create  {"site":"work","issueIdOrKey":"OPS-123","body":"{\"body\":{\"type\":\"doc\",\"version\":1,\"content\":[{\"type\":\"paragraph\",\"content\":[{\"type\":\"text\",\"text\":\"확인했습니다.\"}]}]}}","dryRun":true}
confluence.pages.get  {"site":"work","pageId":"123456","params":"{\"body-format\":\"storage\"}"}
confluence.pages.create  {"site":"work","body":"{\"spaceId\":\"98765\",\"status\":\"current\",\"title\":\"주간 보고\",\"body\":{\"representation\":\"storage\",\"value\":\"<p>요약</p>\"}}","dryRun":true}
```

- Jira text fields such as comment and description bodies use Atlassian Document Format (`{"type":"doc","version":1,"content":[...]}`). Search uses `jql` with `fields` and `maxResults`; continue with the returned `nextPageToken`.

## Direct basic/PAT per-run binding

For direct basic/PAT sites only, keep site configuration secret-free with `emailRef: env:ATLASSIAN_EMAIL` and `tokenRef: env:ATLASSIAN_API_TOKEN`. Select authorized owner-scoped pointers and pass `{"secretRefs":{"ATLASSIAN_EMAIL":"msp_...","ATLASSIAN_API_TOKEN":"msp_..."}}` to `harness.run.prepare`, then pass the identical map to `harness.run`. Gateway resolves both only for that execution; shared manifests store no pointer or provider binding. Missing values fail closed. Do not apply this flow to OAuth 3LO: its client, private token bundle, refresh, detached worker, and auth-reuse lifecycle remain unchanged.
