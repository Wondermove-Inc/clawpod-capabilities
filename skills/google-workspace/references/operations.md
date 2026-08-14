# Operation guidance

The manifest is the command source of truth and declares all practical Gmail v1, Calendar v3, and Drive v3 operations.

- Gmail: ask whether permanent delete is intended; sending and forwarding are external effects; do not automatically retry an ambiguous send.
- Calendar: require RFC 3339 offsets and IANA zones; all-day end dates are exclusive; ask instance versus recurring series; make `sendUpdates` explicit.
- Drive: require file/drive IDs; native files use export; sharing and comments are external; ownership transfer and permanent removal are destructive.
- Watches: this harness creates/stops provider channels but is not a webhook/Pub/Sub receiver. Require a separately protected receiver and channel-token store.
- OAuth login: a supervising PKCE callback receiver and protected token writer are required. The harness must fail closed if they are absent.
- Credential selection: provide the protected bundle through typed `credentialPath` / `--credential-path` for authenticated auth, Gmail, Calendar, and Drive commands. Keep `account` as the alias selector. Do not place the path in free-form text or output.

## v0.3.0 compatibility migration

- Version 0.3.6 also makes `auth.bindings.permissions.repair` the bounded v0.3.4 GID migration: preview binds exact parent/target snapshots and expected process UID/store GID, then confirmation uses no-follow descriptors to repair only recognized process-UID-owned artifacts to `0700`/`0600`. Unknown names, foreign UIDs, links, races, and unsafe types fail closed; partial failures roll back best-effort and remain retryable without registry revision, backup, credential-byte, legacy-source, or provider drift. Fresh absent stores are a no-op.

- Forge binding roots may use exact absolute `/workspace` at `02777` only when its immediate next component is the process-UID-owned private protected root at `0700` (or legacy pre-repair `02770`) and both have one uniform chain GID. There is no `/workspace/.local` chain. This does not change the existing exact `/root/.local/state/openclaw/google-workspace` rule and does not trust `/workspace` as a prefix: extra components before the boundary, arbitrary deeper roots, lookalikes, symlinks, hardlinks, mixed identities, wrong modes, containment escapes, and path-swap races fail closed.
- Prefer top-level `pageSize` as an integer from 1 through 500. Gateway 2026.4.11 represents that field as JSON `number` during prepare because its validator does not distinguish JavaScript integers; the `argMap` integer gate rejects fractional values before execution, and the harness rich schema revalidates the integer and limits.
- Provider-form pagination is retained for compatibility: Gmail and Calendar accept `params.maxResults`; Drive accepts `params.pageSize`. Through the current Gateway, pass the typed provider object as its deterministic JSON-string argv representation (for example, `params: "{\"pageSize\":10}"`). Direct CLI JSON input continues to accept an object. A top-level/provider value pair must match or the harness rejects it instead of choosing one silently.
- No credential or binding migration is necessary when upgrading from 0.3.0. When rolling back to 0.2.6, aliases are unavailable; use the existing typed `credentialPath` compatibility field and leave the protected binding registry untouched.
