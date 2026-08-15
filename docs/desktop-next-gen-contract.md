# Desktop Skill + Harness 차세대 설치 단위 계약

- 상태: **3.0.0 candidate installed locally for validation, not published**
- canonical name: `desktop` (Skill과 Harness가 동일 이름을 공유)
- registry-first 결정: installed v2.0.0을 **REFINE**, Browser/Playwright/provider Harness와 **COMPOSE**, 새 capability 생성 아님
- 근거: `/workspace/desktop-audit/AUDIT.md` (2026-08-15)

## 1. Routing description candidate

> Use when native desktop, browser chrome, or an OS dialog must be observed and operated through the visible GUI. Can inspect accessible UI and windows, capture redacted evidence, perform human-paced pointer, keyboard, clipboard, drag/drop, file-dialog, and bounded task actions, then verify, recover, or resume them. Use the Browser tool or Playwright for DOM-first web work, node screen control for a specifically attached remote screen, and typed service APIs or provider Harnesses when they can perform the operation directly; compose Desktop only for native GUI handoffs. Never solve CAPTCHA or human verification, and gate secrets, external commitments, destructive actions, coordinates, process termination, and permissions at invocation time.

The Skill and Harness manifests MUST use this text byte-for-byte. It is a selection contract:

- **WHEN**: native desktop, browser chrome, or OS dialog requires visible GUI interaction.
- **CAN**: only the practical surfaces exposed by the Harness, with evidence and recovery.
- **BOUNDARY**: DOM-first web work → Browser/Playwright; attached remote screen → node screen; typed service action → direct API/provider Harness.
- **COMPOSITION**: Desktop accepts a guarded handoff when a typed/DOM workflow reaches native chrome, picker, permission, download, or inaccessible GUI.

### Routing examples

Positive:
1. “설정 앱에서 다크 모드를 켜고 결과를 확인해 줘.” → Desktop.
2. “브라우저 다운로드 창에서 파일을 저장하고 해시까지 확인해 줘.” → Browser may navigate DOM; Desktop handles browser chrome/native chooser; artifact verifier confirms file.
3. “이 앱의 Save As 대화상자에서 지정 폴더에 저장해 줘.” → Desktop file-dialog surface.
4. “접근성 트리가 없는 이미지 버튼을 화면에서 찾아 클릭해 줘.” → Desktop image localization, coordinate-class approval.

Nearby negatives:
1. “웹페이지 DOM의 표를 읽어 JSON으로 줘.” → Browser/Playwright, not Desktop unless DOM access fails and GUI fallback is explicitly chosen.
2. “Notion 페이지를 만들어 줘.” → Notion typed Harness, Desktop only if an unavoidable native authorization handoff is reached.
3. “이 PDF를 OCR해 줘.” → OCR capability, not Desktop.
4. “연결된 Android node 화면을 탭해 줘.” → node screen control, not the local Desktop Harness.

## 2. Installation and manifest alignment

One install transaction MUST contain:

- `skills/desktop/SKILL.md`
- `skills/desktop/capability.json`
- `harnesses/desktop/harness.json`
- `harnesses/desktop/capability.json`
- `harnesses/desktop/command_contracts.json`
- executable implementation, adapters, tests, and evidence documentation
- one registry entry named `desktop`

Invariants:

- one canonical name and one semantic version across Skill, Harness, capability manifests, CLI `--version`, schemas, and registry;
- description byte equality across Skill and Harness manifests;
- install/update is atomic; digest or validation mismatch rolls back the whole unit;
- no hidden “lite” command list: `capabilities` reports every practical backend action, availability, safety class, and reason when unavailable;
- unavailable backends fail closed, never silently emulate via a riskier backend;
- installation does not grant invocation approval.

## 3. Stable response envelope

Every `--json` command emits exactly one envelope on stdout. Human diagnostics go to stderr. JSON Schema uses draft 2020-12 and `additionalProperties: false` for stable objects; additive evolution requires a minor schema version.

```json
{
  "schemaVersion": "desktop.v3",
  "requestId": "req_...",
  "command": "task.run",
  "status": "succeeded|degraded|partial|blocked|failed|cancelled",
  "revision": 4,
  "result": {},
  "error": null,
  "warnings": [],
  "artifacts": [],
  "approval": null,
  "timing": {"startedAt": "...", "endedAt": "...", "durationMs": 123},
  "retry": {"attempt": 1, "maxAttempts": 3, "retryable": false}
}
```

Error object:

