# Verified Research + Tavily MCP integration specification

## Decision and evidence

**Classification: `refine + compose`.** Refine the existing canonical connected capability `verified-research`; compose it with the registered Tavily MCP server as its recommended discovery/extraction backend. Do not create a Tavily Skill or a second research capability.

Evidence inspected on canonical `origin/main` at `dba924f6da5e547fa7014bc3bce5310fae78b3c3`:

- `skills/verified-research/SKILL.md` already owns source selection, cross-checking, contradiction handling, confidence, and no-fabrication policy.
- `harnesses/verified-research/*` version `0.1.5` already owns deterministic capture/import, hashing, bundling, and validation, but explicitly says it does not search.
- `skills/verified-research/capability.json` links Harness `verified-research` at the same version.
- Live `mcporter list tavily --schema` exposes five tools: `tavily_search`, `tavily_extract`, `tavily_map`, `tavily_crawl`, and `tavily_research`; research documents a 20 requests/minute limit.

This is composition, not backend code duplication: Tavily discovers and extracts candidate evidence, while the Harness remains the deterministic evidence authority.

## Release and files

Patch-bump the complete connected unit from **0.1.5 to 0.1.6**. Update every version-bearing source and generated artifact exactly once:

1. `skills/verified-research/SKILL.md`
2. `skills/verified-research/capability.json`
3. Add `skills/verified-research/references/tavily-mcp.md`
4. Add `skills/verified-research/references/onboarding.md`
5. `harnesses/verified-research/README.md`
6. `harnesses/verified-research/TEST.md`
7. `harnesses/verified-research/verified_research.py` provenance version
8. `harnesses/verified-research/scripts/generate_schemas.py`
9. Generated `harnesses/verified-research/harness.json`
10. `harnesses/verified-research/capability.json`
11. Extend `harnesses/verified-research/tests/test_verified_research.py`
12. Regenerate `registry/index.json` with `scripts/sync_registry.py`

No Tavily client, API key, MCP configuration containing a value, provider response fixture, or duplicate Tavily package belongs in the repository.

## Capability contract

### State vocabulary

- `installed_but_not_connected`: Skill/Harness files validated, but Tavily registration, environment resolution, or live schema probe has not succeeded.
- `connected`: server `tavily` is registered using `${TAVILY_API_KEY}`, the environment resolves at Gateway runtime, and a live schema probe returns all five required tools.
- `degraded`: Tavily is missing, unauthorized, unavailable, rate-limited, or lacks a required tool; research may continue with explicit fallback and limitations.
- `revoked`: Tavily registration has been removed and secret binding is no longer usable.

Installation is never connection. The unit remains useful in degraded mode.

### Immediate post-install handoff

Immediately after registry installation and digest validation, the agent must say: **“Verified Research is installed but not yet connected to Tavily.”** It must explain that Tavily is the recommended search/extract/map/crawl/research backend, that `web_fetch` and `browser` remain degraded fallbacks, that the API key stays in protected/persistent OpenClaw environment handling and never enters repository files or command output, and that Gateway restart is a separate approval-gated action. Ask: **“Connect Verified Research to Tavily now?”**

Do not register MCP, use a key, edit runtime configuration, or restart Gateway before approval. If onboarding is deferred, preserve `installed_but_not_connected` and provide the resume phrase “Connect Verified Research to Tavily.”

### Approved onboarding lifecycle

1. **Preflight, read-only:** run `mcporter list tavily --schema`. If an existing server works and exposes all five tools, record `connected` without rewriting config or restarting.
2. **Credential discovery:** search protected secret metadata first. Never ask for plaintext in chat when a usable pointer/environment binding exists. A newly supplied key goes directly to protected storage without echo/logging.
3. **Plan:** show the exact intended registration: server id `tavily`, official remote endpoint `https://mcp.tavily.com/mcp/`, and environment interpolation `${TAVILY_API_KEY}`. No literal key is permitted.
4. **Register/update:** use the supported MCP/OpenClaw configuration surface, preserving unrelated servers and creating a rollback copy. Registration/config mutation is approval-gated `writeSafe`; credential resolution is `secretUse`; the live probe is a network `readOnly` action.
5. **Gateway boundary:** if persistent OpenClaw environment or MCP registration requires Gateway restart, stop and request explicit approval. Use only `openclaw gateway restart` after approval. Never imply install approval covers restart.
6. **Verify:** after runtime reload, run `mcporter list tavily --schema`; require exactly the practical five-tool surface. Then run one bounded, low-cost `tavily_search` smoke query with `max_results=1`, `search_depth=basic`, no raw content/images. Verify a structured response and at least one source URL. Do not use `tavily_research` for connection testing.
7. **Declare:** report `connected` only after schema plus smoke succeed. Otherwise report `installed_but_not_connected` or `degraded`, the sanitized failure class, fallback path, and recovery step.

### Removal and recovery

