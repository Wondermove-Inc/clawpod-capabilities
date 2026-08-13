# Operations

## Connection

Run `onboarding.plan`, `onboarding.preflight`, `onboarding.status`, `auth.contract`, and `mcp.inspect`. With explicit approval, the user runs `/design-login` inside Claude Code and completes sign-in/MFA/consent. Do not run slash commands in a shell. An optional setup token is generated interactively with `claude setup-token`, protected outside argv/files, and never treated as authorization merely because it exists.

`mcp.inspect` may run bounded `claude mcp list`. `mcp.validate` remains unavailable until a live configured name and tool schema are observed. `mcp.install-plan` accepts only an observed official command or URL. `mcp.remove-plan` previews removal by exact configured name. Neither executes configuration changes.

## Typed surface

Projects: list/get/search/create/update/iterate/comment/edit/present/share/export/handoff/delete. Design systems: list/get/create/update/remix/publish/set-default/delete. Templates: list/get/create/update/delete. Code: login and bidirectional sync. Destinations: list and handoff. Admin: status/permissions/usage/enable/role-update.

Read and mutation commands return `HUMAN_VERIFICATION` until a verified official MCP schema supports execution. Follow the exact handoff, preserve IDs/revisions, and reconcile against list/detail, ACL, artifact, git, or organization source of truth. Never convert a handoff into a success claim.

## Exact effects

Run a `*.preview` command with every intended field. Pass its unchanged `effect_digest`, identical fields, and `--approve` to `*.apply`. Any changed field invalidates the digest. Sharing, comments in shared work, destinations, sync, publish/default, enablement, and role updates are external effects.

Delete requires resource ID, exact displayed name, and explicit approval, then absence verification. Permission changes may require up to 15 minutes before refresh/readback. Claude Design has no audit-log support.

## Exports and recovery

Supported documented formats are HTML, PPTX, and PDF. After browser export, run `projects.export.verify` for regular-file path, MIME, bytes, and SHA-256. HTML is active content. On generation timeout, browser loss, or ambiguous saving, reopen by existing ID and inspect before retry. On ambiguous ACL/admin/sync effects, read source of truth and never reapply blindly.

## Verified official MCP, 2026-08-13

Install at user scope with `claude mcp add --scope user --transport http claude-design https://api.anthropic.com/v1/design/mcp`. Authentication follows the active Claude login; never invent another endpoint.

Verified tools: `ack_comments`, `add_member`, `copy_files`, `create_project`, `create_support_js`, `delete_files`, `finalize_plan`, `get_claude_design_prompt`, `get_conversation`, `get_project`, `list_comments`, `list_design_systems`, `list_files`, `list_members`, `list_projects`, `put_conversation`, `read_design_skill`, `read_file`, `remove_member`, `render_preview`, `update_member_role`, `update_sharing`, and `write_files`.

File mutations require `finalize_plan`; writes use etags; `read_file` is capped at 256 KiB. This verified schema does not expose project deletion, design-system mutation, template/admin operations, or binary export, so route those to the guarded browser contract.
