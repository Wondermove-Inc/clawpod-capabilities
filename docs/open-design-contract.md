# OpenDesign daemon contract (verified v0.20.3, 2026-08-31)

Captured from the live self-hosted deployment (nginx 80→443, self-signed TLS) and the `nexu-io/open-design` daemon source. The `open-design` Harness 0.1.0 encodes exactly this surface.

## Auth
- Single shared token: `Authorization: Bearer <OD_API_TOKEN>` (or Basic `open-design:<token>`). No accounts/workspaces without the vendor's Vela cloud.
- When the daemon's `OD_API_TOKEN` env is unset, **every request is accepted** — the Harness `health` command detects this by probing with a wrong credential and reports `AUTH_NOT_ENFORCED`.

## Endpoints used
| Purpose | Endpoint | Notes |
|---|---|---|
| Version | `GET /api/version` | `{version:{version, capabilities:{slideRenderer}}}` |
| Catalogs | `GET /api/skills·design-templates·design-systems·plugins·agents` | read-only |
| Projects | `GET /api/projects`, `GET/DELETE /api/projects/:id`, `POST /api/projects` | create **requires a client-generated UUID `id`**; body `{id,name,metadata:{kind,nameSource},skipDiscoveryBrief}` |
| Files | `GET /api/projects/:id/files` (with `artifactManifest.exports`), `GET /api/projects/:id/files/:name` (raw), `POST /api/projects/:id/upload` (multipart field **`files`**, max 12), `DELETE …/files/:name`, `POST …/files/rename` | |
| Preview | `GET /api/projects/:id/preview-url?file=<name>` → `{url, csp}`; the relative `url` embeds a scope token and **opens without the API token** | omit `file` ⇒ expects `index.html` |
| Export | `POST /api/projects/:id/export/html` (`{fileName}` → raw HTML), `GET /api/projects/:id/archive` (ZIP), `GET /api/projects/:id/export/manifest` | `POST …/export/pdf` → **501 desktop-runtime only**; PPTX gated on `slideRenderer` (false on this deployment) |
| Import | `POST /api/import/claude-design` (multipart field **`file`**, a Claude Design export `.zip`) | creates a project |

## Behaviors verified live (write round-trip, operator-approved)
create → upload → byte-identical read-back → scoped preview URL (200 without token) → export html/zip/manifest → delete → 404. Preview iframe CSP: `sandbox allow-scripts allow-forms; default-src 'self' data: blob:` — external CDNs do not load inside previews.

## Known limits
- One daemon = one shared workspace; isolation requires one daemon per org (deployment concern, out of capability scope).
- Server-side PDF/PPTX unavailable here; deliver the preview link (browser print for PDF) or export HTML/ZIP.
- Upstream moves fast; on `UNVERIFIED_SERVER_VERSION` re-check this file against the running server before trusting writes.
