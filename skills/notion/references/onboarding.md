# Onboarding and recovery

1. Run `auth.onboarding.plan` without a credential.
2. Get approval before opening consent or creating/using credential state.
3. Human-only: select workspace, create/authorize integration, select minimum capabilities, share exact roots, store token through protected secret storage.
4. Agent: protected runtime injection, then `auth.onboarding.verify --roots <typed bounded list>` for normalized `user.me` identity and exact root retrieval.
5. Configure the verified list as `allowedRoots` for every write. A 404 means missing, wrong workspace, or unshared; a 403 indicates capability/workspace policy. Fix sharing/capabilities before changing IDs.
6. Recovery: rerun status, verify workspace identity, re-share exact roots, then rerun verification. Never broaden access merely to clear a diagnostic.
7. Revoke in Notion, delete the protected secret pointer, then verify `auth.status` is disconnected.

OAuth token exchange/refresh/revoke automation and Developer Portal webhook subscription changes are intentionally outside v0.1.0.
