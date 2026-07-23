# GitHub Harness

Canonical `github` / **GitHub** Harness. It invokes the real `gh` executable and emits one stable JSON envelope on stdout. Diagnostics are redacted on stderr.

## Contract

Read commands cover auth status, repositories, issues, pull requests/checks, workflow runs/logs, releases, and allowlisted API GET. Mutations cover issue/PR actions, run rerun/cancel, and release create/upload. Mutations require `--dry-run`, current approval, and `--confirm <command>`; they are never automatically retried.

Authorization is asynchronous: approved `auth.login.start` launches the provider flow and returns a job ID promptly; `auth.login.status` checks it without occupying the Gateway. Humans enter passwords, MFA, verification, and consent only in GitHub's flow. The Harness does not read credential/config files.

Run tests with `python3 -m pytest harnesses/github/tests -q`. No live credentials or network are used. Real-backend verification is approval-gated and documented in `TEST.md`.
