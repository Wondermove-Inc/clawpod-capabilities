# Mandatory post-install onboarding

Immediately after installation, report **installed but not connected** and ask for **Codex**, **Claude**, or **both**. If deferred, say “resume ACP Project Continuity onboarding” and do not claim readiness.

Explain which provider receives prompts, exact repository/cwd and permissions, likely side effects, revocation, and ACPX local named-session records. Obtain explicit approval before login/OAuth, credential use, provider prompting, mutation, rotation, or close. A read-only preflight may start an adapter to inspect capabilities.

- Codex: verify bundled ACPX, the Codex adapter, and provider-supported authentication.
- Claude: accept OAuth only into protected storage. Every authenticated command uses `exec.useSecrets` to inject `CLAUDE_CODE_OAUTH_TOKEN`; never Gateway Harness input or ordinary environment text.
- Both: connect and verify independently; never share identifiers or credentials.

Run `onboard`, register canonical git root/branch/full HEAD, then `acpx-preflight`. A provider is `verified` only after two bounded `session-run` invocations in separate OS processes reuse the deterministic ACPX name and lineage. No OpenClaw runtime change, Gateway callback, install, restart, or deployment is part of onboarding.
