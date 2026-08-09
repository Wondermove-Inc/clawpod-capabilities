# Detached paid-image job contract

Status: implementation specification for ClawPod Image Studio after v0.3.0. This design does not authorize or perform a paid provider call.

## 1. Scope and provider semantics

OpenAI `POST /v1/images/generations` is synchronous: one HTTP request returns the generated image payload or URLs. OpenAI does not expose a provider-side image job that this Harness can poll after disconnect. Therefore this feature is a **local durable job around one synchronous paid submission**, not a claim that OpenAI provides async execution.

The v0.3.0 safety invariants remain mandatory: exact prepared intent and binding digests, future approval expiry, cost ceiling, one paid submission, no automatic retry, a bounded provider timeout, bounded artifact paths, and protected `OPENAI_API_KEY` runtime injection. The detached path must not reuse the synchronous compatibility command's 45-second request timeout. Existing `image.generate` may remain as a compatibility command; the detached path uses `job.start`, `job.status`, and `job.collect`.

## 2. Storage and identity

Jobs live under `<root>/jobs/<jobId>/`, where `jobId` is `job_` plus 32 lowercase hexadecimal characters. Callers may not choose a job ID.

Files:

- `state.json`: authoritative, redacted job record.
- `request.json`: immutable canonical approved payload needed by the worker. It contains the prepared and binding digests but no secret pointer or plaintext credential.
- `result.json`: terminal result metadata, never image bytes or credentials.
- `worker.pid`: advisory PID plus a Linux process start-time identity, never authoritative by itself.
- `artifacts/` is forbidden. Final bytes are atomically handed directly to the existing `<root>/artifacts` destination.

Every JSON mutation uses a same-directory mode-0600 temporary file, file `fsync`, `os.replace`, then parent-directory `fsync`. Job directories are mode 0700. Artifact writes retain v0.3.0 bounded-path and symlink checks and use the same durable replacement sequence. Readers either see the previous complete record or the next complete record, never partial JSON.

`state.json` includes: `schemaVersion`, `jobId`, `provider`, `operation`, `preparedDigest`, `bindingDigest`, `state`, `phase`, `billingState`, `automaticRetry:false`, `createdAt`, `updatedAt`, `deadlineAt`, `pidIdentity`, `providerRequestId` when known, `artifactPaths`, `error`, and monotonically increasing `revision`. It must not contain prompts, image bytes, environment values, secret references/pointers, authorization headers, provider response bodies, or exception strings that can include secrets.

## 3. Commands

All commands return the normal redacted Harness envelope. Unknown input fields fail closed.

### `job.start`

Input is exactly the existing approved `image.generate` input plus:

```json
{
  "operation": "generate",
  "provider": "openai",
  "model": "gpt-image-1",
  "prompt": "...",
  "count": 1,
  "output": "campaign/a.png",
  "format": "png",
  "options": {},
  "safetyPolicy": "...",
  "rightsPolicy": "...",
  "publicationPolicy": "...",
  "maxUsd": 0.04,
  "expiresAt": "...",
  "bindingDigest": "sha256:...",
  "preparedDigest": "sha256:...",
  "timeoutSeconds": 75
}
```

`timeoutSeconds` is optional, integer, 60 through 300, and controls the local worker wall clock. The detached provider request uses the remaining bounded worker deadline, minus a small artifact-commit reserve, rather than the synchronous compatibility command's fixed 45-second timeout. It is not part of the paid intent and never authorizes retry. No `secretRefs`, pointer, API key, retry count, provider job ID, arbitrary command, or absolute path is accepted.

Before spawning, `job.start`:

1. runs `assert_prepared` and all existing provider, operation, output, expiry, current binding, and cost checks;
2. requires OpenAI generation and a protected `OPENAI_API_KEY` already present only in the process environment;
3. creates `request.json` and `state.json` durably in state `queued`, billing state `not_submitted`;
4. starts the internal worker with a fixed executable/module and only `--root` and `--job-id`, using a new session/process group and closed unrelated file descriptors;
5. records PID identity atomically and verifies the child has not failed its bootstrap handshake.

Success returns HTTP/CLI success only after durable state exists and worker bootstrap is confirmed:

```json
{
  "jobId": "job_...",
  "state": "queued",
  "billingState": "not_submitted",
  "automaticRetry": false,
  "statusCommand": "job.status",
  "collectCommand": "job.collect"
}
```

