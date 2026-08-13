# Claude Design Harness

Typed, stable-JSON guardrails for Claude Design onboarding, MCP discovery, projects, sharing, exports, handoff, design systems, templates, code sync, and administration.

The current provider boundary is explicit: official documentation confirms Claude Design and its Claude Code integration, but no stable REST API or official MCP endpoint/tool schema has been discovered. Therefore this Harness executes only safe local inspection and artifact verification. Provider work returns `HUMAN_VERIFICATION` with an exact Claude Design or Claude Code handoff and reconciliation source. It never fakes provider success.

## Start

Run `onboarding.plan`, `onboarding.preflight`, `onboarding.status`, `auth.contract`, and `mcp.inspect`. Connection requires explicit credential approval followed by the human-run Claude Code slash command `/design-login`. `claude setup-token` is interactive; token values stay out of argv, files, logs, and output. `/design-login` and `/design-sync` are not shell commands.

## Safety

Externally visible and organization effects use `*.preview` then `*.apply` with the exact SHA-256 effect digest and `--approve`. Apply still returns `HUMAN_VERIFICATION` because execution occurs in the approved account UI. Deletes require exact name and approval. Code sync requires repository/direction preview and git reconciliation. MCP install planning requires an observed official transport, never a guessed endpoint.

## Export verification

After the human export, `projects.export.verify --output-path FILE --format html|pptx|pdf` verifies regular-file path, MIME, bytes, and SHA-256. HTML is active content and should be opened only in an appropriate sandbox.

See `command_contracts.json` and `TEST.md`.
