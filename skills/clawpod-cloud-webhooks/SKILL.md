---
name: clawpod-cloud-webhooks
description: Operate and diagnose ClawPod Cloud Webhooks Sources, Playbooks, Rules, Events, guarded mutations, and protected onboarding.
---

# ClawPod Cloud Webhooks

Use the paired `clawpod-cloud-webhooks` Harness for deterministic execution. Do not call the portal directly when the Harness covers the operation.

1. Start with `system.version` and `auth.contract`. Installation is not connection. Onboarding requires either a ClawPod Cloud TA account or an account with Webhook Manager permission. Confirm that prerequisite before login; if absent, stop and report it as a blocker. Before login, account access, cookie creation, secret injection, or any mutation, obtain explicit approval.
2. After approved login, run `auth.status` and read back the authenticated identity, selected tenant, and Webhooks permissions before declaring the capability connected. Then inspect presets, Sources, Playbooks, Rules, and recent Events. Always bind the tenant explicitly and preflight every target against it.
3. Use Source Playbooks only for provider-common interpretation and safety constraints. Use Rule Playbooks for event-specific workflow, evidence, and escalation. Warn when Source and Rule reference the same Playbook because delivery duplicates it.
4. Reject `in`, `not_in`, `gt`, `lt`, `gte`, `lte`, and non-empty `message_template`. Block agent targets unless destination-side evidence is required and available.
5. For every mutation, run `mutation.preview`, show the redacted intended diff and effect digest, obtain approval, then execute with the same digest and a stable idempotency key. Never infer approval from design or preview approval.
6. For Source updates, preserve the full mutable object from a fresh GET, PUT it, and verify a fresh GET. Stop on mismatch or partial failure. Never blindly retry a mutation.
7. Reject inbound test bodies over 1,048,576 bytes. Require a sender-stable request ID. A `received=true` response without `event_id` is not acceptance.
8. Verify Event status asynchronously. Treat any non-empty `error_message` as failure even when status says `delivered`. Require destination-side evidence when delivery matters.
9. Use `event.inspect-redacted`; never return raw cookies, authorization, signatures, URL tokens, signing secrets, or sensitive headers.
10. For rotate/regenerate, warn that prior credentials may remain valid, read back `previous_secret_expires_at`, and report overlap. Never print returned secret material.

Completion requires source-of-truth readback, redacted evidence, and explicit residual limitations. Current known limits are unproven agent delivery, broken comparison/set operators, ignored message templates, silent ingress drops above 1 MiB or for unknown/disabled Sources, throttled Events remaining `accepted`, and no concurrency FIFO guarantee.
