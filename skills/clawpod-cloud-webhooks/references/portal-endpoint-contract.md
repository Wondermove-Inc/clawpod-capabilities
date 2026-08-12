# Portal endpoint contract evidence

This reference records sanitized endpoint evidence only. It contains no credentials, tokens, cookies, tenant identifiers, or resource identifiers.

## Frontend-exposed contract

The authenticated portal frontend exposed these exact proxy-relative routes:

- Reads: `GET /webhook-presets`, `GET /webhook-sources`, `GET /webhook-sources/{id}`, `GET /webhook-playbooks`, `GET /webhook-playbooks/{id}`, `GET /webhook-rules`, `GET /webhook-rules/{id}`, `GET /webhook-events`, `GET /webhook-events/{id}`.
- Sources: `POST /webhook-sources`, `PUT /webhook-sources/{id}`, `DELETE /webhook-sources/{id}`, `POST /webhook-sources/{id}/regenerate`, `POST /webhook-sources/{id}/rotate-secret`.
- Playbooks: `POST /webhook-playbooks`, `PUT /webhook-playbooks/{id}`, `DELETE /webhook-playbooks/{id}`.
- Rules: `POST /webhook-rules`, `PUT /webhook-rules/{id}`, `DELETE /webhook-rules/{id}`.

Source: `/workspace/artifacts/clawpod-cloud-webhooks-readonly-20260728/report.md`, “Portal API contract observed”, lines 204–232. That investigation observed frontend contracts and did not invoke mutations.

## Controlled CRUD and cleanup evidence

A separately approved contract test exercised disposable Source, Playbook, and Rule mutations. Cleanup deleted 32/32 Rules, 6/6 Sources, and 6/6 Playbooks, with zero prefixed resources remaining. The same test established that Source `PUT` is a full-object replacement contract: a partial `PUT` changing only `is_active` cleared nullable `playbook_id`. Therefore updates must fresh-GET, preserve the complete returned object, overlay allowed changes, PUT the full object, then verify by exact-item GET.

Source: `/workspace/artifacts/clawpod-cloud-webhooks-contract-tests-20260728/report.md`, summary lines 4–8, full-object PUT finding line 208, cleanup lines 270–273, and recommendation line 283.

These reports are development provenance, not runtime dependencies. Live mutation still requires preview, digest-bound idempotency key, explicit approval, tenant preflight, and authoritative readback.
