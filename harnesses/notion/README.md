# notion Harness

Stdlib-only typed wrapper for official Notion REST API 2026-03-11.

1. Run `auth.status` and `auth.onboarding.plan` without credentials.
2. After explicit approval, inject `NOTION_TOKEN` through protected runtime secret handling.
3. Run `auth.onboarding.verify` with 1-50 typed roots.
4. Reuse those roots as `allowedRoots` for writes.
5. Run `operation.plan`, then `--preview`, approve the exact intent hash, execute once, and inspect verification.

Credentials are never accepted as CLI arguments or persisted. See `../../docs/notion-contract.md` for coverage and residual limits.
