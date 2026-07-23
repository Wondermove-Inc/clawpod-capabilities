---
name: "github"
description: "Operate GitHub repositories, issues, pull requests, Actions runs, releases, and bounded API reads through the guarded GitHub CLI Harness."
---

# GitHub

Use the canonical `github` Harness. It wraps the real `gh` CLI. Do not construct ad hoc `gh` commands or arbitrary mutation API calls.

## Installation unit

Treat this Skill and the same-named, same-title Harness (`github` / `GitHub`) as one transactional unit. Registry installation, update, and validation of this Skill must use explicit Skill and Harness roots, verify both manifests and digests, and roll back both on partial failure. The capability is incomplete if either artifact is absent or invalid.

## Onboarding prerequisite

Version 0.1 does not automate GitHub login. Before use, the operator must authenticate the system `gh` CLI outside this capability using GitHub's supported login flow and protected credential storage. Never request, display, persist, or log tokens or one-time authorization codes.

After that human-controlled prerequisite, run `auth.status` with the exact host and expected account. It performs only a bounded `GET user` query and returns allowlisted `host`, `login`, and `authenticated` fields. Fail closed on host or exact account mismatch. If disconnected, report “installed but not connected,” explain that pre-authenticated `gh` is required, and provide the provider's revocation path. Do not claim agent-complete onboarding.

Read `references/operations.md` for command selection and `references/onboarding.md` for prerequisites and recovery.

## Operation

Use read commands only after the authentication check. For every mutation, first run `--dry-run`, show the exact target and effect, obtain explicit approval, then use exact `--confirm <command>`. Mutations are never retried because backend commit may be ambiguous. Closing, merging, cancelling, and clobbering release uploads are destructive. Local idempotency keys are not proof of provider-side idempotency.

Keep repository targets explicit. Use `api.get` only for its bounded GET allowlist. Never expose credentials or raw auth/config output.
