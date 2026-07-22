# Google Workspace AgentSkill and CLI Harness contract

Status: implementation design, no implementation in this change

Target capability identity: `google-workspace`

Upstream APIs: Gmail API v1, Calendar API v3, Drive API v3, Google OAuth 2.0

## 1. Product and machine identity

The product is **Google Workspace**, exposed as one paired capability with the same machine name in separate namespaces:

- AgentSkill: `skills/google-workspace/`
- CLI Harness: `harnesses/google-workspace/`
- executable entrypoint (planned): `google_workspace.py`
- harness manifest: `harnesses/google-workspace/harness.json`, `kind: openclaw.harness.v1`, `schemaVersion: 1`
- package metadata: one `capability.json` per package, initially version `0.1.0`

The shared name is safe because AgentSkills and CLI Harnesses are distinct capability types and installation namespaces. Command names are dotted (`gmail.messages.list`) to remain stable if the executable presentation later adds nested subcommands.

The capability is an API client, not a replacement UI, sync engine, mail server, file system, webhook receiver, or credential vault. Gmail, Calendar, and Drive resource IDs remain opaque strings. Human-readable names never substitute for IDs when a command can mutate or delete a resource.

## 2. Repository fit and architecture

This design follows the repository's existing paired-package pattern:

1. The **AgentSkill** interprets intent, chooses an account and least-privilege scope profile, resolves ambiguity, obtains required approval, invokes previews, and explains results.
2. The **CLI Harness** deterministically validates typed input, obtains injected credentials, calls official REST APIs, writes local transfer targets where requested, and emits exactly one JSON result.
3. `harness.json` declares every command's `baseArgv`, `safetyClasses`, closed `inputSchema`, stable `outputSchema`, and `argMap`.
4. Package tests live under `harnesses/google-workspace/tests/`. Repository validation and generated registry behavior remain unchanged.

```text
user intent
  -> google-workspace AgentSkill (routing, account/scope/safety decisions)
  -> google-workspace CLI Harness (validation, HTTP, transfer, stable JSON)
  -> Google OAuth 2.0 + Gmail/Calendar/Drive REST APIs
```

The harness should use a small dependency surface and Google-supported authentication/client primitives. API behavior is pinned to Gmail v1, Calendar v3, and Drive v3, while discovery documents are test inputs, not an unchecked runtime command generator.

## 3. Safety model, independent of feature availability

A command being implemented and authorized by OAuth does **not** mean it is approved to run. The manifest may list multiple classes:

| Mark | Manifest class | Meaning | Default runtime treatment |
|---|---|---|---|
| `C` | `credentialRelated` | Starts, changes, uses, inspects, or revokes an authenticated account/session | secret-aware runtime boundary; never log token material |
| `R` | `readOnly` | Reads remote state, though returned content may be sensitive | no remote mutation; still requires account authorization |
| `W` | `writeSafe` | Changes private/recoverable state without intended third-party notification | show exact target/change; approval according to runtime policy |
| `E` | `externallyVisible` | Sends, shares, invites, notifies, publishes, or changes another principal's access | explicit approval after recipient/target preview |
| `D` | `destructive` | Permanent deletion, bulk deletion, ownership transfer, or high-impact clearing | explicit confirmation bound to account, resource IDs, and operation digest |

All API commands that use OAuth are technically credential-using, but command tables mark `C` only for credential lifecycle/account inspection commands. The manifest's `authModel` must still declare `type: oauth2-user`, `storesSecrets: false`, and `requiresHumanAccount: true`; API commands receive credentials solely through approved injection.

`--dry-run` is mandatory for `W`, `E`, and `D` commands. It validates input, account, granted scopes, target existence where safely readable, and preconditions, but performs no mutation. `--preview` returns a canonical effect plan. Neither option silently degrades into execution. Execution of `E` and `D` requires `--confirm <effectDigest>` from that preview, scoped to the account and expiring after 10 minutes. `W` accepts the digest when runtime policy requires it. A feature remains available even when policy blocks invocation; return `APPROVAL_REQUIRED`, not `UNSUPPORTED`.

Previews redact message bodies, file contents, attendee notes, tokens, and credential paths by default. They include recipient/access principals, resource names and IDs, calendar/time range, Drive destination/permission role, notification behavior, and recoverability.

## 4. Global invocation and typed input

Logical invocation:

```text
google_workspace.py <dotted-command> [declared flags] --json
```

Every command accepts these manifest-declared common fields where applicable:

| Field | Type | Rules |
|---|---|---|
| `account` | string | required except `auth.*` discovery; normalized local alias, never inferred when multiple accounts exist |
| `fields` | array[string] | optional partial-response field paths; harness adds identity/pagination fields required by its envelope |
| `pageSize` | integer | optional, `1..500` unless upstream maximum is lower |
| `pageToken` | string | opaque; cannot be combined with a changed query fingerprint |
| `allPages` | boolean | default false; bounded by `maxItems` and `maxPages` |
| `maxItems` | integer | default 1000, maximum 10000 |
| `maxPages` | integer | default 20, maximum 100 |
| `timeoutMs` | integer | `1000..120000`, default 30000 |
| `dryRun` | boolean | default false; mutation commands only |
| `preview` | boolean | default false; mutation commands only |
| `confirm` | string | effect digest from a fresh preview |
| `requestId` | string | caller correlation ID, 1..128 safe ASCII characters; not an idempotency guarantee |
| `ifMatch` | string | optional ETag precondition where supported |

