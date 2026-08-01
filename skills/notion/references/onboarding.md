# Onboarding and recovery

1. Run `auth.onboarding.plan` without a credential.
2. Get approval before opening consent or creating/using credential state.
3. Human-only: select workspace, create/authorize integration, select minimum capabilities, share exact roots, store token through protected secret storage.
4. Agent: protected runtime injection, `user.me`, bounded capability probes, exact root retrieval.
5. A 404 may mean unshared or absent. Check workspace identity and root sharing before changing IDs.
6. Revoke in Notion, delete the protected secret pointer, then verify `auth.status` is disconnected.

OAuth token exchange/refresh/revoke automation and Developer Portal webhook subscription changes are intentionally outside v0.1.0.