Calling `job.start` is the single paid-action boundary. It never deduplicates by prepared digest: an existing job for that digest causes `PAID_JOB_EXISTS`, with its job ID and state, rather than another submission. A new paid attempt requires a newly prepared and approved intent.

If spawn/bootstrap fails before the worker can enter submission, start records terminal `failed`, `billingState:not_submitted`. It never silently falls back to synchronous execution.

### `job.status`

Input:

```json
{"jobId":"job_..."}
```

This command is local and non-billable. It never requires or resolves a credential and never contacts OpenAI. It returns the authoritative record subset:

```json
{
  "jobId":"job_...",
  "state":"running",
  "phase":"provider_request",
  "billingState":"unknown",
  "terminal":false,
  "automaticRetry":false,
  "createdAt":"...",
  "updatedAt":"...",
  "deadlineAt":"..."
}
```

Before returning, status performs bounded recovery. If a nonterminal worker is absent, its PID identity was reused, or its deadline plus a 5-second kill grace elapsed, status atomically transitions it according to section 5. Status may terminate an over-deadline process group with TERM then KILL, but never starts or resubmits work.

### `job.collect`

Input:

```json
{"jobId":"job_..."}
```

Collect is local, non-billable, credential-free, and idempotent. It first performs the same bounded recovery as status.

- `succeeded`: returns the same artifact/provenance shape as `image.generate`, reading terminal metadata and re-inspecting each bounded artifact. It verifies expected path, regular-file/no-symlink status, MIME/decode, size, and SHA-256. Hash mismatch or missing bytes returns `ARTIFACT_INVALID` without changing a successful paid submission into retryable work.
- `failed`, `ambiguous`, or `cancelled`: returns the recorded sanitized terminal error, billing state, provider request ID if known, and `automaticRetry:false`.
- nonterminal: returns `JOB_NOT_READY` with current state and `retryable:true`, where retryable means only “poll this same local job again,” never “repeat the paid submission.”

Collect does not move, copy, delete, publish, or register professional-studio artifacts. The worker's atomic write to the approved artifact destination is the handoff. `generation.register` remains a separate explicit offline action.

## 4. State machine

States and legal transitions:

```text
queued -> running -> succeeded
queued -> failed
queued -> cancelled
running -> failed
running -> ambiguous
running -> succeeded
```

No terminal state transitions to a nonterminal state. There is no retry transition.

`phase` refines `running`:

```text
bootstrap -> preflight -> provider_request -> provider_response -> artifact_commit
```

Billing mapping:

- `queued`, `bootstrap`, `preflight`: `not_submitted`.
- Immediately **before** the network opener can be invoked, persist `running/provider_request` with `billingState:unknown`; this conservative write-ahead boundary prevents a crash from causing a duplicate paid call.
- Definite OpenAI 401, 403, 429, or other documented 4xx rejection: terminal `failed/not_accepted`.
- HTTP success received: `accepted`; malformed JSON, unexpected count, invalid base64/MIME, unsafe URL, download failure, or artifact commit failure remains accepted or `accepted_output_unavailable`, never retryable.
- Timeout, connection loss, 5xx, worker death, host crash, or forced termination after the write-ahead boundary: terminal `ambiguous/unknown`, unless a successful response had already established `accepted`.
- `succeeded`: `accepted`; provider-reported actual cost remains null/unreconciled when absent.

The worker writes the provider request ID as soon as available. Its absence is not proof of non-acceptance.

## 5. Timeout and process ownership

The detached worker owns `timeoutSeconds` using a monotonic deadline and passes the remaining bounded provider budget to the HTTP transport. Reserve at least 10 seconds for response validation and artifact commit, so a 300-second job permits at most about 290 seconds in the provider request. The transport performs zero retries. The synchronous `image.generate` compatibility path may retain its existing 45-second timeout, but `job.start` must not inherit it. The parent `job.start` owns only a short bootstrap timeout (5 seconds). `job.status` and `job.collect` own recovery/termination of a worker beyond its recorded deadline.

The worker runs in a new session/process group so the invoking CLI may exit without sending it a terminal signal. It closes stdin and redirects stdout/stderr to `/dev/null` or a bounded sanitized diagnostic file. It installs TERM handling that records the safest terminal billing classification before exit. PID checks include process start identity to prevent signaling a reused PID. Only the recorded process group is signaled.

