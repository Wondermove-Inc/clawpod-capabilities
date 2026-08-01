# Test

Run:

```text
python3 -m pytest -q harnesses/notion/tests
python3 harnesses/notion/tests/onboarding_smoke.py
python3 scripts/sync_registry.py --check
python3 scripts/validate.py
```

Tests use deterministic adapter fixtures and loopback mock HTTP only. They cover login/MFA/permission/secret-capture/CAPTCHA handoffs, workspace and 403/404 root failures, revision/restart/cancel/timeout behavior, redaction, pure plan/status, allowlists, and API errors. No test contacts Notion or uses a real credential.
