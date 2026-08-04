# Mandatory post-install onboarding

Immediately after installing the linked Skill and Harness, state that the capability is **installed but not connected**. Ask the user to choose **Codex**, **Claude**, or **both**. If deferred, record connection as pending, provide the exact resume action (“resume ACP Project Continuity onboarding”), and do not claim operational readiness.

## 1. Explain the connection

Explain that the selected coding provider receives the project prompt and can read or modify files allowed by the ACP runtime. State the account/tenant, repository and cwd, permission profile, expected side effects, and how access can be revoked. Obtain explicit approval before opening login, starting OAuth, creating credential state, or using a stored credential.

## 2. Connect the selected provider

Perform safe local readiness checks first. Do not ask the user to repeat a credential that already exists in protected secret storage.

- **Codex:** check the Codex ACP adapter and existing vendor authentication. If absent, guide the provider-supported login/OAuth flow. Store no auth material in Harness state.
- **Claude:** check the Claude ACP adapter and existing Claude Code authentication. If an OAuth token is needed, accept it only through the protected memory-secret onboarding path, never a file, Harness argument, prompt artifact, log, or continuity state. Bind the resulting secret pointer to ACP at runtime as `env:CLAUDE_CODE_OAUTH_TOKEN` through `sessions_spawn(..., useSecrets:[...])`.
- **Both:** complete and verify each provider independently. Never reuse one provider’s session id or credential binding for the other.

Report three states separately for each provider: `installed`, `connected`, and `verified`. A successful Harness `onboard` records only the user’s provider selection; it does **not** prove vendor authentication.

## 3. Initialize local continuity state

Run Harness `status` through Gateway and verify `pureLocal`, `network: false`, `gatewayCalls: false`, `acpCalls: false`, and `vendorCalls: false`.

Create a private local state directory, then run Harness `onboard` with its absolute `stateRoot`, a state file beneath it, `expectedRevision: 0`, and exactly one mode:

- `codex`: manage only Codex lineages.
- `claude`: manage only Claude lineages.
- `both`: manage separate Codex and Claude lineages in the same project registry.

Onboarding is additive. A later CAS-protected onboarding can add the other agent. All project operations fail until onboarding is recorded, and agent operations fail when that agent was not onboarded.

## 4. Verify first run and resume

For each selected provider:

1. Register the exact project context and acquire a lease.
2. Start a bounded one-shot ACP run with `sessions_spawn(runtime:"acp", agentId:"codex"|"claude", mode:"run", thread:false, cwd:<exact cwd>)`; include only approved secret pointer bindings.
3. Attach the returned upstream session id.
4. Resolve it, then start a second bounded one-shot with the exact `resumeSessionId` and a deterministic continuity challenge.
5. Verify that the resumed turn recalls the challenge and still operates in the exact repo/cwd/branch. Record evidence, release the lease, and only then mark the provider `verified`.

If resume fails or the session is missing, stop and report it. Never silently fall back to a new session. Rotate only after an explicit recovery decision.

## 5. Rotate or revoke

Credential rotation updates the protected secret pointer through the approved secret lifecycle, then repeats the bounded provider verification. Revocation removes or disables the protected credential and closes the associated local lineages. Provider-side account revocation remains available through the provider’s account security controls.

Do not place onboarding in `WORKFLOW.md`; installation and onboarding must not modify that file.
