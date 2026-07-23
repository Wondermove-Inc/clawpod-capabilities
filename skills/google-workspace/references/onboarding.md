# Agent-desktop OAuth onboarding

Each installed agent must issue and store its own Google OAuth credential on that agent's managed desktop. Do not copy another agent's credential bundle or run the callback on a remote host.

1. Start or inspect the agent's OpenClaw-managed browser with the browser tool.
2. Read its loopback CDP/DevTools URL, for example a literal `http://127.0.0.1:<port>` endpoint.
3. Place the Google Desktop/installed-client JSON under a private transfer root as a regular mode-0600 file.
4. Run `auth.login` with a stable account alias, `workspace-max`, relative client/output paths, the local managed-browser DevTools URL, a maximum ten-minute timeout, and bounded Gmail/Calendar/Drive smoke tests.
5. The Harness opens consent in that agent's desktop browser, receives the callback on that same agent's `127.0.0.1`, validates PKCE/state/identity/scopes, and writes the credential bundle atomically at mode 0600.
6. Verify `auth.accounts.status`, identity, granted scopes, and sanitized smoke-test counts before provider work.

The Harness also accepts the local browser endpoint from `GOOGLE_WORKSPACE_MANAGED_BROWSER_DEVTOOLS_URL` or `OPENCLAW_BROWSER_CDP_URL`. Explicit command input wins. Only literal loopback HTTP endpoints are accepted.

Never ask the owner to copy an authorization URL, code, token, client secret, or credential file between agents. If no managed browser is available, stop with a browser-open error instead of moving consent to another machine.
