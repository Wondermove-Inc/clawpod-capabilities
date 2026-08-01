# Minimal-intervention onboarding and recovery

Use `onboard.plan` first. It is read-only and must not create state or contact Notion. Prefer **Internal Integration** for team-owned automation; PAT is personal/development only. OAuth can automate planning and authorization navigation, but provider client registration, redirect configuration, exchange, refresh, and revoke require a separately configured client.

## Resumable flow

1. Provision an existing owner-only (0700) `stateRoot`. Run `onboard.start` with bounded relative `session`/`stateName`, the exact workspace, typed roots, and computed minimum capabilities. The Harness rejects traversal, symlinks, missing/public roots, and non-regular targets; state files are atomic mode 0600 and secret-free.
2. Run read-only `onboard.desktop.task` and pass its returned task contract to the approved desktop layer. Resolve `${workspace}`, `${capabilities}`, and `${roots}` from the approved plan. The desktop layer may navigate and fill safe fields, verifying page identity and non-secret values after every action. It must stop with the exact handoff on login, MFA, CAPTCHA/human verification, workspace/root approval, UI drift, final permission confirmation, or protected credential capture. Never submit the final permission/root action unless that exact handoff is approved. Provider selectors are not live-validated.
3. Resume with `onboard.resume --expected-revision N`; include only the handoff reasons approved for that checkpoint. A stale revision is rejected. Repeating `onboard.start` returns the active session without duplicate effects.
4. For `secret_capture_required`, the owner agent captures the value directly into protected secret storage. The capability never reads it from the page, screenshots it, accepts it as an argument, or writes/logs it. Resume using protected runtime `NOTION_TOKEN` injection.
5. When UI work reaches `verification_required`, run `auth.onboarding.verify` with the exact roots. Confirm `user.me` matches the approved workspace, retrieve every root, set the verified list as `allowedRoots`, and run a bounded read-only retrieve/search smoke. A 404 means wrong workspace, missing, or unshared root; a 403 means capability/workspace policy denial.
6. `onboard.status` and `onboard.inspect` are read-only. `onboard.cancel` discards local browser-task progress and records cleanup guidance. Timeout is explicit and restartable.

On each desktop handoff, call `onboard.status`, obtain the exact user approval if applicable, then call `onboard.resume` with the current revision and only the approved handoff reason. On `ui_drift`, stop and report the last verified step plus visible non-secret labels; do not guess selectors. Screens, DOM, credential fields, cookies, and tokens are excluded from task output, state, and audit. CAPTCHA always stops automation. Fixture injection is test-only and unavailable through the production manifest.

To revoke, revoke the integration/PAT in Notion, disconnect roots, delete the protected secret pointer, cancel remaining local state, then verify `auth.status` is disconnected.
