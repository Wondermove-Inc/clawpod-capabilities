# Operations

## Browser-first connection

Run `onboarding.plan`, `onboarding.preflight`, `onboarding.status`, `auth.contract`, and `auth.status`, then open `https://claude.ai/design` with the desktop/browser capability. Readiness means the authenticated Design UI is visible and usable. Reuse the browser session. The human performs only missing sign-in, MFA, or provider consent. Default onboarding does not register an MCP endpoint, initiate Claude Code OAuth, request a setup token, or delegate CLI work.

## Typed 61-command surface

The Harness preserves 61 commands. It plans and guards browser work rather than pretending to execute provider mutations. Projects: list/get/search/create/update/iterate/comment/edit/present/share/export planning/diagnosis/verification/handoff/delete. Design systems: list/get/create/update/remix/publish/set-default/delete. Templates: list/get/create/update/delete. Code: browser login handoff and bidirectional sync. Destinations: list/handoff. Admin: status/permissions/usage/enable/role-update. System, onboarding, auth, browser input planning/verification/diagnosis, and optional MCP diagnostics complete the surface.

Read and mutation commands return `HUMAN_VERIFICATION` with the browser URL and reconciliation source. Perform the action through desktop/browser, preserve IDs/revisions, then verify list/detail, ACL, artifact, git, or organization state. Never convert the handoff itself into success.

## Exact browser input and long prompts

Start from a fresh browser snapshot and inspect the target's tag, role, and contenteditable state. Run `browser.input.plan --prompt ... --ref ...` with those observed semantics. The deterministic routing contract is:

- `input` and `textarea` use one `fill` action regardless of prompt length.
- Contenteditable targets use one `type` action only through 600 characters. Above 600 characters they use one ref-scoped `evaluate` action that replaces the contents with a text node and dispatches bubbling `input` and `change` events. Prompt content is serialized as a JSON string literal, so quotes, backslashes, newlines, Unicode, and markup remain inert text.
- Unsupported elements fail closed. If browser evaluate is disabled, long contenteditable input fails closed unless the browser exposes a separately supported paste action; repeated `type` calls are not a safe fallback.

After insertion, read the target's text/value through browser evaluate and run `browser.input.verify` with the original prompt and observed text. Submit only when exact equality passes; the reported character count and UTF-8 SHA-256 provide auditable supporting evidence. A mismatch is non-retry-safe and must never be submitted.

Refs are snapshot-scoped. If a ref is stale, take a fresh snapshot, redetect the same editable by accessible role/name and editable semantics, retry the selected input action once, and perform exact verification. If the action times out, inspect the current field content and browser status before choosing a retry. Use `browser.input.diagnose` to classify these failures. A timeout is not evidence of Gateway failure and never by itself authorizes restarting the Gateway; diagnose control-plane health independently.

## Exact effects and exports

Run `*.preview` with every intended field. Pass the unchanged `effect_digest`, identical fields, and `--approve` to `*.apply`. Changed fields invalidate the digest. Deletes require ID, exact displayed name, and explicit approval, followed by absence verification. Permission changes may take up to 15 minutes.

Before native PDF export, run `projects.export.plan --file-url ... --ui-filename ... --expected-pages ... --observed-slides ...`. The URL must contain exactly one non-empty `file` parameter whose bounded URL-decoded value exactly equals the active UI filename. Reject paths, non-`.dc.html` suffixes, literal Unicode escape placeholders, mojibake, and slide-count mismatches before opening Share. Use **Share → PDF → Print or Save as PDF**. A one-page iframe/browser print is not a full-deck export when multiple pages are expected. Supply `--preview-pages` when known and require an exact match.

Keep export execution in the foreground until the artifact is verified or a real provider blocker is established. If a browser, print-preview, filesystem, or other tool call errors or times out, return immediately to the same active `.dc.html` file and inspect the current browser or dialog state. Run `projects.export.diagnose` with the same identity/count inputs and `--provider-error` when applicable, then resume at the last verified step. A tool failure is not a terminal handoff: do not switch tasks, leave the export in the background, claim completion/failure, restart infrastructure, or select a fallback solely because the call failed. In Chrome print preview, traverse the preview shadow DOM to activate Save when ordinary browser refs cannot reach it. In the GTK Save File dialog, enter the exact destination path/name and activate Save. Verify the local file exists before artifact verification.

Run `projects.export.verify` with `--project-id`, `--provenance native-claude-design`, `--expected-pages`, and repeated `--qa-page` values covering every page. Success requires regular-file path, MIME, bytes, SHA-256, project ID, provenance, exact page-count match, and page-by-page visual QA. If native export genuinely fails only after checking Share → Export, a fallback renderer may be used but must be recorded as `fallback-rendering`; never present fallback output as native provenance. HTML and PPTX remain supported browser exports. HTML is active content. On timeout, browser loss, or ambiguous state, reopen the existing resource and inspect before retrying.

## Optional MCP diagnostics and verified defect, 2026-08-13

MCP is optional acceleration and has no effect on capability readiness. `mcp.inspect` performs bounded diagnostics only. `mcp.install-plan` and `mcp.remove-plan` never execute. Do not initiate MCP registration or OAuth during default onboarding. Use an MCP route only after a real read-only Claude Design tool call returns authorized provider data. CLI output showing transport `Connected` is not evidence that the tools are authorized.

Claude Code 2.1.229 was verified to send an OAuth `redirect_uri` rejected by the provider for the documented Design MCP transport. This can leave transport discovery looking connected while tool calls remain unauthorized. Treat this as a provider/client interoperability defect, do not loop OAuth, and continue through the logged-in browser. The observed endpoint and prior schema are diagnostic context only, not readiness dependencies.

A previously observed schema included project/file/comment/member operations, but omitted project deletion, design-system mutation, template/admin operations, and binary export. Even after MCP recovers, browser routing remains required for unsupported surfaces.

## Limits

Claude Design exposes no supported audit log. Browser selectors and provider UI can change, so verify source-of-truth state after every mutation. The Harness never inspects browser cookies or claims browser authentication on its own.

## Stale file-route recovery

Use `projects.reenter.plan` for attempt 1 and, only if needed, attempt 2. Browser performs the fresh project-list read and exact generated-result thumbnail selection; the Harness never clicks. Verify each observation with `projects.reenter.verify`, then classify the combined evidence with `projects.file_route.diagnose`. `provider_failure` requires two healthy, fresh-list, same-thumbnail attempts with independent file-serving 404 evidence. Browser/CDP failure is always `browser_failure`. Continue a recovered route from the last checkpoint through two full slide reviews and independent native PPTX/PDF verification and reflow comparison.
