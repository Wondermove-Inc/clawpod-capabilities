# resend-email Harness

Stdlib-only typed CLI for Resend's HTTPS API. It emits one stable redacted JSON object, stores no API key, and requires a private standing-policy file for sends. Single/bulk permissions and a lock-protected durable UTC-daily recipient quota are owner-configured; previews consume no quota and state contains counters only.

Run `./resend_email.py onboarding` for the secret-free first-use contract. Tests use only a loopback mock backend and fixture credentials.
