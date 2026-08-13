# Operations

## Browser-first connection

Run `onboarding.plan`, `onboarding.preflight`, `onboarding.status`, `auth.contract`, and `auth.status`, then open `https://claude.ai/design` with the desktop/browser capability. Readiness means the authenticated Design UI is visible and usable. Reuse the browser session. The human performs only missing sign-in, MFA, or provider consent. Default onboarding does not register an MCP endpoint, initiate Claude Code OAuth, request a setup token, or delegate CLI work.

## Typed 56-command surface

The Harness preserves 56 commands. It plans and guards browser work rather than pretending to execute provider mutations. Projects: list/get/search/create/update/iterate/comment/edit/present/share/export/handoff/delete. Design systems: list/get/create/update/remix/publish/set-default/delete. Templates: list/get/create/update/delete. Code: browser login handoff and bidirectional sync. Destinations: list/handoff. Admin: status/permissions/usage/enable/role-update. System, onboarding, auth, export verification, and optional MCP diagnostics complete the surface.

Read and mutation commands return `HUMAN_VERIFICATION` with the browser URL and reconciliation source. Perform the action through desktop/browser, preserve IDs/revisions, then verify list/detail, ACL, artifact, git, or organization state. Never convert the handoff itself into success.

## Exact effects and exports

Run `*.preview` with every intended field. Pass the unchanged `effect_digest`, identical fields, and `--approve` to `*.apply`. Changed fields invalidate the digest. Deletes require ID, exact displayed name, and explicit approval, followed by absence verification. Permission changes may take up to 15 minutes.

For native PDF export, use **Share → Export → PDF → Download → Print or save as PDF**. Present and File menus are not authoritative export discovery surfaces, so their lack of an export item is not evidence that native export is unavailable. In the print preview, confirm the page count equals the expected full deck before saving.

Run `projects.export.verify` with `--project-id`, `--provenance native-claude-design`, `--expected-pages`, and repeated `--qa-page` values covering every page. Success requires regular-file path, MIME, bytes, SHA-256, project ID, provenance, exact page-count match, and page-by-page visual QA. If native export genuinely fails only after checking Share → Export, a fallback renderer may be used but must be recorded as `fallback-rendering`; never present fallback output as native provenance. HTML and PPTX remain supported browser exports. HTML is active content. On timeout, browser loss, or ambiguous state, reopen the existing resource and inspect before retrying.

## Optional MCP diagnostics and verified defect, 2026-08-13

MCP is optional acceleration and has no effect on capability readiness. `mcp.inspect` performs bounded diagnostics only. `mcp.install-plan` and `mcp.remove-plan` never execute. Do not initiate MCP registration or OAuth during default onboarding. Use an MCP route only after a real read-only Claude Design tool call returns authorized provider data. CLI output showing transport `Connected` is not evidence that the tools are authorized.

Claude Code 2.1.229 was verified to send an OAuth `redirect_uri` rejected by the provider for the documented Design MCP transport. This can leave transport discovery looking connected while tool calls remain unauthorized. Treat this as a provider/client interoperability defect, do not loop OAuth, and continue through the logged-in browser. The observed endpoint and prior schema are diagnostic context only, not readiness dependencies.

A previously observed schema included project/file/comment/member operations, but omitted project deletion, design-system mutation, template/admin operations, and binary export. Even after MCP recovers, browser routing remains required for unsupported surfaces.

## Limits

Claude Design exposes no supported audit log. Browser selectors and provider UI can change, so verify source-of-truth state after every mutation. The Harness never inspects browser cookies or claims browser authentication on its own.
