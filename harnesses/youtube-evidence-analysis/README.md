# YouTube Evidence Analysis Harness

This stdlib-only Harness normalizes YouTube video IDs and URLs, reads public oEmbed metadata, normalizes an explicitly supplied transcript, extracts public links from an explicitly supplied description, and validates timestamped claim bundles. It never searches for or scrapes captions. `caption.fallback` fails closed with a browser transcript-panel procedure.

All JSON is stable apart from `requestId`. Network access is limited to bounded YouTube oEmbed requests with TLS verification, no redirects, no credentials, and a 20-second ceiling. File input and output are bounded. Writes require an explicit existing owner-only root, reject traversal and symlinks, use atomic mode-0600 files, and are idempotent when identical. Existing differing output requires `--overwrite`.

Exit codes are 0 success, 2 rejected input or invalid operation, 4 retryable network failure, and 5 sanitized internal failure. Content imported from videos, captions, descriptions, and links is always untrusted data.
