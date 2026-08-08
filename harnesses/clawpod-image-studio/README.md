# ClawPod Image Studio

Portable, guarded CLI Harness for OpenAI Images, Vertex Imagen, BFL FLUX, and Recraft. Version 0.2.0 adds the first production transport, one-shot OpenAI image generation. Other providers remain offline/injectable only.

## OpenAI production transport

Live transport remains disabled unless an approved run injects `OPENAI_API_KEY` as a protected runtime environment value. That injection automatically enables the OpenAI-only live path; explicit `CLAWPOD_IMAGE_STUDIO_TRANSPORT=openai-live` and `CLAWPOD_IMAGE_STUDIO_VERIFY=openai-live` overrides remain available for controlled runtimes. Never place the key in argv, input JSON, files, logs, or artifacts. `connection.verify` uses the documented non-billable `GET /v1/models/gpt-image-1` readiness check; it never generates an image. Without protected injection, keep the connection `configured_unverified`.

`image.generate` submits exactly one `POST /v1/images/generations` request with a 45-second HTTPS timeout and no automatic retry. It supports base64 and HTTPS URL results. A timeout, transport loss, 5xx, malformed success response, or failed result download after submission is potentially billable and is never retried automatically. Authentication and definite 4xx validation failures are classified as pre-acceptance. A new submission always requires a newly reviewed paid intent.

Paid calls require an unchanged prepared digest, binding digest, cost ceiling, and future expiry. OpenAI options are allowlisted and cannot override the approved model, prompt, or count. Gateway prepare and run must receive identical `secretRefs`; pointer IDs never belong in this package. Output paths are bounded beneath `<root>/artifacts`, symlinks and traversal are rejected, and artifacts include MIME, dimensions when detectable, SHA-256, provider/model/request provenance, and decode QA.

Fresh agents must run `onboarding.interview`, obtain approval before binding or verification, and use `connection.bind` with safe pointer metadata. All commands accept `--input-json OBJECT` and optional `--root PATH`, and return one redacted JSON envelope. Tests use injected HTTP openers and `mock-*` modes, never provider calls.
