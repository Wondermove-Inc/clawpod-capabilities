---
name: desktop
description: "Use for native desktop, browser chrome, or OS-dialog GUI work: inspect accessible UI, operate pointer, keyboard, dialogs, or files, and verify with redacted evidence. Prefer Browser/Playwright, node screen, or typed APIs when applicable."
---

# Desktop

Prefer Browser/Playwright for DOM work, node screen for an attached remote screen, and typed APIs for service operations. Compose Desktop only at native GUI handoffs.

## Workflow

1. Run `desktop environment.preflight --input '{}'` and stop on unavailable AT-SPI or backend state.
2. Observe before acting. Prefer stable accessible targets over images or coordinates.
3. Preview S2-S4 actions and obtain a fresh digest-bound approval. Never put secret values in arguments, previews, evidence, or task files.
4. Execute bounded observe, act, verify steps with idempotency keys and expected revisions.
5. Stop on CAPTCHA or human verification. Ask the human to complete it, then re-observe before resuming.
6. Report partial commits and unknown outcomes explicitly, then perform ownership-scoped cleanup.

Read [operations](references/operations.md) for command families and [safety](references/safety.md) before mutations.
