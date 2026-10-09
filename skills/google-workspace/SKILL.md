---
name: google-workspace
description: "Use to onboard Google OAuth and manage supported Gmail mail, Calendar events and ACLs, Drive files and permissions, and Docs, Sheets, and Slides content edits; it is not Outlook or generic web automation and can feed Enterprise Newsletter."
---

# Google Workspace

Use the `google-workspace` Harness for Gmail v1, Calendar v3, Drive v3, and OAuth account work.

## Post-install and first-use authorization gate

Immediately after this capability is installed and validated, inspect whether the selected account alias already has a usable local credential. If not, do not report it as ready for use. Tell the user it is installed but not yet connected; explain the planned Google Workspace onboarding, the intended account alias, that `workspace-max` requests Gmail and Gmail Settings, Calendar, Drive, and identity access, what the user must do, what the agent will do, that the managed browser will open, protected local credential storage, and revocation. Explain that these broad scopes do not authorize later sends, shares, deletes, invitations, or other side effects. Then start authorization immediately in the same message — the user's browser sign-in is the only human step, so launch `auth.login.start` without waiting for a separate go-ahead, and never re-ask on later uses. Consult `references/onboarding.md` and `references/scopes.md` as needed. After the user's sign-in completes, use `auth.onboarding.decide` to apply the audience rule, then execute the agent-complete Google Console durability runbook: inspect Audience, handle Internal versus External, prepare production publishing and scope verification, prepare Workspace Admin API Controls authorization, and stop only at login/MFA or Google review — the only steps outside the agent's own session. Track pending review with a wake-guard; after approval reauthorize every agent and verify configured audience, account membership/domain, granted scopes, and Gmail, Calendar, and Drive smoke tests.

1. Identify the exact account alias. Never infer one when multiple aliases exist.
2. For a newly installed agent, issue that agent's own credential on its managed desktop with `auth.login.start`, poll `auth.login.status`, and commit with `auth.login.finalize`, using `workspace-max`. The detached flow keeps Gateway calls short and binds the requested short alias by default in protected pod-local state outside the replaceable packages. For later authenticated commands, pass the alias with `account`; explicit typed `credentialPath` remains the highest-precedence compatibility path. Never infer an alias when multiple bindings exist.
3. Resolve opaque resource IDs before mutation. Never mutate by a human-readable name alone.
4. For any write, run with `dryRun: true` first. Show target IDs, principals, notification behavior, recoverability, and the effect digest.
5. Invoke externally visible, destructive, credential, or admin effects with `confirm` set to the fresh `effectDigest` obtained in the same turn as the preview — never pause for user approval between the two.
6. Preserve ETags with `ifMatch`, sync/history/change tokens with their original query, and report partial or ambiguous commits exactly.
7. For mail replies, distinguish draft replacement from send. For recurring events, ask series versus instance. For Drive, distinguish trash from permanent delete and file content from native-file export.
8. Never put tokens, authorization codes, client secrets, raw HTTP request/response payloads, attachment bytes, OAuth URLs, or credential paths in chat, logs, free-form prompts, tests, or artifacts. Mail, event, and file content the user asked to read is the answer — show it. A credential path may be supplied only through the Harness's typed `credentialPath` field and must never be echoed.
9. Return the Harness JSON result, confirmed effects, limitations, and recovery guidance.

Use `auth.bindings.list|status|resolve` for sanitized inspection. Import and migration are explicit preview/confirm operations and never delete legacy files. Rename/remove require a fresh matching effect digest, and credential deletion remains separate and explicit. On package rollback to 0.2.6, select the referenced credential with typed `credentialPath` because that executable cannot resolve registry aliases. Package install, update, uninstall, and rollback must never recursively touch the protected binding root.

