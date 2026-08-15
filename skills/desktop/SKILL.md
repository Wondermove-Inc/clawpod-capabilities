---
name: desktop
description: "Use for native apps or OS dialogs when no typed API or DOM fits. Observe and operate pointer/keyboard, windows/dialogs, or drag/drop; QA, verify, recover. Prefer Browser for DOM, nodes for remote screens, provider APIs for services."
---

# Desktop

Prefer Browser/Playwright for DOM work, node screen for an attached remote screen, and typed APIs for service operations. Compose Desktop only at native GUI handoffs.

## Workflow

1. Run `desktop environment.preflight --input '{}'` and stop on unavailable AT-SPI, D-Bus session, or backend state.
2. Observe before acting. Use accessibility targets first. Permit image fallback only when explicitly supported, and use digest-bound coordinates only as a last resort.
3. Bind precision actions to a fresh window, observed revision, target digest, and explicit read-only postcondition. Re-observe stale targets within the bounded policy, then stop rather than approximate.
4. Preview S2-S4 actions and obtain a fresh digest-bound approval. Never put secret values in arguments, previews, evidence, or task files.
5. Verify focus immediately before input. Dispatch click-like actions at most once per idempotency key, confirm their postcondition, and never replay an unknown outcome automatically.
6. Use bounded drag trajectories and deadlines. Stop on focus drift, target drift, unsupported fallback, missing postcondition, or uncertain effect.
7. Stop on CAPTCHA or human verification. Ask the human to complete it, then re-observe before resuming.
8. Report partial commits and unknown outcomes explicitly, then perform ownership-scoped cleanup.

Read [operations](references/operations.md) for command families and [safety](references/safety.md) before mutations.
