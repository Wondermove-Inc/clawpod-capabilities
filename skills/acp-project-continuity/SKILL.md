---
name: acp-project-continuity
description: Maintain project-level Codex or Claude continuity with bundled ACPX named persistent sessions, canonical git validation, leases, rotation, protected secrets, and fail-closed recovery. Use when work must continue across separate OS processes without OpenClaw runtime changes.
---

# ACP Project Continuity

Use the paired Harness as the only continuity-state writer and bundled ACPX named sessions as the only continuity backend. There is no Gateway callback and no `sessions_spawn` dependency.

## Required workflow

1. Immediately after installing, read [onboarding.md](references/onboarding.md). Obtain explicit approval for provider connection, protected credential use, and requested file/tool side effects. `onboard` records selection, not authentication.
2. Resolve the canonical git top-level, current branch, and full `HEAD`; register their exact absolute repo/cwd context. Stop on detached HEAD, cwd/root mismatch, or drift.
3. Run `acpx-preflight` against the bundled executable. Require ACPX 0.3.1 or newer and adapter `loadSession`, `resume`, `list`, and `close` support.
4. Invoke `session-run` directly in a bounded exec, supplying the prompt only on stdin. It leases, derives the project-agent-generation name, runs strict-JSON `sessions ensure --name`, then a separate `prompt --session ... --file -`, returns the assembled agent response, records only identifiers/completion metadata, and releases. Repeats reuse the name; `--rotate` advances generation.
5. For Claude, use approved `exec.useSecrets` injection for `CLAUDE_CODE_OAUTH_TOKEN` when required. Never resolve, persist, print, or put it in argv, a prompt, Harness input, state, or logs.
6. Re-read after `stale_revision`. Never bypass an active lease. Use `session-close` only with explicit approval because it terminates the named ACPX session.

Read [safety.md](references/safety.md) before execution. Read [shared-storage.md](references/shared-storage.md) only for an explicitly requested non-sensitive handoff.

Stop on missing/old ACPX, missing capability, auth failure, timeout, malformed JSON, incomplete identifiers, context drift, corruption, unsafe permissions, secret-like state, lease conflict, or stale revision. Never copy ACPX output/prompts into state or silently choose another session.
