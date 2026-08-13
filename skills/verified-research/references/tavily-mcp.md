# Tavily MCP policy

Tavily is the recommended external network-read backend for discovery and extraction. Decompose the question into claims before searching, keep calls bounded, batch URLs where supported, reuse non-sensitive results, and avoid parallel bursts. Never send secrets, credentials, private documents, personal data, unpublished business data, or unredacted user content without specific authorization. Tavily snippets and synthesis are leads: material claims require source URL capture/import, exact quote/line/hash validation, and a validated evidence bundle.

## Tool selection

- `tavily_search`: discover sources and current facts. Default to `search_depth=basic` and at most 5 results. Use `advanced` only for consequential, disputed, or weak-result claims, with narrow domain/date filters and a warning when extra cost or latency may be material.
- `tavily_extract`: extract one or more known URLs. Default to basic Markdown without images. Use advanced only when lawfully accessing tables, embedded, or protected content, after warning about material cost or latency.
- `tavily_map`: locate relevant site sections before crawling. Default to depth 1, a bounded low limit, and restricted paths/domains.
- `tavily_crawl`: gather multiple necessary pages from one site. Set explicit low depth, breadth, and total limits; default `allow_external=false`.
- `tavily_research`: reserve for broad, multi-subtopic discovery where iterative search is materially worse. Default to `mini`; warn the user about cost and latency before `pro`. Run one research call at a time, and never automatically retry a chargeable successful submission. Its synthesis is not evidence by itself; verify material claims against returned source URLs.

Import selected content through Harness `source.fetch`, bounded `source.batch`, or `source.import`, then run `bundle.build` and `bundle.validate`.

## Limits, failures, and degraded mode

The observed `tavily_research` schema states 20 requests/minute, but this policy is stricter. Honor `429` and `Retry-After`; never tight-loop or silently switch to expensive research. For timeout, unavailability, or 5xx, retry once with bounded backoff and then degrade without configuration churn. Missing tools or schema drift means `degraded`: retain the last known-good configuration and report expected versus observed tools.

When Tavily is unavailable, say that research is operating in degraded mode. Use `web_fetch` for known public URLs and `browser` for JavaScript-only pages without bypassing controls. If discovery is unavailable, ask for URLs or state that coverage is incomplete.
