# resend-email Harness

Stdlib-only typed CLI for Resend's HTTPS API. It emits one stable redacted JSON object, stores no API key or private policy, and enables single send, privacy-preserving per-recipient bulk, attachments, and all syntactically valid recipient domains by default. Live sends fail closed unless Resend reports the sender domain as verified. Non-configurable provider and safety bounds remain enforced.

Run `./resend_email.py onboarding` for the secret-free first-use contract. After protected credential and sender verification, `onboarding.test` submits one fixed test message and stores only private, non-sensitive acceptance proof; acceptance is not inbox delivery. Tests use only mocks and fixture credentials.
