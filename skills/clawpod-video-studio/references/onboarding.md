# Provider onboarding

Run live `provider.requirements`; do not infer availability from installation. Baseline profiles include keyless/local, stock media, image/video gateways, direct video providers, speech/audio, music, and optional local GPU services. Ask which profiles or named providers to connect and permit independent defer/revoke states.

Accept credentials only after explicit approval and route every value directly to protected secret storage. Call `connection.configure` with pointer IDs plus the intended environment variable or mode-0600 secret-file variable. Never pass or persist values in `inputJson`, argv, `.env`, ordinary files, logs, artifacts, reports, tests, or child-agent prompts. The agent must use scoped secret resolution/injection only for the separately approved verification or execution process.

Built-in non-billable read verification adapters exist for OpenAI, Google, ElevenLabs, Pexels, Unsplash, and xAI. Each requires separate secret-use and network-read approval. Record `connected` only after a successful adapter response, `invalid` on an explicit authorization rejection, and `configured_unverified` when no reviewed endpoint exists. Never generate media to verify a credential. Preserve independent `missing_companion_field`, `deferred`, and `revoked` states.

Supported execution profiles include keyless, fal, OpenAI, Google, ElevenLabs, Kling, Runway, HeyGen, Pexels, Pixabay, Unsplash, xAI, Suno, Volcengine, Azure Speech, DashScope, Doubao Speech, Freesound, Higgsfield, Replicate, Modal endpoint injection, Hugging Face, NARA, Coverr, Pond5, and Videvo. Multi-provider selector tools require an explicit selected profile before approval.

Explain provider permissions, network destinations, data-retention/billing exposure, exact execution approvals, provider-console revocation, local binding removal, and protected-secret deletion as separate actions. Installation is not operational cloud readiness.