Input schemas use `additionalProperties: false`, explicit formats, bounded arrays/strings, and mutually exclusive alternatives (`oneOf`) for source variants. Dates are `YYYY-MM-DD`; instants are RFC 3339 with an offset or `Z`; time zones are IANA names. Email addresses are validated conservatively without rewriting case or internationalized values. Local paths have manifest `pathRole` and are resolved without traversal outside the explicitly supplied transfer root.

Large request bodies use `--input-json <path>` or standard input, never shell-expanded body flags. Binary content uses an input path. No command accepts an access token, refresh token, client secret, or service-account key as a normal argument.

## 5. Stable JSON output

Exactly one UTF-8 JSON object is written to stdout. Diagnostics go to stderr and contain no secrets or content unless an explicit safe debug mode is added later.

Success:

```json
{
  "ok": true,
  "schemaVersion": 1,
  "command": "drive.files.list",
  "requestId": "caller-or-generated-uuid",
  "account": {"alias": "work", "subject": "redacted-hash", "email": "user@example.com"},
  "data": {},
  "page": {"nextPageToken": null, "itemsReturned": 3, "pagesFetched": 1, "truncated": false},
  "effects": [],
  "provenance": {
    "provider": "google",
    "api": "drive",
    "apiVersion": "v3",
    "operation": "files.list",
    "receivedAt": "2026-01-01T00:00:00Z",
    "resourceIds": [],
    "etag": null
  },
  "warnings": []
}
```

Failure:

```json
{
  "ok": false,
  "schemaVersion": 1,
  "command": "calendar.events.insert",
  "requestId": "...",
  "account": {"alias": "work"},
  "error": {
    "code": "PRECONDITION_FAILED",
    "message": "Event changed since preview",
    "retryable": false,
    "providerStatus": 412,
    "providerReason": "conditionNotMet",
    "details": {},
    "remediation": "Refresh the event and create a new preview"
  },
  "effects": [],
  "provenance": {"provider": "google", "api": "calendar", "apiVersion": "v3"}
}
```

Stable resource adapters preserve documented Google fields but normalize collection placement:

- list outputs: `data.items: array`, plus `page`;
- single resource: `data.resource`;
- transfer: `data.transfer` with `path`, `bytes`, `sha256`, `mimeType`, `resumed`, and remote ID;
- mutation: `data.resource` when returned and `effects[]` containing `kind`, resource/principal IDs, before/after summaries, notification mode, recoverability, and `effectDigest` in previews;
- watch: `data.channel` with ID, resource ID, expiration, token hash (never token), and stop parameters.

Unknown upstream fields may pass through within `data.resource.providerFields`, but documented normalized fields and envelope keys cannot change before a major version. Empty values are explicit `null`/`[]`, not omitted unpredictably.

## 6. Pagination and partial responses

- Preserve Google page tokens as opaque strings. Return only the next token, never fabricate offsets.
- Automatic traversal is opt-in (`allPages`) and stops at both `maxItems` and `maxPages`; `page.truncated` and a warning explain the boundary.
- Bind cached/page tokens to account alias, API, command, query parameters, corpus/space/drive, and requested field set. Reject mismatches locally.
- Calendar incremental sync tokens and Gmail history IDs are not generic page tokens. They use dedicated fields and commands. Drive change page tokens are likewise separate.
- Send `fields` for partial responses where supported. The harness unions caller fields with IDs, ETags, pagination tokens, and fields required to produce its stable schema. Return `effectiveFields` in provenance.
- Drive commands should default to narrow fields because Drive v3 requires deliberate field selection for many useful properties. Caller field expressions are syntactically validated and size-bounded.

## 7. Command inventory

The inventory is the final target scope. Phasing in section 18 schedules implementation but does not remove commands. `*` means the command has a preview/dry-run path.

### 7.1 Authentication and account status

| Command | Operation and key typed inputs | Safety |
|---|---|---|
| `auth.accounts.list` | local account aliases; no token values | C,R |
| `auth.accounts.status` | `account`; granted/required scopes, expiry state, subject/email, enabled APIs | C,R |
| `auth.login`* | `account`, `scopeProfile`, optional incremental scopes, loopback callback mode | C,E |
| `auth.logout`* | remove local account binding/cache; optional `revokeRemote` | C,W; E if remote revoke |
| `auth.scopes.list` | named profiles and exact scope URIs | R |
| `auth.scopes.check` | `account`, `commands[]` or `scopeProfile`; missing grants only | C,R |
| `auth.whoami` | profile identity from Gmail profile/Drive about and token subject consistency | C,R |

