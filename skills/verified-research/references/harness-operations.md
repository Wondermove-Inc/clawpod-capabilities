# Harness operations

The Harness consumes bounded JSON through explicit input roots and writes only beneath explicit output roots. Every path is relative and symlink-free. Existing outputs fail closed unless `overwrite` is explicitly true.

- `source.fetch`: public `url`, optionally `outputRoot` plus `snapshot`; the latter stores an exact `<snapshot>.bytes` file and a JSON source record.
- `source.batch`: `inputRoot` plus a nonempty bounded URL `manifest`; optional output captures per-item results. Any failed item returns `PARTIAL_FAILURE` while retaining successes.
- `source.import`: `inputRoot` plus local `capture`; optional public `sourceUrl` is syntax-checked without live DNS for offline use. Output stores exact bytes and the source record.
- `bundle.build`: source and claim JSON inputs plus explicit output. It validates structures before writing JSON and bounded Markdown.
- `bundle.validate`: `inputRoot` plus `bundle`, optionally `asOf` for future-date checks. It performs no network requests and rechecks referenced snapshots.
- `bundle.inspect`: bounded read-only summary.

A URL manifest is `{ "urls": ["https://…"] }`. Claims use closed statuses `supported`, `verified`, `unsupported`, `unresolved`, or `conflicted`; supported/verified claims require evidence. Evidence quote text must exactly equal the normalized `startLine` through `endLine` span.

No search provider is included. For JavaScript-only pages, use OpenClaw browser capture without sending cookies or credentials to the Harness; save only needed readable text under a private declared input root, then import it. Do not bypass paywalls or access controls. The Harness validates deterministic evidence integrity, not semantic truth.
