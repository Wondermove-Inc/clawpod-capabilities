---
name: "clawpod-image-studio"
description: "Create, edit, compare, onboard, and QA images across OpenAI, Vertex Imagen, BFL FLUX, and Recraft."
---

# ClawPod Image Studio

Use the linked `clawpod-image-studio` Harness v0.2.0. Treat the Skill and Harness as one installation unit with the canonical title **ClawPod Image Studio**.

## Immediate post-install onboarding

Immediately after installation, say: **“ClawPod Image Studio is installed but not yet connected.”** Start the onboarding interview in `references/onboarding.md`; do not wait for first use or a provider error.

1. Run `provider.list`, `provider.requirements`, and `onboarding.interview` without credentials.
2. Ask about intended uses, raster/vector/editing needs, quality and latency, preferred providers/models, budget per request and compare ceiling, data residency/retention constraints, rights and real-person policy, and publication plans.
3. Explain provider account, billing, data transfer, permissions, model choices, and revocation before connecting it.
4. Ask which providers to connect now or defer. Recommend only providers that fit the answers.
5. Obtain explicit approval before credential capture. Capture API keys only with protected secret tooling, never ordinary chat, prompts, argv, files, logs, fixtures, artifacts, or child prompts.
6. Store only owner-scoped pointer metadata. Vertex keeps its ADC/OAuth/service-account lifecycle and must not be converted to an API-key flow.
7. Configure bindings with `connection.bind`. With separate secret-use and network-read approval, use identical per-run `secretRefs` for prepare and run. For OpenAI, inject `OPENAI_API_KEY` only as a protected runtime environment value and use `connection.verify` with the documented non-billable model-readiness read. Never put the key in argv/input/files/logs or generate media merely to test it. Providers without an implemented documented check remain `configured_unverified`.
8. Report each provider as `connected`, `configured_unverified`, `deferred`, or `revoked`. State that connection does not authorize paid generation, editing, comparison, publication, or sharing.

## Provider routing

Run `provider.list` and `provider.requirements`, then select:

- **Recraft** for SVG/vector, logos, icons, illustration, mockups, or design-system assets.
- **Vertex Imagen** for Google Cloud IAM, project/region governance, SynthID, or enterprise RAI requirements.
- **BFL FLUX** for explicit FLUX models, photorealism, control/reference workflows, or async jobs.
- **OpenAI Images** for general generation, multi-image work, mask editing, and no stronger differentiator.

Honor an explicit compatible provider/model. Never silently substitute after approval. Read `references/providers.md` for provider differences and authentication.

## Production workflow

1. Clarify the target, audience, intended use, dimensions/aspect, raster or vector output, references, edit mask, rights, real-person consent, publication plan, deadline, and budget.
2. Call `request.validate`, then `request.estimate`. Do not infer unsupported provider options.
3. For multi-provider comparison, use `image.compare` only after validating every leg. Cap provider count and total outputs; show aggregate and per-leg costs.
4. Call `request.prepare`. Present provider, model, operation, prompt/reference digests, count, dimensions, quality/options, destination, pricing snapshot, estimate range, maximum USD, secret-binding metadata, expiry, and approval digest.
5. Obtain exact approval for credential use and paid external generation. Any material change requires a fresh preparation and approval.
6. Pass the unchanged prepared digest and identical owner-scoped `secretRefs` to the run command. For the current production path, protected `OPENAI_API_KEY` injection automatically enables only the approved OpenAI generation path. Never put plaintext credentials in Harness input.
7. For async providers, track the original job through `job.status` and `job.collect`; do not resubmit because polling or webhook delivery failed.
8. Inspect every artifact with `artifact.inspect`. Verify decode, MIME, dimensions, SHA-256, alpha/SVG validity, provider/model provenance, safety metadata, and reconciled cost.
9. Store durable deliverables only under an approved shared-storage artifact root. Do not claim durable delivery when shared storage is unavailable.
10. Treat publication or external sharing as a separate approval and action.

## Safety and paid retries

Read `references/safety.md` before real-person work, public-figure or political imagery, copyrighted/trademarked references, adult content, high-impact use, or publication.

- Require separate rights, consent, safety, and publication decisions.
- Block non-consensual intimate imagery, sexual content involving minors, deceptive impersonation, credential imagery, and unlawful use.
- Provider acceptance is not publication approval.
- Never automatically retry after possible paid acceptance. OpenAI timeout, connection loss, 5xx, malformed success response, and result-download failure are ambiguous or already accepted. Mark billing state accordingly and reconcile the original request ID when available.
- Retry only a documented pre-acceptance non-billable transport failure. A new paid submission needs a fresh estimate and approval.
- Stop on stale pricing, changed intent, changed secret binding, budget overrun, safety rejection, path escape, corrupt output, or provider-contract drift.

## Completion

Report provider/model, operation, artifact paths and hashes, dimensions/MIME, provenance and safety state, estimate and provider-reported billed cost when available (otherwise mark cost unreconciled), retry safety, approval/publication state, and remaining limitations. The capability is operational only for providers that passed onboarding and documented verification; otherwise report installed-but-not-connected or configured-unverified.
