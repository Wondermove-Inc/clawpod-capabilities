# Harness operations

- `status`, `preflight`: no input and no writes.
- `video.normalize --video ID_OR_URL`: accepts an 11-character ID or unambiguous YouTube watch, short, embed, live, or Shorts URL.
- `metadata.oembed --video ... [--timeout 1..20] [--max-bytes <=500000]`: reads only public YouTube oEmbed JSON.
- `caption.fallback --video ...`: always returns unavailable plus the browser transcript-panel capture contract.
- `transcript.import --input-root ROOT --input capture.json --video ... --language ko --source-kind browser-transcript-panel [--output-root ROOT --output transcript.json]`: input is `{"segments":[{"start":"0:01","end":"0:05","text":"..."}]}`; `duration` may replace `end`.
- `description.links --input-root ROOT --input description.txt`: extracts bounded credential-free public HTTP(S) links without fetching them.
- `bundle.validate --input-root ROOT --input bundle.json`: claims use `id`, `text`, `kind` (`fact`, `opinion`, `marketing`, `sponsorship`), `status`, and evidence entries with `url`, `start`, `end`, `quote`, and the exact canonical `timestampUrl`.

Only `inputRoot` and `outputRoot` are Gateway path arguments. `input` and `output` are bounded relative child strings. Output roots must already exist with owner-only permissions. Re-running an identical write is an idempotent `unchanged` success; differing existing content fails unless `overwrite` is explicitly true.
