# Onboarding

## Interview

Ask in small groups, not as one wall of questions:

1. What images will be created or edited, and will outputs be raster, vector, typography-heavy, or enterprise-governed?
2. Which providers/models are preferred? Offer OpenAI, Vertex Imagen, BFL FLUX, Recraft, or defer.
3. What quality, latency, per-request budget, and compare-mode ceiling apply?
4. What account, billing, project, region, IAM, retention, residency, and training constraints apply?
5. What rights, real-person consent, brand, copyrighted-reference, and publication rules apply?

For each provider, explain required account and permissions, billing exposure, data transfer, revocation, and whether non-billable verification exists. Capture credentials directly through protected secret tooling. Never request plaintext credentials in ordinary chat.

## Provider credentials

- OpenAI: protected `OPENAI_API_KEY` binding.
- BFL: protected `BFL_API_KEY` binding.
- Recraft: protected `RECRAFT_API_KEY` binding.
- Vertex: ADC/OAuth/service-account lifecycle with project and location; do not substitute an API key.

Persist safe pointer and connection metadata only. Use per-run owner-scoped `secretRefs` with identical prepare/run mappings. Report `connected`, `configured_unverified`, `deferred`, or `revoked`.

## Step separation

Verification, paid generation, editing, comparison, publication, and external sharing are each their own prepared step — run each with its own digest in the same turn, without approval pauses.