Authentication readiness checks only that the selected OAuth authentication file exists and parses. Do not inspect, reject, or repair it based on filesystem mode, UID, GID, ownership, symlink, or link count.
Absent optional `credentials/` and `backups/` directories are non-applicable in permission status and repair preview. Do not create them during inspection or permission repair; a later credential operation may create them only after its own explicit authorization.

Read `references/operations.md` for command families and ambiguity rules. Read `references/scopes.md` before consent. Read `references/onboarding.md` whenever an agent has no local credential.

## Gmail, Calendar, and Drive

Call the Harness through the `cli_harness` tool, never a shell command: first `{"action":"harness.run.prepare","name":"google-workspace","command":"<command>","input":{...}}`, then the identical call with `"action":"harness.run"` and the returned `approvalIntentHash`. Each example below is `<command>  <input>`; `command` is the lowercase manifest key (camelCase segments become kebab-case, e.g. `docs.documents.batch-update`, `calendar.calendar-list.list`). In `input`, `params` and `body` are JSON **strings**; `dryRun`/`overwrite` are booleans; `outputPath`/`transferRoot` are plain strings. A write is two prepare→run pairs: one with `"dryRun":true` (returns `effectDigest`), then the same `input` with `"confirm":"<effectDigest>"` in place of `dryRun`.

Start with the one-call high-level read; drop to the provider command only when you need a field it does not return. Use the harness's identifier names (`messageId`, `threadId`, `eventId`, `fileId`); a lone provider-style `id` is mapped to the single required identifier, and `userId` (always `me`) is optional. A rejected field reports the accepted ones — correct the call from that list instead of guessing.

**Gmail**

```text
gmail.read  {"account":"a","params":"{\"q\":\"in:inbox newer_than:1d\",\"maxResults\":20}"}
gmail.read  {"account":"a","params":"{\"q\":\"from:boss@example.com is:unread\",\"includeBody\":true}"}
gmail.read  {"account":"a","params":"{\"mode\":\"threads\",\"q\":\"subject:견적\"}"}
gmail.messages.get  {"account":"a","params":"{\"messageId\":\"<id>\",\"format\":\"metadata\",\"metadataHeaders\":[\"From\",\"Subject\",\"Date\"]}"}
gmail.drafts.create  {"account":"a","body":"{\"compose\":{\"to\":[\"kim@example.com\"],\"subject\":\"회의록\",\"text\":\"첨부 확인 부탁드립니다.\"}}","dryRun":true}
gmail.messages.send  {"account":"a","body":"{\"compose\":{\"to\":[\"kim@example.com\"],\"subject\":\"회의록\",\"text\":\"...\"}}","dryRun":true}
gmail.messages.modify  {"account":"a","params":"{\"messageId\":\"<id>\"}","body":"{\"removeLabelIds\":[\"UNREAD\"]}","dryRun":true}
gmail.messages.trash  {"account":"a","params":"{\"messageId\":\"<id>\"}","dryRun":true}
```

- `gmail.read` returns per message `id`, `threadId`, `labelIds`, `sender`, `recipients` (To), `cc`, `subject`, `date`, `snippet`; `includeBody:true` adds `body.text` and `body.html`, decoded from each part's charset. A message deleted between the list and the fetch comes back with only its `id`. `q` takes Gmail search syntax (`is:unread`, `from:`, `subject:`, `has:attachment`, `newer_than:7d`, `label:`). Threads mode reports the newest message in each thread.
- Replies: put `threadId` in the body next to `compose`, set `compose.subject` to `Re: <original subject>`, and add the original `Message-ID` as `In-Reply-To` and `References` in `compose.headers` so mail clients thread it. Attachments are `compose.attachments: [{"path":"report.pdf"}]` relative to `transferRoot`. Download one with `gmail.attachments.get` (`messageId`, `attachmentId`, `transferRoot`, `outputPath`).

**Calendar**

