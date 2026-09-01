# Operation guidance

The manifest is the command source of truth and declares all practical Gmail v1, Calendar v3, and Drive v3 operations.

- Gmail: default to trash unless the request explicitly says permanent delete; sending and forwarding are external effects; do not automatically retry an ambiguous send.
- Calendar: require RFC 3339 offsets and IANA zones; all-day end dates are exclusive; ask instance versus recurring series; make `sendUpdates` explicit.
- Drive: require file/drive IDs; native files use export; sharing and comments are external; ownership transfer and permanent removal are destructive.
- Watches: this harness creates/stops provider channels but is not a webhook/Pub/Sub receiver. Require a separately protected receiver and channel-token store.
- OAuth login: a supervising PKCE callback receiver and protected token writer are required. The harness must fail closed if they are absent.
- Credential selection: provide the protected bundle through typed `credentialPath` / `--credential-path` for authenticated auth, Gmail, Calendar, and Drive commands. Keep `account` as the alias selector. Do not place the path in free-form text or output.

## v0.3.0 compatibility migration

- Version 0.3.7 retires binding permission check/repair commands; auth readiness depends on authentication-file existence and parsing, not filesystem metadata.

- Prefer top-level `pageSize` as an integer from 1 through 500. Gateway 2026.4.11 represents that field as JSON `number` during prepare because its validator does not distinguish JavaScript integers; the `argMap` integer gate rejects fractional values before execution, and the harness rich schema revalidates the integer and limits.
- Provider-form pagination is retained for compatibility: Gmail and Calendar accept `params.maxResults`; Drive accepts `params.pageSize`. Through the current Gateway, pass the typed provider object as its deterministic JSON-string argv representation (for example, `params: "{\"pageSize\":10}"`). Direct CLI JSON input continues to accept an object. A top-level/provider value pair must match or the harness rejects it instead of choosing one silently.
- No credential or binding migration is necessary when upgrading from 0.3.0. When rolling back to 0.2.6, aliases are unavailable; use the existing typed `credentialPath` compatibility field and leave the protected binding registry untouched.

## Docs, Sheets, Slides examples

```
# read a doc as text / a range's values / a deck outline
google-workspace docs.read   --account a --params '{"documentId":"<id>"}'
google-workspace sheets.read --account a --params '{"spreadsheetId":"<id>","range":"Sheet1!A1:D20"}'
google-workspace slides.read --account a --params '{"presentationId":"<id>"}'

# write values (mutation gate: dry-run → approve digest → confirm)
google-workspace sheets.values.update --account a   --params '{"spreadsheetId":"<id>","range":"Sheet1!A1:B2","valueInputOption":"USER_ENTERED"}'   --body '{"values":[["이름","점수"],["가",95]]}' --dry-run
google-workspace sheets.values.append --account a --params '{"spreadsheetId":"<id>","range":"Sheet1!A:B","valueInputOption":"USER_ENTERED"}' --body '{"values":[["나",88]]}' --dry-run

# structured edits: one verb per request object
google-workspace docs.documents.batchUpdate --account a --params '{"documentId":"<id>"}'   --body '{"requests":[{"insertText":{"location":{"index":1},"text":"요약\n"}}]}' --dry-run
google-workspace slides.presentations.batchUpdate --account a --params '{"presentationId":"<id>"}'   --body '{"requests":[{"createSlide":{}}]}' --dry-run
```
