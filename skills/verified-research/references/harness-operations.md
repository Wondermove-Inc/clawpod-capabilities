# Harness operations

The Harness consumes JSON files through explicit input roots and writes only beneath explicit output roots. Paths are relative, symlink-free, and bounded.

- `source.fetch`: `--url`, optionally `--output-root` and `--snapshot`.
- `source.batch`: `--input-root --manifest`, optionally `--output-root --output`.
- `source.import`: `--input-root --capture`, with optional `--source-url` and output options.
- `bundle.build`: `--input-root --sources --claims --output-root --output`.
- `bundle.validate`: `--input-root --bundle`.
- `bundle.inspect`: `--input-root --bundle`.

A manifest is `{ "urls": ["https://…"] }`; claims are `{ "claims": [{"id":"c1","text":"…","status":"supported","evidence":[{"sourceId":"…","startLine":1,"endLine":2,"quote":"…"}]}] }`.

No search provider is included. For JavaScript-only pages, use OpenClaw browser capture without sending private cookies to the Harness; save only needed readable text under the declared input root, then import it. Do not bypass paywalls or access controls.
