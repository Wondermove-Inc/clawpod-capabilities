---
name: resend-email
description: "Use to onboard Resend, verify senders, preview messages, attach files, or deliver transactional email retry-safely; use Google Workspace for inbox management and Enterprise Newsletter to compose approved content."
---

# Resend Email

Use only the paired `resend-email` Harness (version 0.1.10). Never construct curl requests.

## Two ways to send

Resend always needs a sender (`from`) and recipients (`to`). Which sender you can use decides who you can reach:

| Mode | `from` | Reaches | When |
|---|---|---|---|
| **Domain** | any address at a domain verified in the user's Resend account (e.g. `notice@example.com`) | anyone | real use |
| **Test** | `onboarding@resend.dev` | only the Resend account owner's own email and test addresses (`delivered@`, `bounced@`, `complained@resend.dev`) | no verified domain yet, or a quick connection check |

Individual sender addresses are never registered; verifying the domain covers every address at it. The Harness checks domain verification before a domain-mode send and skips that check for `onboarding@resend.dev`. `sender.readiness`, `status`, and every send report `sender_mode`. A test-mode send to anyone else fails with `test_recipient_restricted`: tell the user to verify a sending domain in Resend (DNS work happens in Resend; this Harness does not change DNS).

## API key

The key reaches the Harness only through `RESEND_API_KEY` environment injection, never as an argument. When the user supplies a key in the Room or a message, route it immediately to owner-only `memory_secret` storage without echoing it, keep only safe pointer metadata, and treat the original message as sensitive. For every credentialed command, pass the same owner-authorized memory-secret pointer to both Gateway calls — `harness.run.prepare`, then `harness.run` with the matching intent hash:

```json
{"secretRefs":{"RESEND_API_KEY":"msp_..."}}
```

Never put the plaintext key in config JSON, arguments, ordinary files, normal memory, reports, prompts, or logs, and never reuse another agent's pointer. Room delivery alone does not mean the key is compromised and does not require revocation; rotate only on provider revocation or another independent compromise signal.

## Onboarding

Right after installation, report **installed but not connected** and run `onboarding`. Once the key is stored:

1. Run `verify`, then `domains.list`.
2. **A verified domain exists:** ask which sender address to use (any address at that domain), then run `onboarding.test` with that sender and the owner's own address.
   **No verified domain:** run `onboarding.test --from onboarding@resend.dev --to delivered@resend.dev` — no question to the user. Report that the account is connected in test mode and can reach only the owner's own address until a domain is verified.
3. Report that Resend **accepted** the test for submission; inbox delivery is not confirmed.

`onboarding.test` needs a private absolute `--state` path and is idempotent. The state stores only acceptance, message ID, timestamp, sender domain, and a recipient hash. `status --state <path>` reports `installed_but_unconnected`, `connected_not_verified`, or `onboarding_complete`, plus `sender_mode` and `can_send_to_anyone`.

Single send, bulk send, attachments, and any recipient domain are always available. Never ask the owner for send limits, recipient-domain allowlists, or permission toggles.

## Sending

1. Pick the sender per the mode table, then run `send` (single) or `bulk.send` (per-recipient) directly — no per-send approval. Use `preview` or `--dry-run` only when the user asks to review first.
2. Report provider IDs, idempotency keys, and `sender_mode`. Submission is not delivery.

Bulk deduplicates addresses, rejects CC/BCC, bounds concurrency and rate, honors `Retry-After`, and gives each recipient a stable idempotency key. On partial failure, retry only the failed recipients with their returned keys. Never report message bodies, attachment bytes, or keys.

On 429 wait `retry_after_seconds`; on transport or 5xx errors retry with the same idempotency key. `sender_not_ready`, `test_recipient_restricted`, `unauthorized`, and `provider_rejected` need the cause fixed, not a retry.
