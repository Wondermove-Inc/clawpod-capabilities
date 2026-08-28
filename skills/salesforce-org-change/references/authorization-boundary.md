# Authorization Boundary Reference

Read before planning or executing any Salesforce org mutation.

## Authorization requirements

Explicit authorization must name:

- operation type;
- target Salesforce org;
- approved scope/components/records;
- timing or execution window;
- success criteria;
- stop conditions;
- rollback or bounded cleanup expectation.

If any item is missing or ambiguous, do not mutate. Provide a read-only plan and ask for a decision.

## Required rule documents

Read `dev-rules/README.md` first and apply relevant `DR-CMN-001` through `DR-CMN-013`.

Read `dev-rules/08_case_chatter_rules.md` for approved-request tracking. Link every mutation to the approved request and track applicable intake, correction, and completion through Case and Chatter while preserving Case, FeedItem, FeedComment, and Mention relationship evidence when Case/Chatter is the approved work-record system.

Read every canonical technology module that matches the mutation:

- Metadata/configuration: `dev-rules/01_configuration_rules.md`
- SOQL/Apex-related data or tests: `dev-rules/02_soql_rules.md`, `dev-rules/03_apex_rules.md`
- Flow deploy/activation: `dev-rules/04_flow_rules.md`
- LWC deployment surface: `dev-rules/05_lwc_rules.md`
- Integration, credentials, endpoints, events: `dev-rules/06_integration_rules.md`

## Target identity and command hygiene

- Verify target org identity with read-only evidence and compare org ID, alias or username, environment type, API version, and expected user to the approved target.
- Reconfirm target identity immediately before execution.
- Pin every mutating command with `--target-org` or `-o`.
- Never rely on default org.
- Do not use shell backticks, command substitution, globs, or generated command strings.
- Write exact bounded commands and explicit targets.

## Evidence requirements

Capture before and after state for the same metadata, records, permissions, Flow state, endpoint, or runtime surface. Preserve raw command output and identifiers.
