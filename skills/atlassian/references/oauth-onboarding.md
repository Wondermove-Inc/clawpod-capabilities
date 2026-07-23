# Agent-local Atlassian OAuth 2.0 (3LO)

## Handoff and approval

If no usable credential exists, say the capability is installed but not connected. Explain what the user controls: account sign-in and any password or MFA entry. Explain what the agent controls after that login: exact-site selection, displayed-scope verification, the final consent click, callback validation, protected storage, resource selection, and read-only verification. State that access is scoped, revocable, and does not authorize later mutations.

Ask, "Start Atlassian authorization now?" Continue only after an explicit affirmative response in the current conversation. Never expose authorization URLs, codes, client secrets, tokens, or credential-file contents.

## Keep Gateway responsive

Long-running Gateway executions are prohibited. Never increase Gateway or Harness execution timeouts to wait for OAuth consent, browser interaction, human input, or external work. Keep Gateway lifecycle calls short and bounded. Run the consent wait in an approved background executor that does not occupy Gateway, record a wake-guard, and resume on completion.

## Preflight

1. Confirm the OAuth app callback exactly matches the Harness loopback callback.
2. Verify required scopes by their saved scope codes, not by clicks or an unsaved editor state.
3. For the Confluence v2 spaces endpoint, include granular `read:space:confluence`; classic `read:confluence-space.summary` alone can return `401 Unauthorized; scope does not match`.
4. Use relative OAuth file names beneath `transferRoot`. Do not pass absolute credential paths when the Harness enforces private relative paths.
5. Immediately before authorization, verify `transferRoot` is owner-controlled with no group/other permission bits and OAuth input files are mode `0600`. Shared-volume defaults can reintroduce group permissions.
6. Keep client, token, site, and temporary diagnostic files distinct. Reject symlinks and path escapes.

## Consent and resource selection

Open the managed browser and request only configured scopes. The user handles sign-in, passwords, and MFA only. The initial explicit authorization approval covers the agent selecting the exact intended site, verifying the displayed permission categories against the requested scope codes, and pressing the final consent button. Do not ask the user to press Allow again. Never type credentials or complete MFA. If the site or displayed scope state is missing, mismatched, or ambiguous, fail closed before consent.

After token exchange, Atlassian may return separate Jira and Confluence accessible-resource records with the same cloud ID. Coalesce records by cloud ID and union their scopes before matching. Prefer an exact cloud ID or site URL, then an exact normalized site alias/name. A sole coalesced resource is safe. If multiple coalesced resources remain ambiguous, fail closed and inspect only sanitized candidate metadata stored in an owner-only temporary file; never guess. Remove temporary diagnostics after selection.

Require the granted token scopes to contain every requested scope. If scopes are added after a failed verification, save them in the developer console, update the protected client configuration, and re-consent.

## Protected persistence

Persist the reusable token bundle and site alias atomically with mode `0600`. Keep parent directories owner-controlled. Never print, log, attach, or message credential values. Verify the stored site alias and non-expired OAuth status without exposing account details.

## Read-only completion checks

Run all of the following with strict bounds and no mutations:

1. `auth.oauth.status`
2. `auth.sites.list`
3. `auth.whoami`
4. `jira.projects.list` with `maxResults=1`
5. `confluence.spaces.list` with `limit=1`

Also verify Jira and Confluence smoke tests, if provided, both report success. Record command names, success status, file modes, and limitations as evidence. Do not report onboarding complete until every check succeeds.

## Failure handling

- Relative-path rejection: fix the Harness contract or pass relative names under `transferRoot`; do not weaken private-path validation.
- Permission rejection: restore owner-only directory and mode-`0600` file permissions, then retry safely.
- `scope does not match`: add the endpoint's documented granular scope and re-consent.
- Duplicate resources: coalesce identical cloud IDs before ambiguity checks.
- Multiple distinct resources: stop and require an exact cloud ID or sanitized owner selection.
- Consent timeout: stop the background wait and restart a fresh authorization; never extend Gateway timeout.
- Partial storage failure: roll back both token and site files before retrying.