```json
{
  "code": "HUMAN_VERIFICATION",
  "message": "Automation stopped before the protected interaction.",
  "category": "policy",
  "retryable": false,
  "details": {},
  "remediation": "Complete verification manually, then resume with the checkpoint token."
}
```

Artifact entries contain `kind`, workspace-relative `path`, `sha256`, `bytes`, `mediaType`, `redaction`, and `createdAt`. Paths outside the run root are forbidden unless a typed file operation explicitly authorizes an approved root.

## 4. Exit behavior

| code | meaning |
|---:|---|
| 0 | succeeded, including idempotent replay |
| 10 | usage/schema error |
| 20 | target not found or stale selector |
| 21 | timeout |
| 22 | backend/session unavailable |
| 23 | application launch or owned-process failure |
| 24 | accessibility/AT-SPI failure |
| 30 | approval required or approval mismatch |
| 31 | policy refusal |
| 32 | human verification detected |
| 40 | partial failure with committed subresults |
| 41 | revision/idempotency conflict |
| 42 | cancelled |
| 50 | internal error |

`--help` and `--version` return 0. Status `degraded` returns 0 only when the requested operation completed and warnings do not weaken its safety guarantee. `partial` always returns 40 and lists committed and uncommitted steps.

## 5. Command inventory and typed arguments

All commands accept `--json`, `--request-id`, `--timeout-ms`, and backend selectors where applicable. Mutations accept `--idempotency-key`, `--expected-revision`, `--approval-file`, and `--dry-run`.

### Discovery and observation

- `version`, `help`, `capabilities`
- `environment.preflight --backend auto|x11|wayland --display STR --session STR`
- `session.list|get|open|close|recover`
- `app.list|get|launch|focus|close`
- `window.list|get|activate|move|resize|minimize|maximize|restore|close`
- `screen.list|capture`
- `ui.observe|find|read|table|wait|verify`
- `image.locate`
- `dialog.inspect`
- `clipboard.inspect`
- `task.get|events|artifacts`

Typed selectors use exactly one primary locator (`nodeId`, accessible `name`, `text`, `role`, image template, or coordinates), plus optional `appId`, `windowId`, `nth`, and expected bounding box/revision. Stable node IDs are session-scoped and carry observation revision.

### Interaction

- `pointer.click|double-click|right-click`
- `pointer.move|scroll|drag-drop`
- `keyboard.type|key|shortcut|select`
- `clipboard.read|write|clear`
- `dialog.respond`
- `file-dialog.open|save|choose-directory|cancel`
- `download.wait|inspect|move|quarantine`
- `image.click`
- `task.plan|preview|run|pause|resume|cancel|cleanup`

### Process and recovery

- `app.launch` creates an ownership record; `app.close` is graceful by default.
- `process.terminate` and `process.kill` are exposed, never hidden, but require owned PID identity, start-time match, unsaved-work inspection, exact preview, and force-class approval.
- `session.recover` reconciles owned processes, windows, checkpoint revision, committed steps, and artifacts before resuming.

Representative typed task step:

```json
{
  "stepId": "save-1",
  "action": {
    "kind": "file-dialog.save",
    "windowId": "win_123",
    "path": "reports/final.pdf",
    "approvedRoot": "/workspace/outputs",
    "collision": "fail"
  },
  "verify": {"kind": "file", "sha256": null, "minBytes": 1},
  "timeoutMs": 20000,
  "retry": {"maxAttempts": 2, "backoffMs": 500}
}
```

## 6. Session, task, idempotency, and concurrency

- Session state: `sessionId`, backend identity, display/monitor inventory, app/window/process ownership, policy snapshot, revision, lease expiry.
- Task state: `prepared → awaiting_approval → running → paused|blocked → succeeded|partial|failed|cancelled → cleaned`.
- Every mutation requires an idempotency key. Same key + same canonical request digest returns the original result; same key + different digest returns exit 41.
- `expectedRevision` prevents stale actions. Observation-derived actions include observed revision and target identity.
- One mutating lease per window/task. Competing writes fail with `RESOURCE_BUSY`; reads remain available.
- Resume requires checkpoint token + expected revision. It never repeats committed non-idempotent steps.
- Timeouts are per action and whole task. Timeout triggers observation and safe checkpointing, not blind retry.
- Retries are allowed only for typed retryable failures. External commitments, destructive actions, permission decisions, password entry, coordinate actions, and process kill are never automatically retried.
- Cancellation is cooperative first; forced cleanup is a separately approved action.

## 7. Partial failure and recovery contract

A partial result identifies:

- `committedSteps` with evidence and side effects;
- `failedStep` and stable error;
- `notRunSteps`;
- `rollbackAvailable`, rollback preview, and rollback limits;
- resumable `checkpointToken` (opaque, non-secret, expiry-bound).