If the wall deadline occurs before `provider_request`, the job is `failed/not_submitted`. At or after `provider_request`, it is `ambiguous/unknown`, or `failed/accepted_output_unavailable` if acceptance was already established. A deadline never authorizes a second request.

## 6. Crash recovery

There is intentionally no automatic daemon and no provider polling for OpenAI. Recovery occurs on `job.status`, `job.collect`, or a future explicit local reconciler.

- Missing/corrupt `request.json` before submission: `failed/not_submitted`.
- Missing worker while `queued`: `failed/not_submitted` only when the durable phase proves the provider boundary was not crossed.
- Missing worker in `provider_request`: `ambiguous/unknown`.
- Missing worker in `provider_response` or `artifact_commit`: terminal failure with `accepted_output_unavailable` unless all expected artifacts and hashes validate, in which case recovery may finalize `succeeded` without network access.
- Corrupt `state.json`: `STATE_INVALID`; preserve files for operator inspection and never resubmit.
- Orphan temporary files are ignored and may be removed locally. They are never treated as completed state or artifacts.

Because OpenAI exposes no retrieval job for this synchronous operation, an ambiguous submission cannot be collected from OpenAI. Reconciliation uses the original request ID when available and billing/account records outside this command; otherwise it remains ambiguous.

## 7. Protected credential contract

The gateway resolves the approved owner-scoped secret for the `job.start` invocation only and injects it as `OPENAI_API_KEY`. The child inherits that environment directly from its trusted parent. The key is never passed through argv, JSON, files, logs, exceptions, process titles, job state, or artifact metadata. The worker removes `OPENAI_API_KEY` from its environment immediately after constructing the in-memory Authorization header and before decoding or persisting results.

`request.json` stores only `bindingDigest`. The worker revalidates that digest against current local connection metadata and verifies the prepared intent has not expired before crossing the provider boundary. Credential unavailable, binding changed, or expiry reached is terminal `failed/not_submitted`.

`job.status` and `job.collect` must work after the secret-use grant has expired and must not request secret injection.

## 8. Artifact and error behavior

Provider bytes are first written to same-directory temporary files under the already-approved artifact parent, decoded and inspected, then atomically renamed. For multiple outputs, all temporary files are validated first; terminal success is written only after every final file and the artifact directory are fsynced. A partial final set is recorded as `accepted_output_unavailable`, with existing files listed for safe manual inspection, not as success.

Errors persist only stable codes and allowlisted details such as HTTP status, phase, billing state, and provider request ID. Raw provider bodies, URLs containing query credentials, headers, prompts, filesystem environment, and arbitrary exception text are forbidden. Normal envelope redaction remains defense in depth.

## 9. Required tests, all non-billable

Use injected openers, fake clocks/processes, temporary roots, and `mock-*` transport only.

1. Start rejects changed/expired prepared intent, binding mismatch, absent protected environment, unsupported provider/operation, unsafe output, invalid timeout, and unknown fields before spawning.
2. Start durably writes queued state, spawns exactly once with fixed argv/new session/closed FDs, returns promptly, and never places the key or pointer in argv/files/output/logs.
3. Duplicate prepared digest is rejected while queued, running, succeeded, failed-not-accepted, and ambiguous; no second opener call occurs.
4. Worker transitions through legal revisions and invokes the opener exactly once.
5. 401/403/429/definite 4xx become failed/not_accepted; timeout, URL error, 5xx, malformed response, worker death, and kill after provider boundary become non-retryable ambiguous/unknown.
6. Success commits inspected artifacts atomically with exact hashes/provenance, then collect is idempotent and performs no network or credential access.
7. Crash points after every atomic write recover conservatively; before provider boundary is not_submitted, at/after it is ambiguous unless accepted artifacts can be proven complete.
8. Wall-clock timeout uses monotonic time, TERM/KILL targets only the matching process group identity, and PID reuse is never signaled.
9. Torn JSON/temp files, symlinks, traversal, corrupt images, partial multi-output commit, missing artifacts, and hash mismatch fail closed without resubmission.
10. State/result/error fixtures and every CLI envelope pass secret-canary scans, including raw key, bearer header, pointer ID, prompt, and signed URL query.
11. `job.status` and `job.collect` work with `OPENAI_API_KEY` absent and make zero network calls.
12. Existing v0.3.0 synchronous, onboarding, professional-studio, registry, and validator tests remain green.

No test may call a live provider or use a real credential. A later non-billable smoke may exercise only local lifecycle with a mock worker/transport.