`auth.login` is a one-shot Desktop-app flow intended to run on the account owner's PC. Invoke it with `--account <alias> --transfer-root <private-dir> --output-path <relative-credential-file> --body '{"clientPath":"relative-installed-client.json","profiles":["gmail-read"]}' --timeout-ms 180000 --json`; add `--overwrite` only when merging a new alias into an existing private bundle. The installed-client input and existing output must be regular, non-symlink mode-0600 files beneath the transfer root. The receiver binds only `127.0.0.1` on an OS-assigned port, uses state and PKCE S256, opens the browser, and prints the standard authorization URL only when browser opening fails. The result contains sanitized alias/identity/scope metadata, never authorization codes, tokens, client secrets, verifier, or credential contents. Device flow, web-client JSON, public callbacks, service accounts, and domain-wide delegation are not supported.

### 7.2 Gmail

`userId` defaults to `me`; another value requires an explicitly delegated/admin account model. Gmail raw message bytes are base64url encoded by the API, but the CLI accepts/returns files or decoded structured MIME unless `rawBase64Url` is explicitly requested.

| Command | Operation and key inputs | Safety |
|---|---|---|
| `gmail.profile.get` | profile/email, totals, history ID | R |
| `gmail.messages.list` | `q`, `labelIds[]`, `includeSpamTrash`, paging | R |
| `gmail.messages.get` | `messageId`, format `minimal|metadata|full|raw`, metadata headers | R |
| `gmail.messages.modify`* | ID, add/remove label IDs | W |
| `gmail.messages.batchModify`* | bounded IDs (max upstream limit), labels | W |
| `gmail.messages.trash`*, `gmail.messages.untrash`* | message ID | W |
| `gmail.messages.delete`*, `gmail.messages.batchDelete`* | permanent deletion by IDs | D |
| `gmail.messages.import`*, `gmail.messages.insert`* | RFC 2822 source, internal date policy, labels; import scanning options | W |
| `gmail.messages.send`* | MIME source or structured compose input, thread linkage | E |
| `gmail.threads.list`, `gmail.threads.get` | query/labels or thread ID and format | R |
| `gmail.threads.modify`* | thread ID, add/remove labels | W |
| `gmail.threads.trash`*, `gmail.threads.untrash`* | thread ID | W |
| `gmail.threads.delete`* | permanent deletion | D |
| `gmail.attachments.get` | message ID, attachment ID, output path or base64url | R (local write declared) |
| `gmail.labels.list`, `gmail.labels.get` | label identity | R |
| `gmail.labels.create`*, `gmail.labels.patch`*, `gmail.labels.update`* | name, visibility, colors | W |
| `gmail.labels.delete`* | removes user label from mailbox/resources | D |
| `gmail.drafts.list`, `gmail.drafts.get` | paging or draft ID | R |
| `gmail.drafts.create`*, `gmail.drafts.update`* | MIME/compose source; update replaces content | W |
| `gmail.drafts.delete`* | permanent draft deletion | D |
| `gmail.drafts.send`* | draft ID or draft payload | E |
| `gmail.history.list` | `startHistoryId`, history types, labels, paging | R |
| `gmail.watch.start`*, `gmail.watch.stop`* | Pub/Sub topic, labels/filter; mailbox stop | E |
| `gmail.settings.get` | kind `autoForwarding|imap|language|pop|vacation` | R |
| `gmail.settings.update`* | same kind and typed settings body | W; E for vacation/forwarding behavior |
| `gmail.settings.filters.list|get` | filter ID | R |
| `gmail.settings.filters.create`*, `gmail.settings.filters.delete`* | criteria/action or ID | W; E when forwarding |
| `gmail.settings.forwardingAddresses.list|get` | address | R |
| `gmail.settings.forwardingAddresses.create`*, `gmail.settings.forwardingAddresses.delete`* | forwarding address | E |
| `gmail.settings.sendAs.list|get` | alias | R |
| `gmail.settings.sendAs.create`*, `gmail.settings.sendAs.patch`*, `gmail.settings.sendAs.update`*, `gmail.settings.sendAs.verify`* | alias/signature/reply-to/SMTP config or verification | C,E |
| `gmail.settings.delegates.list|get` | delegate email | R |
| `gmail.settings.delegates.create`*, `gmail.settings.delegates.delete`* | delegate email; Workspace/admin constraints | C,E |
| `gmail.settings.smime.list|get` | send-as and certificate ID | C,R |
| `gmail.settings.smime.insert`*, `gmail.settings.smime.setDefault`*, `gmail.settings.smime.delete`* | certificate/key material by injected file, IDs | C,E; D for delete |

Settings coverage intentionally excludes Gmail CSE key-pair/identity lifecycle in v1: private-key wrapping and key-service administration deserve a separate security contract. The harness must report these as `UNSUPPORTED_BY_CONTRACT`, not hide that the upstream API exists.

### 7.3 Calendar

Event inputs distinguish timed (`dateTime` plus required/derivable `timeZone`) from all-day (`date`); mixing them is invalid. `sendUpdates` is explicit (`all|externalOnly|none`) and never defaults silently on externally visible operations.

