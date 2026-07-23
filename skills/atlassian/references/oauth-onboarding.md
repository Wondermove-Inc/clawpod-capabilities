# Agent-local Atlassian OAuth 2.0 (3LO)

Use one organization-managed, distributable Atlassian 3LO app. Atlassian explicitly advises integrations not to tell each customer or agent to create a separate 3LO app or API token.

## App prerequisite

In the Atlassian Developer Console, configure one OAuth 2.0 integration with Jira, Confluence, User Identity, and `offline_access` scopes needed by the Harness. Register one exact fixed callback URL:

`http://127.0.0.1:<fixed-port>/oauth/atlassian/callback`

The Developer Console must accept this exact callback. Atlassian requires `redirect_uri` to match the registered callback exactly and documents confidential authorization-code exchange with a client secret. Atlassian does not document PKCE for this flow, so the Harness does not invent PKCE parameters.

Distribute the shared app client configuration only through protected agent provisioning. Store it as a regular mode-0600 JSON file under a private transfer root. Its `oauth2` object contains the app client identifier, protected client secret, exact redirect URI, and an array of the configured Jira, Confluence, User Identity, and offline scopes. Never place real or credential-shaped example values in docs, prompts, chat, tests, logs, or ordinary config.

## Per-agent login

1. Start or inspect that agent's managed browser and obtain its literal loopback CDP/DevTools URL.
2. Run `auth.oauth.login` with a private transfer root, relative client/credential/site-config paths, a site alias, the expected `https://<tenant>.atlassian.net` resource URL, and the managed-browser endpoint.
3. The Harness binds only the exact registered `127.0.0.1` port and callback path, creates an unguessable state value, opens consent in that agent's browser, validates the callback, and exchanges the code without returning either value.
4. It retrieves `/me` and `accessible-resources`, selects the exact resource URL, writes the rotating credential bundle and site alias atomically at mode 0600, and runs bounded Jira/Confluence read-only smoke checks.
5. Verify `auth.oauth.status`. Refresh consumes a provider rotating token and changes local secret state, so preview `auth.oauth.refresh` and run it only with the matching fresh confirmation; it serializes concurrent refreshes and atomically replaces both tokens.

Never copy another agent's credential bundle, authorization URL, callback URL with code, or refresh token. OAuth scopes never replace the user's Jira/Confluence permissions and do not bypass mutation preview and confirmation.