Cleanup is idempotent and scoped to Harness-owned temporary files, leases, clipboard values, and launched processes. It MUST NOT close pre-existing apps, delete user files, clear unrelated clipboard content, or kill unowned processes. Crash recovery detects stale leases, validates PID start time, retains redacted evidence, and marks uncertain external effects as `outcomeUnknown`, requiring human review before retry.

## 8. Evidence and redaction

Each run root contains:

- `manifest.json` with schema, task digest, environment, versions, and artifact hashes;
- append-only `events.jsonl` with monotonic sequence and lifecycle events;
- redacted before/after observation JSON;
- redacted screenshots when policy permits;
- approvals as digest-bearing receipts without secret values;
- recovery and retry observations;
- final result envelope.

Default redaction covers password/secret/OTP fields, protected clipboard content, authorization headers/tokens, configured screen regions, and values injected from secret references. Secret text never appears in argv, task JSON, stdout/stderr, screenshots, accessibility dumps, clipboard evidence, or approval previews. Screenshot capture around sensitive fields is suppressed or masked before persistence.

## 9. Safety classes and invocation controls

| class | examples | default |
|---|---|---|
| S0 observe | app/window list, redacted observe, inspect | run |
| S1 reversible named action | focus, scroll, named toggle | run with verify |
| S2 sensitive/recoverable | clipboard write, file save, drag/drop, known safe dialog | exact preview, scoped confirmation |
| S3 external commitment | submit/send/purchase, financial/legal, production mutation | exact preview + explicit fresh approval |
| S4 destructive/privileged | delete/overwrite, permission grant, force close, terminate/kill | exact preview + explicit fresh approval + recovery statement |
| STOP | CAPTCHA, bot detection, human verification | never automate |

Approval receipt binds `requestDigest`, safety class, exact targets, app/window/domain/account, intended side effect, file/process identity, expiry, and one invocation. Material UI drift, target change, dialog change, revision change, or expiry invalidates approval.

### Exact preview requirements

- **Secret/password/OTP entry**: account/app/domain, destination field identity, source as secret reference only, whether submit follows. Protected injection only; no value display or logging. Fresh approval is required for password/OTP and any subsequent submit is a separate S3 action.
- **Submit/send**: recipient/destination, account, exact payload summary or attachment hashes, button/action label, irreversible consequences.
- **Purchase/financial/legal**: merchant/counterparty, currency and exact amount, item/terms/document hash, account, final action label. No approval bundling.
- **Production**: environment, resource IDs, operation, expected impact, rollback plan.
- **Destructive/file overwrite**: canonical path/resource identity, existing hash/size where available, deletion/overwrite scope, recovery availability.
- **Coordinate/image click**: fresh screenshot hash, monitor, DPI/scale, x/y or bbox, template hash/confidence, intended target, observed revision. Any display/layout change invalidates it.
- **Process terminate/kill**: PID, process start time, executable hash/path, ownership, windows, unsaved-work state, graceful attempt result, signal.
- **Dialogs/permissions**: dialog title/origin/app, exact permission and scope, selected button, persistence/duration. Unknown dialogs always stop.

### Human verification stop contract

On CAPTCHA, bot-detection, “prove you are human”, visual challenge, protected iframe, or equivalent signal:

1. stop before clicking, typing, image matching, OCR, or coordinate fallback;
2. emit exit 32 / `HUMAN_VERIFICATION`;
3. redact and record minimum evidence, detected signals, app/window/domain, and checkpoint;
4. release input control but keep a resumable, expiry-bound session;
5. ask the human to complete verification directly;
6. after human completion, re-observe and resume only non-verification steps with a fresh revision.

The Harness must not offer a bypass flag.

## 10. Browser, Playwright, node screen, and API composition

- Browser tool/Playwright owns DOM semantics, selectors, navigation, network-aware waits, tabs, and page content. Desktop owns browser chrome, native dialogs, OS permission prompts, inaccessible widgets, and explicit visual fallback.
- A Browser→Desktop handoff includes target URL origin, browser app/window identity, expected UI state, allowed GUI actions, and return condition. Desktop→Browser returns changed tab/window identity and verified state.
- Node screen control owns an explicitly attached remote/mobile screen. Local Desktop MUST NOT silently route to a node or claim remote-screen state.
- Direct APIs/provider Harnesses own typed service reads and writes. GUI imitation is fallback only when the direct surface cannot perform the requested step and the user accepts the weaker reliability/evidence model.
- OCR and Image Studio are separate semantic/image capabilities. Desktop may pass a screenshot artifact to OCR for reading, but deterministic target localization must not be represented as OCR, and neither may be used on human verification.