| Command | Operation and key inputs | Safety |
|---|---|---|
| `calendar.colors.get`, `calendar.settings.list|get` | color/setting metadata | R |
| `calendar.calendarList.list|get` | paging or calendar ID | R |
| `calendar.calendarList.insert`*, `calendar.calendarList.patch`*, `calendar.calendarList.update`* | calendar entry/preferences | W |
| `calendar.calendarList.delete`* | unsubscribe/remove from user's list, not calendar deletion | W |
| `calendar.calendarList.watch`* | HTTPS channel definition | E |
| `calendar.calendars.get` | calendar ID | R |
| `calendar.calendars.insert`*, `calendar.calendars.patch`*, `calendar.calendars.update`* | summary, description, location, IANA zone | W |
| `calendar.calendars.delete`* | permanently delete secondary calendar | D |
| `calendar.calendars.clear`* | delete all primary calendar events | D |
| `calendar.calendars.transferOwnership`* | calendar ID, new owner, admin access | C,E,D |
| `calendar.events.list` | calendar, time bounds, query, event types, sync token, deleted/singleEvents/order | R |
| `calendar.events.get` | calendar/event ID; optional time zone | R |
| `calendar.events.instances` | recurring event ID, original start/time bounds, paging | R |
| `calendar.events.insert`*, `calendar.events.import`*, `calendar.events.quickAdd`* | typed event/iCal import/text; notification/conference options | E |
| `calendar.events.patch`*, `calendar.events.update`* | IDs, event body, ETag; update is full replacement | E |
| `calendar.events.move`* | source calendar/event, destination calendar, notifications | E |
| `calendar.events.delete`* | calendar/event ID, notification mode | D,E |
| `calendar.events.watch`* | calendar query plus HTTPS channel | E |
| `calendar.freebusy.query` | RFC 3339 range, IANA zone, bounded calendar/group IDs | R |
| `calendar.acl.list|get` | calendar/rule ID | R |
| `calendar.acl.insert`*, `calendar.acl.patch`*, `calendar.acl.update`* | scope type/value, role, notifications | E |
| `calendar.acl.delete`* | revoke access rule | E,D |
| `calendar.acl.watch`* | calendar and HTTPS channel | E |
| `calendar.channels.stop`* | channel/resource ID | W |

### 7.4 Drive

All file commands expose `supportsAllDrives`; list/search additionally expose `corpora`, `driveId`, `includeItemsFromAllDrives`, `spaces`, and `orderBy`. Shared-drive mutations require explicit `driveId`/resource ID context rather than name matching.

| Command | Operation and key inputs | Safety |
|---|---|---|
| `drive.about.get` | required fields | R |
| `drive.files.list`, `drive.files.search` | `q`, corpora/drive/spaces/order, paging; search is a validated alias of list | R |
| `drive.files.get` | file ID, metadata fields, acknowledge abuse where allowed | R |
| `drive.files.create`* | metadata; optional local content and upload mode | W |
| `drive.folders.create`* | name, parent IDs, drive context | W |
| `drive.files.upload`* | local path, metadata, `simple|multipart|resumable` | W |
| `drive.files.download` | file ID, output path, range/resume, acknowledge abuse | R (local write declared) |
| `drive.files.export` | Google Workspace file ID, export MIME, output path | R (local write declared) |
| `drive.files.copy`* | source ID, new metadata/parents | W |
| `drive.files.update`* | metadata and/or content, ETag, upload mode | W |
| `drive.files.move`* | file ID, add/remove parent IDs; validates single-parent semantics | W |
| `drive.files.trash`*, `drive.files.untrash`* | implemented via files.update `trashed` | W |
| `drive.files.delete`* | permanent delete | D |
| `drive.files.emptyTrash`* | scope/drive context where supported | D |
| `drive.files.generateIds` | count, space, type | R |
| `drive.permissions.list|get` | file/permission IDs, paging | R |
| `drive.permissions.create`* | type, role, email/domain, discovery/expiry/transferOwnership/sendNotificationEmail | E; D when ownership transfer |
| `drive.permissions.update`* | IDs, role/expiry/pending-owner transfer, notification behavior | E; D when ownership transfer/downgrade impact |
| `drive.permissions.delete`* | revoke principal access | E,D |
| `drive.comments.list|get` | file/comment IDs, includeDeleted, paging | R |
| `drive.comments.create`*, `drive.comments.update`*, `drive.comments.delete`* | content/quoted anchor or IDs | E; D for delete |
| `drive.comments.replies.list|get` | file/comment/reply IDs | R |
| `drive.comments.replies.create`*, `drive.comments.replies.update`*, `drive.comments.replies.delete`* | content/action or IDs | E; D for delete |
| `drive.revisions.list|get` | file/revision IDs, paging or content output | R |
| `drive.revisions.update`* | keepForever/publish flags where supported | E |
| `drive.revisions.delete`* | permanent version deletion | D |
| `drive.sharedDrives.list|get` | paging/query or drive ID | R |
| `drive.sharedDrives.create`* | name and required caller `requestId` idempotency key | W |
| `drive.sharedDrives.update`*, `drive.sharedDrives.hide`*, `drive.sharedDrives.unhide`* | drive ID and metadata/view state | W |
| `drive.sharedDrives.delete`* | permanently delete empty shared drive | D |
| `drive.changes.startPageToken`, `drive.changes.list` | optional drive ID, page token, restrictions, paging | R |
| `drive.changes.watch`* | page token and HTTPS channel | E |
| `drive.files.watch`* | file ID and HTTPS channel | E |
| `drive.channels.stop`* | channel/resource ID | W |

