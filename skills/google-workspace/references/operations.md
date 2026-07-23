# Operation guidance

The manifest is the command source of truth and declares all practical Gmail v1, Calendar v3, and Drive v3 operations.

- Gmail: ask whether permanent delete is intended; sending and forwarding are external effects; do not automatically retry an ambiguous send.
- Calendar: require RFC 3339 offsets and IANA zones; all-day end dates are exclusive; ask instance versus recurring series; make `sendUpdates` explicit.
- Drive: require file/drive IDs; native files use export; sharing and comments are external; ownership transfer and permanent removal are destructive.
- Watches: this harness creates/stops provider channels but is not a webhook/Pub/Sub receiver. Require a separately protected receiver and channel-token store.
- OAuth login: a supervising PKCE callback receiver and protected token writer are required. The harness must fail closed if they are absent.
- Credential selection: provide the protected bundle through typed `credentialPath` / `--credential-path` for authenticated auth, Gmail, Calendar, and Drive commands. Keep `account` as the alias selector. Do not place the path in free-form text or output.