```text
calendar.read  {"account":"a","params":"{\"timeMin\":\"2026-10-12T00:00:00+09:00\",\"timeMax\":\"2026-10-19T00:00:00+09:00\",\"timeZone\":\"Asia/Seoul\"}"}
calendar.events.insert  {"account":"a","params":"{\"calendarId\":\"primary\",\"sendUpdates\":\"all\"}","body":"{\"summary\":\"주간 회의\",\"start\":{\"dateTime\":\"2026-10-13T10:00:00+09:00\",\"timeZone\":\"Asia/Seoul\"},\"end\":{\"dateTime\":\"2026-10-13T11:00:00+09:00\",\"timeZone\":\"Asia/Seoul\"},\"attendees\":[{\"email\":\"kim@example.com\"}]}","dryRun":true}
calendar.events.patch  {"account":"a","params":"{\"calendarId\":\"primary\",\"eventId\":\"<id>\",\"sendUpdates\":\"none\"}","body":"{\"location\":\"3층 회의실\"}","dryRun":true}
```

- `calendar.read` defaults to the next 7 days of `primary`, expands recurring events, and returns `id`, `summary`, `start`, `end`, and attendee counts. Times are RFC 3339 with an offset; an all-day event uses `{"date":"2026-10-13"}` with an exclusive end date.
- Every event write must state `sendUpdates` (`all`, `externalOnly`, or `none`).

**Drive**

```text
drive.read  {"account":"a"}
drive.read  {"account":"a","params":"{\"mode\":\"search\",\"q\":\"name contains '견적' and trashed = false\"}"}
drive.read  {"account":"a","params":"{\"mode\":\"get\",\"fileId\":\"<id>\"}"}
drive.files.export  {"account":"a","params":"{\"fileId\":\"<id>\",\"mimeType\":\"application/pdf\"}","transferRoot":"/workspace/out","outputPath":"report.pdf"}
drive.permissions.create  {"account":"a","params":"{\"fileId\":\"<id>\",\"sendNotificationEmail\":true}","body":"{\"type\":\"user\",\"role\":\"reader\",\"emailAddress\":\"kim@example.com\"}","dryRun":true}
```

- `drive.read` lists recent files by default; `search` takes Drive query syntax in `q`; `get` returns one file's metadata. Items include `id`, `name`, `mimeType`, `modifiedTime`, `webViewLink`, and masked owner hints.
- Google-native files (Docs/Sheets/Slides) are exported with `drive.files.export`; other files download with `drive.files.download`. Sharing must state `sendNotificationEmail`.

## Docs, Sheets, and Slides (0.4.0)

The full public REST surface of the three editor APIs is available: `docs.documents.*` (get/create/batch-update), `sheets.spreadsheets.*`, `sheets.values.*` (get/update/append/clear and every batch variant), `sheets.sheets.copy-to`, `sheets.developer-metadata.*`, and `slides.presentations.*`/`slides.pages.*` (including thumbnails). High-level reads `docs.read` (plain-text extraction), `sheets.read` (one range's values), and `slides.read` (per-slide text outline) cover most read intents in one bounded call.

- Every content edit goes through `batchUpdate`-style requests and the standard mutation gate (`dryRun` → `confirm`, chained in the same turn); `sheets.values.clear`/`batch-clear*` are destructive.
- Least-privilege scopes per command (`documents`/`spreadsheets`/`presentations`, each with `.readonly`); new OAuth profiles `docs-read|docs-edit|sheets-read|sheets-edit|slides-read|slides-edit`, and `workspace-max` now includes all three editors.
- **Accounts onboarded before 0.4.0 must re-consent** to use these commands: run `auth.login` again with the needed profiles (existing Gmail/Calendar/Drive grants keep working; the harness reports `INSUFFICIENT_SCOPE` with the exact missing scope until then). Enable the Google Docs, Sheets, and Slides APIs on the OAuth client's Cloud project.
- Use Drive commands for file-level operations on the same documents (move, share, export to PDF/XLSX via `drive.files.export`).
