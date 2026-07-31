# GitHub Harness

Canonical `github` / **GitHub** Harness. It invokes the real `gh` executable and emits one stable, bounded JSON envelope. Diagnostics are bounded and redacted.

## Contract

Read commands cover safe auth identity, repositories, issues, pull requests/checks, workflow runs/logs, releases, and allowlisted API GET. `auth.status` invokes only `gh api --hostname <validated-host> --method GET user --jq '{login:.login}'`, returns allowlisted fields, and compares the expected account exactly. It never invokes `gh auth status` or requests token-bearing fields.

Mutations cover issue/PR actions, run rerun/cancel, release create/upload, and guarded existing-release body updates. They require `--dry-run`, current approval, and exact `--confirm <command>`. They are never retried because backend commit may be ambiguous. Release upload preview discloses `--clobber` behavior.

`release.body.update` first reads `repos/{owner}/{repo}/releases/tags/{exact-tag}` and snapshots all returned metadata except `body`, `updated_at`, and `assets`, with the complete assets array protected separately. Its dry run shows the exact body change and numeric release endpoint. On confirmation it performs one `PATCH repos/{owner}/{repo}/releases/{numeric-id}` with stdin JSON containing only the `body` key, then performs an independent GET by numeric id. It reports success only when the body matches exactly and protected metadata and assets remain identical. Verification failure is fail-closed with `ambiguousCommit:true`; the mutation is never retried.

Version 0.1 requires a pre-authenticated system `gh` CLI. Login commands are intentionally absent until a safe agent-complete browser handoff can be proven. The Harness never reads credential/config files, authorization codes, or tokens.