Folders are Drive files with MIME type `application/vnd.google-apps.folder`; `drive.folders.create` is a safer typed convenience command. Copy and move remain distinct. Trash is recoverable; delete and empty trash are destructive. Drive approvals, access proposals, labels, CSE, and long-running-operation administration are outside v1 contract and may be added without weakening the listed scope.

## 8. MIME and RFC 2822 mail contract

Compose input is exactly one of:

1. `rawPath`: complete RFC 2822/MIME message bytes;
2. `rawBase64Url`: already encoded API payload, allowed only for machine callers;
3. `compose`: typed `{from?, to[], cc[], bcc[], replyTo[], subject, text?, html?, headers?, attachments[]}`.

The harness constructs CRLF-delimited RFC 2822/MIME, validates header names, blocks CR/LF injection, and uses base64url without padding for Gmail API `raw`. It generates a random MIME boundary, encodes non-ASCII headers correctly, streams attachments from declared input paths, detects/accepts MIME type, and reports filename, size, and SHA-256 in previews. Bcc is included for delivery but redacted from stored/displayed previews except recipient identity needed for approval. Caller-supplied `Message-ID` is allowed only in raw mode and validated; structured mode generates one only if required for duplicate controls.

Thread replies require `threadId` plus RFC-compliant `References` and `In-Reply-To` values. The harness warns if subject/headers would prevent Gmail from associating the message with the intended thread. Gmail messages are immutable after creation; editing means replacing a draft or creating/sending another message.

Attachment retrieval verifies decoded byte count against upstream size when available and writes atomically (`.part`, fsync, rename). Existing outputs require `overwrite: true` or a matching resume contract.

## 9. Calendar time zones and recurrence

- Accept only RFC 3339 instants with explicit offsets, IANA time-zone IDs, and ISO dates for all-day events. Reject ambiguous local date-times without a zone.
- Preserve the event/calendar zone and original offset in output. Include normalized UTC instants as additive fields, never replace source values.
- Timed event end must be after start. All-day `end.date` is exclusive. Preview states both human zone and UTC range.
- Recurrence accepts an array of RFC 5545 recurrence lines (`RRULE`, `RDATE`, `EXDATE`) with validation and bounded expansion for previews. A recurring event requires a time zone.
- `events.instances` is the authoritative expansion command. Local recurrence expansion is preview assistance only and must be marked non-authoritative around DST or provider-specific behavior.
- Updating one instance requires its instance event ID and `originalStartTime`; changing a series uses the recurring event ID. The Skill must ask which is intended.
- Incremental sync follows Calendar's `nextSyncToken`; incompatible filters cannot change between sync calls. A provider `410 Gone` maps to `SYNC_TOKEN_EXPIRED` and requires a fresh full sync.

## 10. Transfers and resumability

Drive uploads support simple media for small content, multipart for metadata plus content, and resumable sessions for large or interruption-prone content. Default to resumable above a configurable threshold (initially 8 MiB) and use chunk sizes that are multiples of 256 KiB. Persist only resumable session metadata, never authorization headers: account alias, file/path identity, source size/mtime/SHA-256, session URL encrypted or treated as a bearer secret, confirmed byte offset, expiry, target metadata digest, and timestamps. Resume only when all fingerprints match.

Downloads use range requests where upstream supports them, write to `.part`, and verify ETag/version plus expected total before resume. Google Workspace native files use export, not media download. If the export exceeds provider limits or a format is unsupported, fail clearly without a partial success claim.

A transfer result is successful only after final provider confirmation and local atomic rename/checksum. Interrupted transfer state is bounded by TTL and removable via cache maintenance; no content bytes are cached by default.

## 11. Idempotency and duplicate prevention

- Reads, preview, watch stop, label-state setting, trash/untrash, and full desired-state updates are retryable only when their exact semantics are idempotent and preconditions still hold.
- Calendar event creation may use a caller-supplied valid event ID. Drive shared-drive creation requires Google's `requestId`. Drive file creation may use pre-generated IDs where the API supports the file type. Store provider-created IDs against a local idempotency key.
- Gmail send and draft send are **not automatically retried** after any ambiguous network failure. Return `AMBIGUOUS_COMMIT` with the request fingerprint and reconciliation guidance. Search by generated `Message-ID` only as evidence, not proof of non-delivery.
- Generic `requestId` is correlation only. A mutation may additionally accept `idempotencyKey`; bind it to account, command, canonical input digest, and result ID for a bounded TTL. Reuse with different input is `IDEMPOTENCY_CONFLICT`.
- Before create/copy/send, previews include a duplicate fingerprint. The AgentSkill should search for likely existing events/files/drafts when practical and present candidates rather than silently deduplicate.
- Use ETags/`If-Match` for read-modify-write where Google supports them. Preview confirmation is invalid if the observed ETag or target summary changes.

## 12. Retries, backoff, quotas, and partial failure

