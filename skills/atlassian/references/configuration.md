# Site configuration

Set `ATLASSIAN_SITES_FILE` or pass `--sites-file` to a mode-0600 JSON document:

```json
{"sites":{"work":{"baseUrl":"https://example.atlassian.net","auth":{"type":"basic","email":"user@example.com","tokenRef":"env:ATLASSIAN_TOKEN"}},"oauth":{"jiraBaseUrl":"https://api.atlassian.com/ex/jira/cloud-id","confluenceBaseUrl":"https://api.atlassian.com/ex/confluence/cloud-id","auth":{"type":"oauth","tokenRef":"file:/protected/oauth-bundle.json"}}}}}
```

Only HTTPS service origins are accepted. Secret values are resolved at invocation from environment variables or files with mode 0600. An OAuth file may be the protected rotating 3LO bundle created by `auth.oauth.login`; the Harness resolves only its current access token and never emits bundle contents.

OAuth cloud routing uses separate Jira and Confluence `api.atlassian.com/ex/.../{cloudId}` origins. Aliases isolate tenants and credentials. Never place secret values in the site document.

For first-time issuance, read `oauth-onboarding.md`. Each agent must perform consent in its own managed browser and must not copy another agent's credential or authorization callback.
