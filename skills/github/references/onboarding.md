# GitHub onboarding prerequisite

Version 0.1 requires the system `gh` CLI to be authenticated before this capability is used. Login is intentionally outside the Harness because a safe, agent-complete browser handoff is not yet implemented.

The human operator uses GitHub's supported `gh auth login` flow, handles sign-in, password, MFA, verification, and consent, and relies on `gh` protected credential storage. The agent never receives or records tokens or one-time codes. Then verify with Harness `auth.status --host <exact-host> --expected-account <exact-login>`.

If verification fails, report the capability as installed but not connected. Revoke access using GitHub account settings or `gh auth logout` outside this capability. Each future mutation still requires preview and explicit approval.