## 11. Test matrix

Every row requires deterministic local fixtures, network denied unless the test is explicitly an approved integration, JSON Schema validation, artifact hash verification, and cleanup assertions.

| area | required cases |
|---|---|
| app | launch/focus/graceful close, pre-existing vs owned, crash/relaunch, unsaved work |
| browser | DOM handoff, chrome, tabs/popups, download, native picker, browser crash |
| file | open/save-as/directory, traversal/symlink denial, overwrite/collision policies, hash/size |
| dialog | known modal, nested, permission, login/payment, unknown fail-closed, stale dialog |
| clipboard | text/html/image, prior-value ownership, secret redaction, clear-after-use, race |
| drag/drop | accessible targets, file drop, coordinate fallback, cancellation, verification |
| window | list/activate/move/resize/min/max/restore, z-order, multi-monitor, negative coords |
| image | exact/near match, scale/rotation rejection, false positive, template hash, CAPTCHA refusal |
| DPI | 100/125/150/200%, per-monitor scale, layout change invalidates approval |
| theme | light/dark/high contrast, image mismatch fail-closed |
| AT-SPI | unavailable, registry loss, stale/defunct node, recovery, no unsafe fallback |
| D-Bus | absent/degraded/reconnect, portal denied, explicit backend status |
| crash | Harness kill between action/verify, durable event replay, `outcomeUnknown` |
| retry | retryable transient, non-retryable commitment, backoff, max attempts |
| race | window closes, target moves, competing mutation lease, stale revision |
| timeout | action/task deadline, checkpoint, cancellation, cleanup budget |
| redaction | password/OTP/token, clipboard, screenshot masking, argv/env/log/event leakage |
| accessibility | keyboard-only, high contrast, IME/non-US, virtualized lists/tables |
| offline | all smoke fixtures local; any unexpected network access fails the test |

## 12. Contract tests

### Description/routing

- at least 3 positive and 2 nearby-negative prompts assert the expected primary capability and optional composition;
- CAPTCHA request routes to Desktop only to refuse/stop, never to image/OCR solving;
- direct provider mutation does not select Desktop as primary.

### Collision

- exactly one registry name `desktop`;
- Skill/Harness descriptions and versions are byte-equal;
- no aliases collide with Browser, Playwright, node screen, OCR, or provider commands;
- installing over an older linked unit is atomic and rollback-safe;
- an installed standalone binary without matching manifests is reported as drift, not silently adopted.

### Action surface

- `capabilities --json` inventory equals the union of executable dispatcher actions and `command_contracts.json`;
- every action has typed input/output schema, safety class, timeout, idempotency, evidence, and backend availability declaration;
- hidden backend methods capable of input, file mutation, clipboard access, process control, or permissions fail the test;
- all S2–S4 actions support dry-run exact preview; approval digest mutation fails;
- all STOP signals refuse across direct, task, image, OCR-handoff, and coordinate paths.

## 13. Skill Workshop update candidate procedure

This is prepared text only. Do not submit/apply it until implementation and adversarial tests prove the verbs.

1. Route native GUI/browser-chrome/OS-dialog work to Desktop only after checking for Browser/Playwright, node screen, or direct typed API as the safer primary path.
2. Preflight backend/session/display/AT-SPI/D-Bus/monitor state and report degraded or unavailable features explicitly.
3. Open or recover a revisioned session, observe, choose a stable accessible target, and prefer named actions over image/coordinate fallback.
4. Plan bounded actions with per-step verification, timeout, retry classification, idempotency key, evidence policy, and cleanup scope.
5. Produce exact previews and obtain fresh invocation approval for S2–S4 actions. Never log or preview secret values.
6. Execute observe → act → verify → recover with redacted lifecycle evidence. Do not automatically retry commitments or uncertain outcomes.
7. Stop immediately on CAPTCHA or human verification and issue a resumable human checkpoint.
8. On partial failure, report committed, failed, and unrun steps; never imply rollback when none occurred.
9. Return control to the composing capability with verified state and artifact hashes, then perform ownership-scoped cleanup.

## 14. Implementation gate

This design does not authorize live installation, publication, or a Skill Workshop update. The implementation card must:

1. implement manifests and executable surfaces under canonical `desktop`;
2. prove every CAN verb with tests;
3. run routing, collision, action-surface, safety, schema, offline, and full matrix tests;
4. revise the description downward if any practical surface is not verified;
5. only then prepare a guarded update/install review.
