# GitHub Harness

Canonical `github` / **GitHub** Harness. It invokes the real `gh` executable and emits one stable, bounded JSON envelope. Diagnostics are bounded and redacted.

## Contract

Read commands cover safe auth identity, repositories, issues, pull requests/checks, workflow runs/logs, releases, and allowlisted API GET. `auth.status` invokes only `gh api --hostname <validated-host> --method GET user --jq '{login:.login}'`, returns allowlisted fields, and compares the expected account exactly. It never invokes `gh auth status` or requests token-bearing fields.

Mutations cover issue/PR actions, run rerun/cancel, and release create/upload. They require `--dry-run`, current approval, and exact `--confirm <command>`. They are never retried because backend commit may be ambiguous. Release upload preview discloses `--clobber` behavior.

Version 0.1 requires a pre-authenticated system `gh` CLI. Login commands are intentionally absent until a safe agent-complete browser handoff can be proven. The Harness never reads credential/config files, authorization codes, or tokens.