- Removal must preview the exact `tavily` server entry and remove only that entry after approval; preserve unrelated MCP configuration. Gateway restart remains separately approved. Do not delete the protected key unless the owner separately requests destructive secret deletion.
- After removal, verify `mcporter list tavily --schema` no longer resolves and report `revoked`; Verified Research remains installed and degraded-capable.
- Unauthorized/key invalid: rotate/update the protected value, never put it in MCP JSON, restart only with approval, then repeat schema and bounded smoke.
- Server unavailable/timeout/5xx: no configuration churn; retry once with bounded backoff, then degrade.
- 429: honor `Retry-After`; do not tight-loop or silently switch to expensive research. Degrade or ask whether to wait.
- Schema drift/missing tool: mark `degraded`, retain last known-good configuration, avoid destructive re-registration, and report expected versus observed tools.
- Broken config/reload: restore the exact rollback copy, request restart approval if needed, verify prior MCP state, and report partial side effects.

## Tool-selection policy

1. Decompose the question into claims before searching.
2. Use `tavily_search` for discovery/current facts. Default `basic`, 5 or fewer results; use `advanced` only for consequential, disputed, or weak-result claims. Use domain/date filters narrowly.
3. Use `tavily_extract` for one or more known URLs. Default `basic`, markdown, no images; use advanced only for tables/embedded/protected content when access is lawful.
4. Use `tavily_map` to locate relevant site sections before crawling. Default depth 1 and bounded limit; restrict paths/domains.
5. Use `tavily_crawl` only when multiple pages from one site are necessary. Set explicit low depth, breadth, and total limit; default `allow_external=false` for evidence gathering.
6. Use `tavily_research` only for broad multi-subtopic discovery where iterative search would be materially worse. Default `mini` for narrow work, `pro` only with a user-visible cost/latency warning. Its synthesized answer is never evidence by itself; verify material claims against returned source URLs.
7. Import/capture selected source content through existing Harness `source.fetch`, bounded `source.batch`, or `source.import`, then build and validate the evidence bundle. Tavily snippets and synthesis are leads, not a substitute for quote/line/hash validation.
8. If Tavily is unavailable, explicitly announce degraded mode and use `web_fetch` for known/public URLs and `browser` for JS-only pages without bypassing controls. If discovery itself is unavailable, ask for URLs or state that coverage is incomplete.

## Cost, limits, privacy, and safety

- All Tavily calls are external network reads and may send the query, URLs, instructions, and filters to Tavily. Never include secrets, credentials, private documents, personal data, unpublished business data, or unredacted user content without specific authorization.
- MCP registration/configuration is `writeSafe`; secret lookup/injection is `secretUse`; account/plan changes are outside this capability; Gateway restart is an explicit operational approval; removal is reversible config mutation; protected-secret deletion is destructive and separately approved.
- Bound calls, batch URLs where supported, reuse results, cache only non-sensitive evidence artifacts, and avoid parallel bursts. Respect 429 and `Retry-After`. `tavily_research` is capped at 20 requests/minute by the observed schema, but policy should remain stricter: one active research call at a time and no automatic retry after a chargeable successful submission.
- Before advanced search/extract, crawl beyond small defaults, or `research pro`, disclose likely extra latency/cost when material. Do not claim exact billing unless provider-reported.
- Sanitize errors. Tests, fixtures, docs, commits, logs, and artifacts must contain `${TAVILY_API_KEY}` only, never a key-shaped literal or resolved value.

## Tests

Add deterministic documentation/contract tests that assert:

- Skill routes Tavily as recommended backend and preserves `web_fetch`/`browser` degraded fallback.
- All five exact tool names are documented and assigned distinct bounded use cases.
- `0.1.6` matches Skill metadata, linked Harness, Harness metadata, generated manifest, runtime provenance, and Registry entries.
- Immediate post-install wording distinguishes installed from connected and asks before onboarding.
- Connection requires schema plus bounded basic-search smoke; no paid/deep research smoke.
- Restart is named as separately approval-gated.
- Registration uses `${TAVILY_API_KEY}` and repository scan rejects likely Tavily key literals.
- Removal preserves the secret unless separately requested; degraded and rollback paths are explicit.
- 429/`Retry-After`, one-at-a-time research, bounded map/crawl, and cost warning rules exist.
- Existing focused evidence-pipeline tests remain unchanged and pass.

Live validation, using protected runtime configuration and no captured response body in committed artifacts:

```text
mcporter list tavily --schema
mcporter call tavily.tavily_search --args '{"query":"OpenClaw official documentation","max_results":1,"search_depth":"basic","include_raw_content":false,"include_images":false}'
```

The live smoke is an onboarding/release evidence step, not a hermetic CI test.

## Validation and publication gates

Run from a clean candidate worktree:

```text
python3 -m pytest -q harnesses/verified-research/tests/test_verified_research.py
python3 -m pytest -q
python3 harnesses/verified-research/scripts/generate_schemas.py
python3 scripts/sync_registry.py --check
python3 scripts/validate.py
python3 -m py_compile harnesses/verified-research/verified_research.py harnesses/verified-research/scripts/generate_schemas.py
git diff --check
```

Also install the candidate Skill/Harness into isolated temporary roots, validate digests and linked-version invariants, inspect generated manifests, and run degraded-mode tests with the key absent and MCP unavailable. Publication is blocked unless: canonical main was the base; version/digest invariants pass; no secret scan findings exist; focused/full/clean-install suites pass; five-tool live schema evidence is current; bounded smoke succeeds or is explicitly recorded credential-blocked; rollback/removal is tested; registry sync is clean; and review confirms there is no duplicate Tavily Skill. Merge/publication and live installation are separate actions from this specification.
