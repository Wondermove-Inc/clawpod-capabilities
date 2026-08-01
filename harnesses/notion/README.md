# notion Harness

Stdlib-only typed wrapper for official Notion REST API 2026-03-11.

1. Run read-only `onboard.plan` without credentials.
2. After approval, use `onboard.start/status/resume/cancel` with exact workspace, roots, minimum capabilities, and a browser/desktop adapter. State is atomic, mode 0600, revisioned, redacted, and resumable.
3. Stop for login/MFA, CAPTCHA, exact workspace/root choice, final permission approval, and `secret_capture_required`. The owner agent stores the token through protected secret handling; the harness never scrapes or persists it.
4. Inject `NOTION_TOKEN` only at runtime, run `auth.onboarding.verify` with 1-50 typed roots, confirm workspace identity, and perform bounded root reads.
5. Reuse verified roots as `allowedRoots`. For writes, run `operation.plan`, then `--preview`, approve the exact intent hash, execute once, and inspect exact-resource verification.

Fixtures under `tests/fixtures` are deterministic adapter contracts and do not contact Notion. See `../../docs/notion-contract.md` for coverage, recovery, revocation, and residual limits.
