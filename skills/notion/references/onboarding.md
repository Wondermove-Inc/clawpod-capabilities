# Minimal-intervention onboarding and recovery

Use `onboard.plan` first. It is read-only and must not create state or contact Notion. Prefer **Internal Integration** for team-owned automation; PAT is personal/development only. OAuth can automate planning and authorization navigation, but provider client registration, redirect configuration, exchange, refresh, and revoke require a separately configured client.

## Resumable flow

1. Get approval to begin the browser/desktop setup, then run `onboard.start` with the exact workspace, typed roots, computed minimum capabilities, state path, and approved adapter. The state file is mode 0600, revisioned, atomic, and secret-free.
2. The adapter may navigate and fill safe fields. It must stop with an exact handoff on login, MFA, CAPTCHA/human verification, workspace/root approval, final permission confirmation, or protected credential capture. It must never submit the final permission action unless that exact handoff is approved.
3. Resume with `onboard.resume --expected-revision N`; include only the handoff reasons approved for that checkpoint. A stale revision is rejected. Repeating `onboard.start` returns the active session without duplicate effects.
4. For `secret_capture_required`, the owner agent captures the value directly into protected secret storage. The capability never reads it from the page, screenshots it, accepts it as an argument, or writes/logs it. Resume using protected runtime `NOTION_TOKEN` injection.
5. When UI work reaches `verification_required`, run `auth.onboarding.verify` with the exact roots. Confirm `user.me` matches the approved workspace, retrieve every root, set the verified list as `allowedRoots`, and run a bounded read-only retrieve/search smoke. A 404 means wrong workspace, missing, or unshared root; a 403 means capability/workspace policy denial.
6. `onboard.status` and `onboard.inspect` are read-only. `onboard.cancel` discards local browser-task progress and records cleanup guidance. Timeout is explicit and restartable.

Browser/desktop adapters must expose deterministic task steps (`navigate`, `fill_safe_fields`, `select_workspace`, `configure_capabilities`, `connect_roots`) and handoff steps. Screens/DOM containing credential fields are excluded from state and audit. CAPTCHA always stops automation.

To revoke, revoke the integration/PAT in Notion, disconnect roots, delete the protected secret pointer, cancel remaining local state, then verify `auth.status` is disconnected.
