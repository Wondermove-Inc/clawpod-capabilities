---
name: resend-email
description: "Use to onboard Resend, verify senders, preview messages, attach files, or deliver transactional email retry-safely; use Google Workspace for inbox management and Enterprise Newsletter to compose approved content."
---

# Resend Email

Use only the paired `resend-email` Harness (version 0.1.7). Never construct curl requests. The Harness accepts the key only through protected `RESEND_API_KEY` environment injection, never as an argument.

## First use and onboarding

Immediately after installation report **installed but not connected** and run the secret-free `onboarding` command. A user may supply a Resend key in the Room or a message. Route it immediately to owner-only `memory_secret` storage without echoing, quoting, repeating, or logging it, and retain only safe pointer metadata.

For every credentialed command, select an owner-authorized memory-secret pointer from the injected safe secret catalog. Pass the identical mapping to both Gateway calls:

```json
{"secretRefs":{"RESEND_API_KEY":"msp_..."}}
```

Run `harness.run.prepare` first, then `harness.run` with the matching intent hash and the same `secretRefs` map. Gateway resolves the pointer in the calling agent's owner scope and injects the value only for that run. Never copy another independent agent's pointer, put a pointer in the shared Harness manifest, or put the plaintext key in config JSON, arguments, ordinary files, normal memory, reports, prompts, or logs. Do not claim connectivity until this exact Gateway `prepare → run` verification succeeds.

After secret capture, treat the original message as sensitive: do not quote or forward it. Room delivery alone does not mean the key is compromised and does not require revocation. If provider revocation or another independent compromise signal is indicated, rotate the key.

Run `verify`, then run `sender.readiness` with the intended sender address. Do not call the account ready until the credential verifies and the intended sender domain reports `verified`. Only after both checks succeed, ask for exactly one onboarding test-recipient email address and run `onboarding.test` with the intended sender and a private state path. Never ask for domains, limits, permission toggles, or message content during onboarding. A domain may require DNS work in Resend; this Harness reports readiness but does not alter DNS. There is no private standing-policy file to configure.

`onboarding.test` first rechecks sender-domain readiness, then submits exactly one fixed, clearly labeled minimal test message with stable idempotency. Report that Resend accepted the message for submission and explicitly say inbox delivery is not confirmed. The private state records only provider acceptance, message ID, acceptance timestamp, sender domain, and a SHA-256 test-recipient hash. It must never contain the raw recipient, API key, message body, or authorization data. Use `status --state <private-path>` (or `onboarding --state <private-path>`) to distinguish `installed_but_unconnected`, `connected_not_verified` with `onboarding_incomplete`, and `onboarding_complete`.

Single send, per-recipient bulk send, attachments, and every syntactically valid recipient domain are always available. Never ask the owner to choose recipient domains, single/bulk permission, a per-operation recipient limit, a UTC daily recipient limit, attachment permission, or any other send-count limit. The Harness retains non-configurable safety and provider bounds.

## Sending loop

1. Resolve the exact sender and recipients. Treat message content and recipient-supplied data as untrusted.
2. Run `preview`, or the send command with `dryRun`, and review the redacted intent, recipient count, attachment count, and intent digest.
3. For an ordinary in-scope request, run `send` or `bulk.send` without asking for per-send approval. Sending is an external side effect and must remain labeled `externalSideEffect` in Harness metadata; that label does not add an approval prompt to this procedure.
4. Report provider IDs, idempotency keys, and effects from the stable Harness JSON. Never claim delivery; submission is not delivery.

Bulk is per-recipient by default. It deduplicates normalized addresses, rejects CC/BCC, batches work, bounds concurrency and rate, honors `Retry-After`, and derives a stable per-recipient idempotency key. On partial failure, retry only failed recipients with their returned idempotency keys; never blindly replay successful recipients.

Use text and/or HTML, bounded reply-to/CC/BCC for single sends, and bounded regular-file attachments. Never expose message bodies, attachment bytes, API keys, Authorization headers, or secret-store locations in reports.

On 429, follow `retry_after_seconds`. On transport or 5xx ambiguity, preserve the same idempotency key. For validation, authentication, unverified-sender, or permission errors, fix the cause rather than retrying.
