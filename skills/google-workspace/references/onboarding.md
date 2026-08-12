# Agent-complete Google OAuth onboarding

Each installed agent issues and stores its own Google OAuth credential on that agent's managed desktop. Never copy another agent's bundle or run its callback remotely. Google Console and Admin Console setup is browser-driven: do not claim API automation for these controls.

## User-facing preflight and immediate post-install handoff

Immediately after installation and validation, inspect whether the selected alias has a usable credential. If it does not, say that the capability is **installed but not yet connected**, identify the intended alias, explain `workspace-max`, the managed-browser consent flow, protected agent-local mode-0600 storage, revocation, and that later sends/shares/deletes still need approval. Ask: **“Start Google Workspace authorization now?”** Explain that this includes the durability setup, using the exact resume label **“Start Google Workspace authorization and durability setup now?”** Continue only after an explicit affirmative response in the current conversation. Do not open a browser, inspect private console state, invoke `auth.login`, or create credential state before that response.

Tell the owner that the agent will perform every automatable console step. The owner is needed only for Google login/MFA, legally meaningful final Publish/verification/admin approvals, and Google review. If deferred, record authorization as pending and give the exact resume action.

## 1. Inspect and choose the durable audience path

After approval, use the managed browser and the `desktop` skill to open Google Cloud Console, select the exact OAuth project, and inspect **Google Auth Platform → Audience**. Treat the rendered project name, user type, and publishing status as source of truth; capture sanitized evidence without client IDs, tokens, secrets, or user content.

- **External, Testing:** explain that refresh tokens can expire after seven days. Navigate to the In production transition, resolve all automatable prerequisites below, and prepare Publish. Stop immediately before the final legally meaningful **Publish app** confirmation, show the exact project/audience/effect, and obtain a fresh owner confirmation. After confirmation, click Publish and re-read Audience until **In production** is displayed. Publishing may trigger verification; it does not itself prove approval.
- **External, In production:** do not republish. Continue with Data Access verification and authorization.
- **Internal:** use this only when the selected project belongs to the owner's Google Workspace organization and all intended users are members. Confirm Audience displays **Internal**. Do not attempt external publishing; continue with Workspace Admin authorization where organization policy requires it. If any intended account is outside the organization, stop and ask whether to use an External project.

Stop for login/MFA rather than asking the owner to operate the remaining browser workflow.

## 2. Prepare External verification completely

Inspect **Google Auth Platform → Branding** and **Data Access**. Gmail and Drive `workspace-max` scopes can be sensitive or restricted. Read the console's current scope classifications and verification state rather than assuming them.

Before asking the owner for a final submission, prepare every automatable field and upload available evidence:

1. Verify app name, support/developer contacts, authorized domains, homepage, and a publicly reachable privacy-policy URL whose domain ownership is established.
2. Make declared scopes match actual `workspace-max` use. Remove unrelated scopes only if doing so does not change the requested Harness behavior.
3. Write concise per-scope justifications tied to Gmail/Gmail Settings, Calendar, Drive, and identity commands; explain least access, user benefit, storage, retention, and revocation.
4. Add only owner-approved test accounts and prepare reviewer steps that exercise representative Gmail, Calendar, and Drive reads without exposing user data.
5. Prepare sanitized demo/video or screenshots, architecture/data-handling evidence, and any restricted-scope security-assessment information the console requests. Never fabricate evidence or claim an assessment was completed.
6. Validate all URLs and fields in the rendered console, then show the exact submission effect and stop for the owner's final verification/submission approval.

After approval, submit. If Google review is pending, record the project, review state, latest verified timestamp, and next check in tracked work with a wake-guard. Do not block a Gateway call or repeatedly poll. Resume when review changes or at the scheduled check; report requests for more information exactly and prepare the response, again stopping for legally meaningful final submission.

## 3. Prepare Workspace Admin authorization

For organization-managed accounts, use the managed browser to open **Google Admin console → Security → Access and data control → API controls** (labels can vary). Inspect app access control, trusted/internal app settings, and domain policy for the exact OAuth client/project.

Prepare the narrow trusted-app or admin authorization required for the intended users and scopes. Show organization, client/project identity, affected users/OU/group, scopes, and policy effect. Stop before the final admin authorization or trust confirmation for owner/admin approval. Never claim domain-wide delegation, trusted-app status, or admin authorization unless the rendered Admin Console confirms it. If the signed-in owner is not an authorized admin, record the exact pending admin action and wait with a wake-guard.

## 4. Authorize each agent and verify

Only after the applicable audience, verification, and admin gates are confirmed:

1. Start/inspect that agent's OpenClaw-managed browser and obtain its literal loopback CDP URL.
2. Place Desktop/installed-client JSON under a private transfer root as a regular mode-0600 file.
3. Run the existing `auth.login` flow unchanged with a stable alias, `workspace-max`, relative client/output paths, local browser URL, at most ten minutes, and Gmail/Calendar/Drive smoke tests.
4. The owner performs only sign-in/MFA, account choice, consent review, and consent confirmation. The agent handles callback validation and storage.
5. Verify `auth.accounts.status`, identity, granted scopes, and sanitized Gmail, Calendar, and Drive smoke-test counts.
6. Repeat authorization and smoke tests separately for every agent. Never transfer credentials between agents.

Use typed `credentialPath` for later calls. Never echo the path. If a previous token was issued while External was Testing, reauthorize after production/approval rather than expecting the old refresh token to become durable.

## Failure and revocation

A sanitized `invalid_grant` refresh failure can mean Testing-mode seven-day expiry, user revocation, password/security changes, long inactivity, token limits, or an invalid/expired refresh token. Inspect Audience and account/admin state, then reauthorize the affected agent; never expose Google's response body. Revocation is available from the Google Account connections page and by removing the protected local bundle through the approved logout flow.

The browser endpoint may come from `GOOGLE_WORKSPACE_MANAGED_BROWSER_DEVTOOLS_URL` or `OPENCLAW_BROWSER_CDP_URL`; explicit typed input wins. Accept only literal loopback HTTP endpoints. Never ask the owner to copy an OAuth URL, code, token, client secret, or credential file.
