# Memory Graph v0.6.0 release evidence

## Scope

Refines the existing paired `memory-graph` Skill and Harness. v0.5 structural/provenance behavior remains the base layer. v0.6 adds a grounded semantic projection that accepts only explicit structured claim metadata.

## Contract

- Entities: `Person`, `Project`, `Decision`, `Event`
- Relations: `participates_in`, `decided`, `caused`, `supersedes`
- Stable explicit IDs, mandatory claim/evidence provenance, temporal/status eligibility
- Deterministic quarantine for invalid or ambiguous semantic records
- Owned semantic namespace only; canonical Markdown remains read-only
- Memory MCP relation tuples use deterministic sidecar provenance
- Query planning remains direct-CLI-only and is intentionally excluded from the initial Gateway manifest

## Evidence

- Design commit: `3abf6ac`
- Implementation commit: `d24b327`
- Independent hardening commit: `e867436`
- Test suite: 54/54 passed
- Repository validator: 34 capability entries passed
- Registry synchronization: passed
- Python compilation: passed
- `git diff --check`: passed
- Paired versions: Skill capability `0.6.0`, Harness manifest/capability `0.6.0`
- Gateway manifest commands: `inspect`, `plan`, `validate-plan`, `validate-snapshot`, `onboard`, `cron-plan`
- Static Gateway schema check: no `enum`, `minimum`, `maximum`, or `minLength`

## Defects found and fixed during independent validation

- Deterministic claim hashing
- RFC 3339/date/interval validation and normalization
- Semantic supersession self-edge, cycle, and backwards-time quarantine
- Alias and external-ID normalization
- Exact deterministic edge hashing
- Removed direct-CLI-only query planning from the initial Gateway manifest

## Migration and rollback

Migration is additive: retain the v0.5 core/claim projection and reconcile only owned `semantic:*` objects. A candidate snapshot must validate before mutation. Rollback removes only semantic objects for the target contract version and restores the prior private state pointer. Canonical Markdown, v0.5 objects, cron state, foreign entities, and unrelated namespaces remain untouched.

## Approval and actions not performed

Jang Jaewon approved branch publication and PR creation in Room 230 on 2026-08-10 14:30 KST. Merge is not authorized. No installation, Gateway restart, production mutation, canonical-memory mutation, or live Memory MCP call was performed during candidate preparation.

## Known limit

The canonical memory writer does not yet emit the structured semantic metadata extension. Therefore v0.6 safely projects only claims that already contain explicit valid semantic metadata. Prose-only claims remain structural locators and do not produce autonomous semantic edges. A writer-extension change is a separate capability/runtime scope and is not included in this PR.
