# GitHub onboarding

1. Verify both package digests, Harness validation/trust, `gh` presence, and canonical name/title.
2. Run bounded `auth.status` for the intended host and expected account. Do not read credential/config files.
3. If disconnected, explain: the user completes GitHub sign-in/password/MFA/verification/consent; the agent handles preflight, exact host/account checks, asynchronous status, verification, and cleanup; `gh` protects credential state; revoke with GitHub settings or approved `gh auth logout` outside this v1 Harness.
4. Ask explicit permission to begin. Use `auth.login.start --dry-run`, then approved start. Never keep a Gateway call waiting for consent.
5. Check `auth.login.status`; once finished, verify `auth.status --expected-account`, `repo.view`, then one bounded issue or PR list.
6. On wrong host/account or insufficient access, stop. Re-consent or logout requires separate credential-related approval.
