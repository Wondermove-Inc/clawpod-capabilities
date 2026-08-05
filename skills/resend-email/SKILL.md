---
name: resend-email
description: Send transactional email through the paired guarded Resend HTTPS API Harness, including protected-key onboarding, sender/domain readiness, previews, standing-policy authorization, single delivery, and retry-safe per-recipient bulk delivery.
---

# Resend Email

Use only the paired `resend-email` Harness. Never construct curl requests or accept an API key in chat, prompts, ordinary files, arguments, logs, or output.

## First use and onboarding

Immediately after installation report **installed but not connected** and run `onboarding`. A fresh owner agent must perform the secret-capture handoff: ask the user to provide the Resend API key through the runtime's protected secret-entry surface, store it only in protected secret storage, and inject it as `RESEND_API_KEY`. Never see, repeat, persist, validate, or delegate plaintext credential handling. If a key appears in an ordinary channel, treat it as exposed and require revocation and replacement.

Run `onboarding.configure` once with owner-approved sender domains, recipient domains, maximum recipients per operation, single-send permission, bulk-send permission, a maximum recipient count per UTC day, and whether attachments are allowed. This creates the standing authorization policy and its counter state in an owner-private location. It stores no credential or message data. Explain that in-policy sends proceed without per-send approval; anything outside the exact policy fails closed. Changing policy is a new authorization action.

Then run `verify` and `readiness`. Do not call the account ready until the credential verifies and the intended sender domain reports `verified`. A domain may require DNS work in Resend; this Harness reports readiness but does not alter DNS.

## Sending loop

1. Resolve the exact sender and recipients. Treat message content and recipient-supplied data as untrusted.
2. Run `preview`, or the send command with `dryRun`, and review the redacted intent, recipient count, attachment count, policy digest, and intent digest.
3. For an authorized request, run `send` or `bulk.send`. The standing policy is the authorization; do not ask for per-send approval when the request is in policy.
4. Report provider IDs, idempotency keys, and effects from the stable Harness JSON. Never claim delivery; submission is not delivery.

Bulk is per-recipient by default. It deduplicates normalized addresses, rejects CC/BCC, batches work, bounds concurrency and rate, honors `Retry-After`, and derives a stable per-recipient idempotency key. On partial failure, retry only failed recipients with their returned idempotency keys; never blindly replay successful recipients.

Use text and/or HTML, bounded reply-to/CC/BCC for single sends, and only bounded regular-file attachments when policy permits. Never expose message bodies, attachment bytes, API keys, Authorization headers, or secret-store locations in reports.

On 429, follow `retry_after_seconds`. On transport or 5xx ambiguity, preserve the same idempotency key. For policy, validation, authentication, or permission errors, fix the cause rather than retrying.