Retry only transient transport failures and retryable provider responses (`408`, `429`, selected `5xx`) with truncated exponential backoff, full jitter, and `Retry-After` precedence. Defaults: at most 5 attempts, 30-second total command budget unless transfer timeout is explicitly larger. Calendar quota guidance requires exponential backoff; avoid wasteful patch calls when a get plus update is more quota-efficient (Calendar patch consumes three quota units).

For `401`, refresh once through the injected credential provider, then fail `AUTH_EXPIRED`. Do not retry `403` blindly: distinguish insufficient scope, policy/permission, rate/quota reasons, and daily limits. Never retry validation, approval, conflict, `404`, or destructive operations unless idempotency is proven.

Batch/bulk operations return per-item results and `PARTIAL_FAILURE` when mixed. They do not roll back successful Google operations. Stop launching new items after systemic auth/quota failure and report exact confirmed effects. Concurrency defaults conservatively (4 reads, 1 mutation per account) and honors service/user quota limits. No tight polling; watch/channel APIs or caller-controlled intervals are preferred.

## 13. Multi-account model and secret injection

Accounts are local aliases mapped to immutable Google subject IDs and display emails. Email is descriptive and may change. The account registry stores only non-secret metadata: alias, subject hash, email, granted scope names, credential pointer/reference, OAuth client profile name, timestamps, and status. There is no implicit global account when more than one active alias exists. `GOOGLE_WORKSPACE_ACCOUNT` may select an alias, but command input wins and output always states the resolved alias.

Secrets must be injected by the host runtime through a protected secret provider, file descriptor, or mode-0600 ephemeral file. Supported secret references may identify OAuth client configuration and refresh-token material, but the harness must not resolve plaintext from ordinary config. Never accept secrets in argv, JSON output, logs, provenance, cache, tests, or environment dumps. Access tokens live in memory only and are sent in the `Authorization` header, never query parameters. Ephemeral secret files are deleted promptly. Refresh-token rotation updates the protected provider through its API or fails safely; it is never copied into package state.

OAuth login uses authorization code with PKCE and state for a Desktop/installed client where appropriate, requests offline access only when needed, verifies returned scopes, and supports incremental authorization. Revocation and logout are distinct. Refresh tokens can expire or be revoked, so status cannot promise permanence.

## 14. Scope profiles

Profiles are named minimum practical sets; exact scopes are shown in preview and checked after consent. The implementation should permit a union of profiles without requesting every scope up front.

| Profile | Intended commands | Principal scopes |
|---|---|---|
| `identity` | status/whoami | `openid`, `email` plus narrow API profile endpoint scope as required |
| `gmail-metadata` | profile, message/thread metadata, labels/history | `gmail.metadata`, optionally `gmail.labels` for label mutation |
| `gmail-read` | message/thread/draft/attachment reads | `gmail.readonly` |
| `gmail-compose` | drafts and send | `gmail.compose` (or `gmail.send` for send-only) |
| `gmail-modify` | mailbox organization/trash/import as allowed | `gmail.modify`; `gmail.insert` for insert-only |
| `gmail-settings` | basic settings/filters | `gmail.settings.basic` |
| `gmail-sharing-admin` | forwarding/delegates where required | `gmail.settings.sharing`, service account plus domain-wide delegation/admin constraints |
| `gmail-permanent-delete` | immediate permanent message/thread delete only | `https://mail.google.com/` |
| `calendar-freebusy` | free/busy | `calendar.freebusy` or `calendar.events.freebusy` |
| `calendar-read` | calendars/events/settings reads | narrow combination of `calendar.events.readonly`, `calendar.calendarlist.readonly`, `calendar.calendars.readonly`, `calendar.settings.readonly`, `calendar.acls.readonly` as commands require |
| `calendar-events` | create/update/delete events | `calendar.events` or `calendar.events.owned` |
| `calendar-manage` | calendar list/calendars/ACL | narrow combination of `calendar.calendarlist`, `calendar.calendars`, `calendar.acls` |
| `drive-file` | app-created/user-selected file operations | `drive.file` (preferred) |
| `drive-metadata-read` | broad search/metadata | `drive.metadata.readonly` |
| `drive-read` | broad metadata/content reads | `drive.readonly` |
| `drive-manage` | broad file/permission/shared-drive management | `drive` |
| `drive-appdata` | harness-owned private app state if ever enabled | `drive.appdata`; not used for local secrets |

Gmail metadata/read/compose/modify and broad Drive scopes are restricted according to Google's published classifications; Gmail send is sensitive. Restricted-scope data stored or transmitted by a server can trigger verification/security-assessment obligations. The implementation must not market scope profiles as avoiding those obligations. `drive.file` is preferred but cannot satisfy arbitrary broad search unless files have been opened/shared with the app.

## 15. Audit, provenance, cache, and state

Each command emits provenance and may append a local JSONL audit record when an explicit audit sink is configured. Record: timestamp, harness/version, command, request ID, account alias/subject hash, scope profile names (not tokens), canonical input hash, target resource/principal IDs, safety classes, preview/confirmation digest, provider request/correlation IDs if returned, result/error code, confirmed effects, API/version, retry count, and transfer checksums. Do not record message bodies, attachment/file bytes, event descriptions, comment content, authorization URLs/codes, tokens, client secrets, channel tokens, or full sensitive query strings. Hash or redact emails in the durable audit sink unless operational policy explicitly permits them.

