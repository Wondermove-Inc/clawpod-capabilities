# notion Harness

Stdlib-only typed wrapper for official Notion REST API 2026-03-11.

The current Gateway accepts structured values through scalar JSON-string fields. Full object/array contracts remain in `command_contracts.json`; `notion.py` parses and revalidates each JSON string. Regenerate both layers with `python3 scripts/update_notion_transport.py` from the repository root.

1. Run read-only `onboard.plan` without credentials.
2. Use an existing owner-only `outputRoot` and bounded relative `session`/`stateName`; traversal, symlinks, missing/public roots, and non-regular targets fail closed. State is atomic, mode 0600, revisioned, redacted, and resumable.
3. Run read-only `onboard.desktop.task`, resolve its approved placeholders, and pass it to the desktop layer. Verify between actions; stop for login/MFA, CAPTCHA, UI drift, exact workspace/root choice, final permission approval, and `secret_capture_required`. The owner agent stores the token through protected secret handling; the harness never scrapes or persists it.
4. Inject `NOTION_TOKEN` only at runtime, run `auth.onboarding.verify` with 1-50 typed roots, confirm workspace identity, and perform bounded root reads.
5. Reuse verified roots as `allowedRoots`. For writes, run `operation.plan`, then `--preview`, approve the exact intent hash, execute once, and inspect exact-resource verification.

Fixtures under `tests/fixtures` are deterministic adapter contracts and do not contact Notion. See `../../docs/notion-contract.md` for coverage, recovery, revocation, and residual limits.
