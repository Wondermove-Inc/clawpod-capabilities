# ClawPod Image Studio

Portable, guarded CLI Harness for OpenAI Images, Vertex Imagen, BFL FLUX, and Recraft. Version 0.4.0 adds detached, bounded OpenAI generation jobs while preserving the legacy one-shot transport and the v0.3.0 offline professional production layer. Other providers remain offline/injectable only.

## Detached OpenAI generation

Use `job.start` for an approved OpenAI generation. It durably creates a local job and returns after a short worker bootstrap, while the detached worker owns one synchronous provider submission. `timeoutSeconds` is 60–300 seconds (default 300). The provider request receives the remaining deadline minus a 10-second validation and artifact-commit reserve, with zero retries. The legacy `image.generate` command alone retains its 45-second compatibility timeout.

Use `job.status` and `job.collect` with only the generated `jobId`. Both commands are deterministic, local, non-billable, credential-free, and never resubmit provider work. Timeout, transport loss, 5xx, malformed success, worker death, or termination after the write-ahead submission boundary remains non-retryable and ambiguous. A duplicate prepared digest is rejected with `PAID_JOB_EXISTS`; a new paid attempt requires a newly prepared and approved intent.

## Professional studio vertical slice

The local Studio commands cover the smallest complete production path:

`project.create` → `brief.save` → `brief.approve` → `shot.compile` →
`generation.register`/`candidate.register` → `qa.evaluate` → `critic.input` →
`select.record` → `revision.plan` → `finish.record` → `master.approve` →
`contact_sheet.create` → `delivery.prepare` → `delivery.package` → `audit.verify`.

Records live beneath `<root>/studio` and use schema version 1, stable prefixed IDs,
revisions, timestamps, immutable SHA-256 asset identity, and parent lineage. This is
an additive state layout: existing v0.2.0 connection, prepared-intent, compare, and
artifact files are read unchanged and need no migration. Candidate and generation
registration are offline: they inspect existing files beneath `<root>/artifacts` or
`<root>/studio/inputs` and never submit provider work. Unknown Shot Spec fields and
unsupported controls fail closed.

Contact sheets are deterministic SVG review proxies with exact JSON manifests.
Delivery preparation recomputes source hashes and requires active hash-bound master
approval. Packaging writes a normalized, byte-reproducible ZIP to an existing
durable root; externally visible delivery additionally requires a separate
publication approval identifier. Automated QA and critic payloads never create a
human approval.

## OpenAI production transport

Live transport remains disabled unless an approved run injects `OPENAI_API_KEY` as a protected runtime environment value. That injection automatically enables the OpenAI-only live path; explicit `CLAWPOD_IMAGE_STUDIO_TRANSPORT=openai-live` and `CLAWPOD_IMAGE_STUDIO_VERIFY=openai-live` overrides remain available for controlled runtimes. Never place the key in argv, input JSON, files, logs, or artifacts. `connection.verify` uses the documented non-billable `GET /v1/models/gpt-image-1` readiness check; it never generates an image. Without protected injection, keep the connection `configured_unverified`.

`image.generate` is the legacy synchronous compatibility command. It submits exactly one `POST /v1/images/generations` request with a 45-second HTTPS timeout and no automatic retry. It supports base64 and HTTPS URL results. A timeout, transport loss, 5xx, malformed success response, or failed result download after submission is potentially billable and is never retried automatically. Authentication and definite 4xx validation failures are classified as pre-acceptance. A new submission always requires a newly reviewed paid intent.

Paid calls require an unchanged prepared digest, binding digest, cost ceiling, and future expiry. OpenAI options are allowlisted and cannot override the approved model, prompt, or count. Gateway prepare and run must receive identical `secretRefs`; pointer IDs never belong in this package. Output paths are bounded beneath `<root>/artifacts`, symlinks and traversal are rejected, and artifacts include MIME, dimensions when detectable, SHA-256, provider/model/request provenance, and decode QA.

Fresh agents must run `onboarding.interview`, obtain approval before binding or verification, and use `connection.bind` with safe pointer metadata. All commands accept `--input-json OBJECT` and optional `--root PATH`, and return one redacted JSON envelope. Tests use injected HTTP openers and `mock-*` modes, never provider calls.
