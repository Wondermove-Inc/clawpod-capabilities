# Evidence Review Reference

Use for all Salesforce read-only gate reviews.

## Direct evidence inspection

1. Compare the approved plan against actual diff, tests, and evidence.
2. Build requirement-to-file-to-test-to-evidence mapping.
3. Open actual files and raw command output; do not rely on worker self-reports, summaries, pass counts, or path lists.
4. Confirm RED failures precede implementation, GREEN commands pass, and BLUE compares final diff with relevant Rule IDs.
5. Confirm Salesforce platform claims use official first-party evidence recorded in the active workspace citation log or in the portable format described by `citation-register.md`.

## Review checklist

Check:

- overspec, scope creep, unrelated changes, speculative components, and duplicate skill triggers;
- unsupported claims, incorrect `[VERIFIED]`, missing `[UNVERIFIED]`, and estimates presented as facts;
- stale evidence, stale citations, or reports that no longer match actual source/org state;
- missing tests, tests not run, hidden expected failures, incomplete negative coverage;
- missing raw evidence, missing identifiers, or missing before/after pairs;
- every applicable MUST, MUST NOT, provisional limitation, and Rule ID from skill-local distilled rules;
- English-only agent instruction files and removal of unfinished template markers from completed skills.

## Finding format

Record severity, evidence location, violated requirement or Rule ID, impact, and required remediation. Treat unavailable evidence as a gap, not as a pass.

Report coverage as `met`, `partial`, or `unmet`; list findings before minor notes; state final `go` or `no-go`; identify every remaining risk.
