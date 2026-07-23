---
name: "github"
description: "Operate GitHub repositories, issues, pull requests, Actions runs, releases, and bounded API reads through the guarded GitHub CLI Harness."
---

# GitHub

Use the canonical `github` Harness. It wraps the real `gh` CLI. Do not construct ad hoc `gh` commands or arbitrary mutation API calls.

## Installation unit

Treat this Skill and the same-named Harness as one unit. Installation is incomplete until both artifacts are present, name/title aligned (`github` / `GitHub`), digest validated, Harness trusted, and a representative `prepare → run` read succeeds. Never call the Skill alone operational.

## Authorization gate

Immediately after installation validation, run `auth.status` for the exact host and expected account. If disconnected, say “installed but not connected,” explain the account/host, permission categories, protected `gh` credential storage, revocation, and future mutation approvals, then ask whether to start authorization. Do not use credentials or start consent without explicit approval.

After approval, use `auth.login.start`; return promptly while the user completes only provider-required sign-in, password, MFA, verification, and consent. Poll with `auth.login.status` outside the Gateway wait path. Never request, automate, display, or persist those values. Finish only after `auth.status --expected-account`, `repo.view`, and a bounded read succeed. Fail closed on host/account mismatch.

Read `references/operations.md` for command selection and `references/onboarding.md` for authorization and recovery.

## Operation

Use read commands freely after prepare. For every mutation, first run `--dry-run`, show the target and effect, obtain explicit approval, then use the exact `--confirm <command>`. Closing, merging, cancelling, and clobbering uploads are destructive. Never infer authorization from installation, trust, prior review, or read access.

Keep repository targets explicit. Use `api.get` only for its bounded GET allowlist. Never expose credentials or raw auth/config output.
