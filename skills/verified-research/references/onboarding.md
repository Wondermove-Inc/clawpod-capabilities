# Tavily connection lifecycle

States are `installed_but_not_connected`, `connected`, `degraded`, and `revoked`. Installation is never connection, and Verified Research remains useful in degraded mode.

## Immediate post-install handoff

Immediately after registry installation and digest validation, say: “Verified Research is installed but not yet connected to Tavily.” Explain that Tavily is the recommended search/extract/map/crawl/research backend; `web_fetch` and `browser` remain degraded fallbacks; the API key stays in protected, persistent OpenClaw environment handling and never enters repository files or command output; and the agent restarts Gateway itself when registration needs it. In the same message, ask for the Tavily API key (the only input a human must supply) and start connecting as soon as it arrives. If the user has no key yet, preserve `installed_but_not_connected` and offer the resume phrase “Connect Verified Research to Tavily.”

## Connection

1. Preflight read-only with `mcporter list tavily --schema`. If it already exposes all five required tools—`tavily_search`, `tavily_extract`, `tavily_map`, `tavily_crawl`, and `tavily_research`—record `connected` without rewriting configuration or restarting.
2. Search protected secret metadata first. Prefer an existing pointer/environment binding and never request plaintext in chat when one is usable. Store a new key directly in protected storage without echoing or logging it.
3. Preview the exact registration: server id `tavily`, official remote endpoint `https://mcp.tavily.com/mcp/`, and environment interpolation `${TAVILY_API_KEY}`. A literal key is forbidden.
4. Use the supported MCP/OpenClaw configuration surface. Preserve unrelated servers and make a rollback copy. Configuration mutation is `writeSafe`, credential resolution is `secretUse`, and the live probe is network `readOnly`.
5. If persistent environment or MCP registration needs a Gateway restart, state the exact effect and run `openclaw gateway restart` in the same turn.
6. Verify after reload with `mcporter list tavily --schema`, requiring the practical five-tool surface. Then run one bounded `tavily_search` smoke query for “OpenClaw official documentation” with `max_results=1`, `search_depth=basic`, `include_raw_content=false`, and `include_images=false`. Require a structured response and at least one source URL. Never use `tavily_research` as a connection smoke test.
7. Declare `connected` only after both schema and smoke succeed. Otherwise report `installed_but_not_connected` or `degraded`, a sanitized failure class, fallback, and recovery step.

## Removal, rollback, and recovery

Preview the exact `tavily` server entry, then remove only that entry in the same turn while preserving unrelated MCP configuration, and restart Gateway if needed. Preserve the protected key unless its owner separately requests destructive secret deletion. Verify the schema no longer resolves, report `revoked`, and retain degraded-capable Verified Research.

For an invalid or unauthorized key, update the protected value, never MCP JSON, and repeat schema plus bounded smoke, restarting Gateway when needed. For schema drift, avoid destructive re-registration. For broken configuration/reload, restore the exact rollback copy, restart Gateway if needed, verify prior MCP state, and report partial side effects.
