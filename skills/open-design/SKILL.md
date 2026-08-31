---
name: open-design
description: "Use when the user asks for a designed deliverable to build, share, and iterate on — a deck, UI prototype, one-pager, or dashboard — living on the team's OpenDesign server as a clickable live-preview link: author the HTML, upload it, hand over the link, revise on feedback, and export HTML/ZIP or import Claude Design zips. Onboards with the server's Base URL and token. Use claude-design for claude.ai canvas editing, artifact-design for in-room artifacts, and Image Studio for stills."
---

# Open Design

Use a self-hosted OpenDesign daemon as the shared design workbench: the agent authors the HTML itself, the server stores it, renders a sandboxed preview, and exports it. The paired Harness (v0.2.1) is the only network surface — typed commands, a JSON envelope with a per-request evidence trail, and no response truncation. The API token travels only through the Gateway-injected `OPEN_DESIGN_API_TOKEN` environment; it never appears in arguments, state, chat, or logs.

## Onboarding (mandatory, in this order)

1. Immediately after installation, report **installed but not connected** and ask the user for the **agent-API Base URL** (it may carry a reverse-proxy prefix, e.g. `https://od.wondermove.local/agent-api`; whether the proxy keeps or substitutes the daemon's `/api` segment is auto-detected at config.set, overridable with `--api-style root|mapped`), the **web URL people open** (e.g. `https://od.wondermove.local`; defaults to the Base URL's origin without the prefix), and the **API token**. Route the token into the Gateway secret lane for `OPEN_DESIGN_API_TOKEN`; never echo it back, never accept it as a command argument.
2. Run `config.set --state-root <owner-only dir> --base-url <api url> [--web-base-url <web url>]` plus TLS trust: `--ca-cert-path` when a CA file exists, or `--insecure-tls-risk-accepted` — internal servers commonly run without verifiable certificates and this is a supported configuration, not an exception. The state stores only the URLs and TLS trust.
3. Run `health`. It reports the server version, whether the version matches the verified 0.20.x series, whether the token is injected, and — by probing with a deliberately wrong credential — **whether the daemon actually enforces its token**. If it reports `AUTH_NOT_ENFORCED`, tell the user plainly that the server currently accepts unauthenticated requests and that setting `OD_API_TOKEN` on the daemon is their action item; do not block onboarding on it.
4. Declare the capability `verified` only after one bounded read (`projects.list`) and one write round-trip (create a clearly named scratch project, `files.put` one small file — the Harness verifies a byte-identical read-back — then delete it with exact-name approval). Report what was created and deleted.
5. Full script and wording: [onboarding.md](references/onboarding.md).

## When to use / not use

Use it to produce and share designs that live on the OpenDesign server: decks, prototypes, one-pagers, dashboards — anything the agent can author as self-contained HTML. Do not use it for claude.ai/design canvas work (`claude-design`), for chat-room document artifacts (`artifact-design`), or for raster image generation (`clawpod-image-studio`).

## Working procedure

1. **Author first, upload second.** Write the deliverable as self-contained HTML in the workspace, following `artifact-design` craft (real typographic hierarchy, chosen palette, both themes where sensible). For decks, one `section.slide` per slide at a fixed slide size; run the deterministic layout gate from the `claude-design` Harness (`projects.qa.layout` with its capture script) before uploading, and revise until it passes.
2. `projects.create --name <user-recognizable name> --kind deck|prototype|document|dashboard` — the Harness generates the project UUID.
3. `files.put --project-id … --path <file>` for the HTML (and any assets, up to 12 per call, 25 MB each). Success requires the Harness's byte-identical read-back; treat anything else as failure.
4. `preview.link --project-id … --file <name>` and deliver the returned `webUrl` (built on the web URL, without the agent-API prefix) to the user (room message, or an `artifact-design` card when the room benefits). The link embeds a scope token and opens without the API token for anyone who can reach the server's network — say so when sharing beyond the room.
5. On revision requests, edit the local file, re-run the gate, `files.put` again (same name), and re-mint the preview link.
6. Files only on request: `export.html`/`export.archive` write local copies; `export.manifest` lists what the server can produce. Server-side PDF/PPTX are not available on the verified deployment (`slideRenderer:false`; PDF export is desktop-runtime only) — the user prints the preview to PDF, or imports into claude.ai/design. A Claude Design export `.zip` can be brought in with `import.claude-design`.
7. Details and worked calls: [workflow.md](references/workflow.md).

## Boundaries and approvals

- Everything visible on the server is shared: one daemon = one shared workspace with a single token; there is no per-agent isolation. Name projects so owners are obvious, and never delete or overwrite a project this session did not create without explicit user direction.
- `projects.delete` is destructive: exact displayed name plus `--approve`, only after user approval; the Harness verifies absence afterwards.
- `import.claude-design` and uploads create server-side state; keep them tied to the user's request. The preview URL is reachable by anyone on the server's network — treat sharing it outside the room as publication.

## Verification

- Onboarding: `health` evidence recorded (server version, authEnforced, token presence) plus the read and write round-trips above.
- Every upload: `roundTripVerified: true` in the response — never claim an upload succeeded without it.
- Delivery: the preview link opened (`opensWithoutToken` in the `preview.link` response) and was sent to the requested channel.
- Every response carries `data.evidence.requests` (method, path, status, duration); cite it when reporting.

## Failure handling

- `NOT_ONBOARDED` / `MALFORMED_STATE` → re-run onboarding from `config.set`.
- `AUTH_REJECTED` (exit 4) → the token no longer matches the daemon; ask the user to re-issue and update the secret. Never retry with guessed tokens.
- `TLS_VERIFY_FAILED` → re-run `config.set` with the CA file, or with `--insecure-tls-risk-accepted` for an internal server without one; never let certificate verification block an internal deployment the user asked to use.
- `UNREACHABLE` / `TIMEOUT` → check the network path once (the server may be down or the tailnet route broken); report with the evidence trail instead of looping.
- `VERIFY_FAILED` on upload → the server stored different bytes; do not continue to preview — re-upload once, then report.
- `UNVERIFIED_SERVER_VERSION` warning → proceed for reads, but re-validate the contract (docs/open-design-contract.md) before relying on writes if anything else misbehaves.
