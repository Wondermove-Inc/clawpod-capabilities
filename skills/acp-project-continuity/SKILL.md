---
name: acp-project-continuity
description: Maintain pure-local, project-level ACP session continuity for Codex, Claude, or both with mandatory onboarding, exact repo/cwd/branch validation, separate lineages, leases, rotation, close, and fail-closed state defenses. Use when an agent must safely attach, resume, validate, rotate, or close a local ACP session without network or Gateway calls.
---

# ACP Project Continuity

Use the paired Harness as the only writer for continuity state. Invoke it through the approved Gateway `prepare → run` lifecycle; the Harness backend itself remains pure local and never calls Gateway, ACP, a vendor, or the network.

## Required workflow

1. Immediately after installing the pair, read [onboarding.md](references/onboarding.md). Ask the user to choose **Codex**, **Claude**, or **both**, complete provider connection and protected credential setup, then run Harness `onboard` for the same selection. Distinguish `installed`, `connected`, and `verified`; do not claim readiness before a bounded first-run and resume test passes.
2. Derive an explicit absolute workspace root, repository, cwd, current branch, state root, and state file. Run `project-register` with the current revision. Never infer a different project when validation fails.
3. Before starting first-run work, acquire a bounded lease. Start the provider only with first-class `sessions_spawn(runtime:"acp", mode:"run", thread:false)`. After it starts, attach only its non-secret upstream session id. Keep Codex and Claude in separate lineages.
4. Before resuming, run `session-resolve` with the same project, repo, cwd, branch, and agent. Pass `resumeSessionId` only to a new first-class one-shot ACP spawn. Run `session-validate` on the observed id. Missing, failed, or mismatched resume is a stop condition; never silently create or select another session.
5. Use compare-and-swap `expectedRevision` for every write. Re-read after `stale_revision`; do not replay an obsolete decision. Use `session-rotate` only after an explicit recovery decision and `session-close` when finished. Release leases promptly; close also removes that agent's lease.

Read [safety.md](references/safety.md) before choosing state paths or handling runtime values. Read [shared-storage.md](references/shared-storage.md) only when optional cross-machine handoff is requested.

## Failure handling

Stop on corruption, secret-like material, unsafe permissions, symlinks, context mismatch, lease conflict, stale revision, missing onboarding, or missing lineage. Preserve the evidence and ask for explicit recovery direction. Never edit the JSON state manually.