State root is explicit and private (`0700` directory, `0600` files):

- account metadata and protected credential references;
- idempotency records, effect previews, and ETag observations with TTL;
- OAuth state/PKCE only until callback completion;
- page/sync/history/change tokens tied to query fingerprint;
- resumable transfer metadata;
- watch channel stop metadata and expiration;
- optional sanitized audit JSONL.

No remote resource content is cached by default. Metadata cache is off by default for correctness-sensitive reads; if enabled, output includes `cache: {hit, ageMs, stale}`. Mutations invalidate related entries. Tokens/session URLs are bearer-like secret state and must use OS-protected storage or encryption; if unavailable, do not persist them. Cache corruption is recoverable by quarantine/reset, never by silently using malformed state. Account removal deletes its local state; remote revocation is separate.

## 16. Error taxonomy and exit codes

| Exit | Stable codes | Meaning |
|---:|---|---|
| 0 | none | success (`ok: true`), including a preview with no mutation |
| 2 | `INVALID_ARGUMENT`, `INVALID_MIME`, `INVALID_TIME_ZONE`, `INVALID_RECURRENCE` | local input/schema failure |
| 3 | `AUTH_REQUIRED`, `AUTH_EXPIRED`, `TOKEN_REVOKED`, `ACCOUNT_NOT_FOUND` | authentication/account failure |
| 4 | `INSUFFICIENT_SCOPE`, `PERMISSION_DENIED`, `POLICY_BLOCKED`, `APPROVAL_REQUIRED` | authorization or safety boundary |
| 5 | `NOT_FOUND` | remote/local target absent |
| 6 | `CONFLICT`, `PRECONDITION_FAILED`, `IDEMPOTENCY_CONFLICT`, `SYNC_TOKEN_EXPIRED` | state conflict/stale cursor |
| 7 | `QUOTA_EXCEEDED`, `RATE_LIMITED` | provider quota/rate limit |
| 8 | `TRANSIENT`, `TIMEOUT`, `NETWORK_ERROR` | retryable transport/provider failure exhausted |
| 9 | `PARTIAL_FAILURE`, `AMBIGUOUS_COMMIT` | some effects confirmed or final commit unknown |
| 10 | `LOCAL_IO_ERROR`, `CHECKSUM_MISMATCH`, `CACHE_CORRUPT` | local transfer/state failure |
| 11 | `PROVIDER_ERROR`, `UNSUPPORTED_BY_PROVIDER`, `UNSUPPORTED_BY_CONTRACT` | nonretryable provider/contract limitation |
| 12 | `INTERNAL_ERROR` | harness defect/invariant failure |

Map Google error `reason` as well as HTTP status. Preserve sanitized provider status/reason and request ID. Never expose raw response bodies if they may contain user content. An error after a mutation includes `effects` with only verified outcomes and a recovery action.

## 17. Test plan

### 17.1 Schema and manifest tests

- Validate both package metadata files against repository schemas and validate the harness manifest conventions already used by `clawpod-capability-registry`.
- Assert command name uniqueness, closed input schemas, required output envelope, `argMap` coverage, path roles, safety classes, and `requiresJson`.
- Snapshot the command inventory and scope/safety matrix so accidental feature loss fails CI.

### 17.2 Unit and mock HTTP tests

- Fake clock, deterministic jitter, and scripted HTTP transport for every command's representative success and documented error.
- Validate request URLs, escaping, headers, field masks, query syntax, pagination, all-drives flags, notification parameters, ETags, retries, and no-retry cases.
- Verify token refresh once, `Retry-After`, quota reason mapping, 410 sync reset, partial/batch failures, ambiguous send/create, and redaction.
- Assert stdout is one JSON object and stderr/audit/state contain no fixture secrets.

### 17.3 Fixtures

Checked-in synthetic fixtures only:

- Gmail multipart/alternative, nested MIME, Unicode headers, inline content IDs, large attachment metadata, malformed headers, base64url edge cases, reply/thread headers;
- Calendar timed/all-day events, DST gap/fold, recurring series, exceptions/cancellations, RRULE/RDATE/EXDATE, sync pages and 410;
- Drive binary/native files, folders, shortcuts, permissions, shared drives, comments/replies, revisions, changes, field masks, resumable 308 flows;
- Google error payloads for auth, scope, quota, rate, conflict, permission, abuse, unsupported export, and backend failure.

Fixtures contain unmistakable fake domains/content and no recorded production traffic.

### 17.4 Subprocess contract tests

Invoke the real entrypoint as a subprocess with temporary state/transfer roots. Cover typed flags and input JSON/stdin, exit-code mapping, atomic file writes, overwrite refusal, interruption/resume, timeout, signals, stdout purity, locale/time-zone independence, and paths with spaces/non-ASCII characters. Confirm CLI behavior matches every manifest `argMap`.

### 17.5 Adversarial and safety tests

