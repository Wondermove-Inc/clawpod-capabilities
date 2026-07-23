# Atlassian CLI Harness

Dependency-free typed Jira and Confluence commands, guarded mutations, and agent-local OAuth 3LO.

## Asynchronous OAuth onboarding

The preferred Gateway-safe flow is `auth.oauth.start`. It validates inputs, creates a private job, starts a detached worker, and returns immediately with only a random job ID and relative status path. The worker is bounded by `workerTimeout` (5 to 600 seconds, default 300).

```sh
./atlassian.py auth.oauth.start \
  --transfer-root /private/root --client-path oauth-client.json \
  --output-path token.json --sites-output-path sites.json \
  --site-alias example --resource-url https://example.atlassian.net \
  --managed-browser-devtools-url http://127.0.0.1:9222

./atlassian.py auth.oauth.job.status \
  --transfer-root /private/root --job-id JOB_ID
```

Status is one of `pending-login`, `pending-consent`, `completed`, or `failed`. Status documents never contain authorization URLs, codes, client credentials, tokens, cookies, or callback state.

The worker opens the managed Chromium endpoint. It observes login and MFA pages but never types into them. After the user finishes account login, it verifies the exact approved site, callback, state, and every requested scope code, selects the site when needed, and presses Accept. It then validates the loopback callback, token scopes, identity, and a single unambiguous cloud resource. Duplicate accessible-resource rows with the same cloud ID are coalesced and their scopes unioned. Distinct cloud IDs fail closed.

Site approval is based only on a uniquely selected/displayed site marker, never
generic body text or hidden options. If none is selected, the driver opens a
native or Atlaskit selector, chooses one exact hostname match, waits for the UI
to settle, and re-reads the selected marker before accepting. Missing,
unsettled, or multiple matches fail closed.

Atlassian abbreviates scope codes in consent UI. The CDP driver therefore uses
a closed mapping, not substring guessing. The live client scope set maps to the
observed tokens `me`, `jira-user`, `jira-work`, `confluence-content.all`,
`confluence-space.summary`, `confluence`, `confluence-content`,
`confluence-file`, and `spaces`. Only `offline_access` is intentionally excluded
because Atlassian does not render it. Any unmapped scope or absent mapped token
fails closed.

The loopback fake-provider seam is unavailable through Harness arguments. It
requires both the unmistakable process-level `ATLASSIAN_INTERNAL_TEST_MODE=1`
flag and a private mode-0600 config path under `transferRoot`; the worker also
rejects non-loopback provider origins. Residual risk: a process owner who can
set both environment values can opt a worker into synthetic consent, so these
variables must never be present in a production Gateway environment.

Token and site files are atomically written mode 0600 only after bounded Jira identity and Confluence v2 space smoke tests succeed. Confluence v2 grants must include `read:space:confluence`. Temporary job configuration and resource diagnostics are removed. The legacy bounded blocking `auth.oauth.login`, credential `auth.oauth.status`, and all existing commands remain available.

### Limits

Atlassian may change consent-page markup or wording. The driver intentionally fails rather than guessing when site or Accept controls are missing or ambiguous. The managed Chromium endpoint and OAuth callback must be loopback-only, and the registered callback must exactly match the client file.
