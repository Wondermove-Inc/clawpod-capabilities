# Bridge test plan

[ESTIMATED] Validate four independent boundaries before claiming a bridge round complete: strict envelope/repository identity, authenticated transport, exact Markdown bytes, and correlated terminal callback. Basis: the approved CP1 brief; successful acceptance alone is insufficient.

1. Test pure KAT/byte-preserving derivation, strict unknown-field/type/nonce/TTL validation, credential-free repository normalization, wrong HEAD/origin/project/path and dirty repository rejection.
2. Test Markdown UTF-8, size, content type, hash/count, exact origin/nonce URL, forbidden paths, new-file-only staging and symlink rejection.
3. Exercise actual CLI subprocess and synthetic loopback HTTP: authenticated document GET plus callback, wrong token/nonce/hash/commit before valid callback, concurrent/duplicate callback, unsupported method/path, empty/oversized body, timeout and cleanup.
4. Check wake outer body text/mode, inbox derived Bearer, no redirects/retries, accepted versus complete, sanitized errors and synthetic secret absence from stdout/stderr/proof files.
5. Leave the 30-run equivalent preparation benchmark to the coordinator's pilot driver (coordinator's CP1 scope clarification); do not claim performance in this package. Run package, registry, metadata, repository and declared WM checks; record missing installed Gateway parser as SKIP.

## r1 independent-review regressions

[VERIFIED] Independent review reproduced two failures: case aliases bypassed forbidden paths on macOS, and a continuously dripping HTTP header kept the process alive after TTL/SIGTERM. Evidence: reviewer `/tmp/bridge-cp1-review-6dop13dx/reproduce.py` and `verdict.json`.

Test mixed-case `.Git`, `.ENV`, `.env.*` input/output/staging/repository paths including actual macOS aliases. Keep unauthenticated header and authenticated body connections open while sending bytes more frequently than the idle timeout; require process exit on both absolute TTL and SIGTERM without closing the client first. Preserve callback ACK, concurrency, and terminal-failure tests.
