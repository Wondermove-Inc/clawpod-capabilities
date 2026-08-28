# Mutation Review Reference

Use when the reviewed work touches or plans Salesforce org mutation.

## Mutation safety checks

Verify:

- explicit authorization covers operation, target Salesforce org, scope, and timing;
- target-org identity evidence is current and matches the approved target;
- mutating commands are pinned with `--target-org` or `-o`;
- default org is not relied on;
- check-only or dry-run evidence is inspected when applicable;
- deploy, test, retrieve, activation/deactivation, data, assignment, and cleanup IDs are recorded when they occur;
- before and after state are captured through the same surface;
- rollback or bounded cleanup is specific, approved, and verified;
- unintended mutation handling is documented if anything unexpected occurred.

## No-go triggers

Return `no-go` for:

- missing explicit authorization;
- ambiguous target org;
- stale or mismatched org identity;
- generated or unbounded mutation command;
- mutation evidence without raw output;
- deploy success reported as runtime acceptance;
- missing cleanup/rollback evidence when cleanup or rollback is in scope;
- self-approval of mutation safety.