- Header injection, MIME boundary collision, zip-bomb-like metadata, oversized arrays, invalid UTF-8, path traversal/symlink escape, hostile filenames, query/field-mask injection, and malicious webhook/channel values.
- Cross-account page token/idempotency/preview reuse, stale effect digest, changed ETag, account alias confusion, duplicate send after timeout, recurrence explosion, DST ambiguity, broad Drive corpus surprise, and notification default ambiguity.
- Secret canaries in token/client config ensure no argv, stdout, stderr, audit, exception, cache, or provenance leakage.
- Verify every `E`/`D` operation refuses execution without a fresh matching confirmation and dry-run makes zero mutating HTTP calls.

### 17.6 Real OAuth E2E (manual/protected CI only)

Use dedicated test Workspace accounts/project and protected secret injection. Never run on personal/production data. Test each scope profile incrementally, consent denial, refresh, expiry/revocation, multi-account isolation, Gmail draft/send to a controlled sink, Calendar create/update/recurrence/delete in a dedicated calendar, Drive upload/resume/download/export/share/revoke/trash/delete in a dedicated folder/shared drive, and channel start/stop against a test HTTPS receiver. Clean up by recorded IDs with explicit test-run authorization. Permanent-delete/ownership-transfer/admin-sharing suites are opt-in, isolated, and separately approved. Capture sanitized provider request IDs and resource IDs, not content or credentials.

## 18. Implementation phases (full scope retained)

1. **Foundation:** paired package skeletons, manifest/schema generation, stable envelope/errors, HTTP/auth injection interfaces, account model, audit/redaction, mock transport.
2. **Read-only core:** account status, Gmail read/labels/history, Calendar reads/instances/freebusy, Drive metadata/search/download/export/changes, pagination/partial fields.
3. **Recoverable creation and organization:** Gmail drafts/labels/trash, Calendar calendar/event writes, Drive create/upload/copy/move/trash; previews, ETags, idempotency, resumable transfers.
4. **External effects:** Gmail send and settings, Calendar attendees/ACL/watch, Drive permissions/comments/watch, channel lifecycle, exact notification controls.
5. **Destructive/admin surfaces:** permanent Gmail deletion, Calendar clear/delete/ownership transfer, Drive permanent delete/empty trash/revision/shared-drive deletion and ownership changes, hardened confirmations.
6. **Hardening and release:** adversarial/subprocess suites, protected real OAuth E2E, scope verification documentation, cross-platform tests, registry validation and package provenance.

A phase may ship behind explicit capability/version metadata, but the final implementation target remains the complete inventory above. Missing later-phase commands must return discoverable not-implemented capability metadata, not be silently omitted from design or help.

## 19. Residual design risks and decisions required

- **OAuth verification:** broad Gmail/Drive scopes may require restricted-scope verification and a security assessment. Product deployment model determines the obligation.
- **Admin functions:** Gmail sharing settings/delegation and Calendar ownership transfer have Workspace, service-account, domain-wide-delegation, and administrator constraints. A dedicated admin account profile and approval policy must be finalized before implementation.
- **Watch delivery:** the harness can create/stop channels but is not a webhook service. HTTPS/Pub/Sub receiver ownership, channel-token storage, renewal, validation, and event processing need a separate runtime design.
- **Secret persistence:** the host's protected credential-provider API and refresh-token rotation contract are not defined in this repository. Implementation must fail closed rather than invent plaintext storage.
- **Provider evolution:** discovery resources already include newer Drive surfaces and Calendar event types. Pin API versions and fixture behavior, and review upstream release notes before release.
- **Idempotency limits:** Gmail send and several create operations cannot guarantee exactly-once behavior after an ambiguous network failure. The contract intentionally reports ambiguity instead of retrying.
- **Scope versus utility:** `drive.file` is safest but cannot provide arbitrary full-Drive automation. Broad search requires restricted scopes and clear user consent.
- **Data minimization:** even read-only commands can expose highly sensitive mail/file/event content. Runtime display, retention, and downstream-agent boundaries need policy beyond CLI classification.

## 20. Authoritative sources

Accessed 2026-07-22. Google documentation is authoritative for provider semantics; this repository is authoritative for local package/manifest conventions.

- Gmail API overview: https://developers.google.com/workspace/gmail/api/guides
- Gmail REST v1 reference: https://developers.google.com/workspace/gmail/api/reference/rest
- Gmail OAuth scopes: https://developers.google.com/workspace/gmail/api/auth/scopes
- Calendar API overview: https://developers.google.com/workspace/calendar/api/guides/overview
- Calendar API v3 reference: https://developers.google.com/workspace/calendar/api/v3/reference
- Calendar OAuth scopes: https://developers.google.com/workspace/calendar/api/auth
- Drive API overview: https://developers.google.com/workspace/drive/api/guides/about-sdk
- Drive API v3 reference: https://developers.google.com/workspace/drive/api/reference/rest/v3
- Drive OAuth scopes: https://developers.google.com/workspace/drive/api/guides/api-specific-auth
- Google OAuth 2.0 overview: https://developers.google.com/identity/protocols/oauth2
- Repository conventions inspected: `README.md`, `schemas/capability.schema.json`, `schemas/package-metadata.schema.json`, `harnesses/clawpod-capability-registry/harness.json`, its paired `capability.json` files, `SKILL.md`, and package/repository tests.
