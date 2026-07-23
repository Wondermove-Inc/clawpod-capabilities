# Site configuration

Set `ATLASSIAN_SITES_FILE` or pass `--sites-file` to a JSON document:

```json
{"sites":{"work":{"baseUrl":"https://example.atlassian.net","auth":{"type":"basic","email":"user@example.com","tokenRef":"env:ATLASSIAN_TOKEN"}},"oauth":{"baseUrl":"https://api.atlassian.com/ex/confluence/cloud-id","auth":{"type":"oauth","tokenRef":"file:/protected/token"}}}}}
```

Only HTTPS origins are accepted. Secret values are resolved at invocation from environment variables or files with mode 0600 or stricter. Aliases isolate tenants and credentials. Do not place secret values in this file.
