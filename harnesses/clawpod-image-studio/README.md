# ClawPod Image Studio

Portable, offline-first CLI Harness for OpenAI Images, Vertex Imagen, BFL FLUX, and Recraft. It validates and estimates requests without network access, routes by capability, records pointer-only provider bindings, prepares exact budget/expiry/binding-bound paid intents, and writes provenance-bearing artifacts only through injected transports.

## Safety contract

Live transport is disabled by default. Paid calls require an unchanged prepared digest, unchanged owner-scoped binding digest, budget ceiling, and future expiry. Gateway prepare and run must receive identical `secretRefs`; pointer IDs never belong in this package. Vertex preserves ADC/OAuth/service-account IAM, project, and location configuration rather than accepting an API-key shortcut. An ambiguous paid response is not retryable automatically.

Fresh agents must run `onboarding.interview`, obtain approval before credential binding or verification, use `connection.bind` with safe pointer metadata (or Vertex governance fields), and perform only explicit non-billable verification. Until that succeeds the state remains `configured_unverified`, not live-ready.

All commands accept `--input-json OBJECT` and optional `--root PATH`, and return one redacted JSON envelope. Tests use `CLAWPOD_IMAGE_STUDIO_TRANSPORT=mock-*`; production adapters are intentionally not bundled in v0.1.0.
