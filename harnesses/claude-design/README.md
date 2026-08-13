# Claude Design Harness

Deterministic browser-first guardrails for Claude Design onboarding, auth/browser readiness, projects, sharing, exports, design systems, templates, code sync, destinations, and administration. The 56-command surface is preserved.

Provider execution defaults to the logged-in `https://claude.ai/design` UI through the desktop/browser capability. The Harness plans actions, emits exact browser handoffs and reconciliation sources, gates effects with SHA-256 digests, and verifies exported artifacts. It never fakes provider success or inspects browser credentials.

## Start

Run `onboarding.plan`, `onboarding.preflight`, `onboarding.status`, `auth.contract`, and `auth.status`, then verify the authenticated Design UI with desktop/browser. Reuse an existing session. The user handles only missing sign-in, MFA, or provider consent. MCP endpoint registration, Claude Code OAuth, setup tokens, and user-run CLI commands are not onboarding requirements.

## Optional MCP

`mcp.inspect` is bounded diagnostics. MCP is usable only after a real read-only Claude Design tool smoke returns authorized data. Transport `Connected` does not prove authorization. Claude Code 2.1.229 has a verified interoperability defect where its OAuth `redirect_uri` is rejected by the provider. This defect does not degrade browser readiness and must not trigger repeated OAuth attempts.

## Safety and verification

Externally visible and organization effects use `*.preview` then `*.apply` with the exact effect digest and `--approve`. Deletes require exact name and approval. Browser actions must be reconciled against provider state. Native PDF export uses Share → Export → PDF → Download → Print or save as PDF, with full-deck page count checked before save. Present/File menus alone cannot establish export unavailability. `projects.export.verify` requires artifact metadata, explicit native or fallback provenance, exact PDF page count, and page-by-page visual QA. HTML is active content.

See `command_contracts.json`, the Skill operations reference, and `TEST.md`.
