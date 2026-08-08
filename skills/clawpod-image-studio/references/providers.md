# Providers

| Provider | Prefer for | Authentication | Execution notes |
|---|---|---|---|
| OpenAI Images | General generation, mask editing, multi-image inputs | `OPENAI_API_KEY` | Treat paid POST acceptance as non-repeatable when ambiguous |
| Vertex Imagen | IAM, region, SynthID, enterprise RAI | ADC/OAuth/service account | Require project, location, billing, and IAM selection |
| BFL FLUX | FLUX models, photorealism, controls, references | `BFL_API_KEY` | Preserve original async job ID and collect short-lived results promptly |
| Recraft | SVG/vector, logos, icons, illustration, mockups | `RECRAFT_API_KEY` | Enforce raster/vector endpoint and output compatibility |

Use `provider.requirements` and current pricing snapshots before preparation. Provider-specific options must fail closed when unsupported; never silently drop them. Ideogram remains a later typography-specialist candidate, not a v0.1.0 provider.