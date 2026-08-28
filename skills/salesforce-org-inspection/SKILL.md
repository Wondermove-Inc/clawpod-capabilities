---
name: salesforce-org-inspection
description: Perform read-only Salesforce org inspection with explicit target-org pinning, schema confirmation, dependency probes, limits checks, evidence redaction, and stop conditions.
---

# Salesforce Org Inspection

Capability: `salesforce-org-inspection`

Use this OpenClaw skill to inspect a specified Salesforce org or tenant instance without changing metadata, setup, permissions, data, or runtime state. Use it before local development, verification, or an approved mutation when the task needs current org facts, schema, metadata inventory, limits, or first-pass dependency evidence.

This skill is read-only. It does not authorize deploy, retrieve, activation/deactivation, data mutation, REST POST/PATCH/DELETE, endpoint probes, package operations, permission assignments, or cleanup.

## Always Apply

1. Read the approved request, active plan, setup evidence, and `references/read-only-inspection.md`.
2. If setup evidence is missing or stale, first seek existing non-secret setup evidence or stop with the gap. Load `salesforce-setup` only for approved setup/readiness work; do not turn read-only inspection into a credential collection or login flow.
3. Never rely on default org. Pin every Salesforce command with `--target-org <TARGET_ORG>` or `-o <TARGET_ORG>` and record `<API_VERSION>` when the command supports it.
4. Separate standard data API queries, Tooling API queries, Metadata API inventory, and limits checks. Do not assume one query surface proves another.
5. Describe objects before querying unfamiliar fields, setup objects, or Tooling API objects.
6. Minimize data exposure: select only fields needed for the inspection, add bounded `WHERE` clauses and `LIMIT`, and redact personal data, customer payloads, auth material, and session URLs.
7. Mark org facts as `[VERIFIED]` only for the specific target org, API version, timestamp, query, and permissions used. Use `[ESTIMATED]` for impact analysis beyond the returned evidence.

## Allowed Commands

Target identity refresh:

```bash
sf org display --target-org <TARGET_ORG> --api-version <API_VERSION> --json
```

Metadata inventory:

```bash
sf org list metadata-types --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf org list metadata --metadata-type <METADATA_TYPE> --target-org <TARGET_ORG> --api-version <API_VERSION> --json
```

Schema and field confirmation:

```bash
sf sobject describe --sobject <OBJECT_API_NAME> --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf sobject describe --sobject <TOOLING_OBJECT_API_NAME> --use-tooling-api --target-org <TARGET_ORG> --api-version <API_VERSION> --json
```

Read-only SOQL:

```bash
sf data query --query "SELECT Id, <NEEDED_FIELDS> FROM <OBJECT_API_NAME> WHERE <BOUNDED_FILTER> LIMIT <N>" --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf data query --use-tooling-api --query "SELECT MetadataComponentName, MetadataComponentType, RefMetadataComponentName, RefMetadataComponentType FROM MetadataComponentDependency WHERE RefMetadataComponentName = '<COMPONENT_API_NAME>' LIMIT <N>" --target-org <TARGET_ORG> --api-version <API_VERSION> --json
```

Limits:

```bash
sf org list limits --target-org <TARGET_ORG> --api-version <API_VERSION> --json
```

These command shapes are verified against local Salesforce CLI `@salesforce/cli/2.141.6` help output and prior project worklog evidence. Recheck installed `--help` before adding other flags.

## Forbidden

- Do not run deploy, retrieve, activation/deactivation, metadata update, data create/update/delete/upsert, REST POST/PATCH/DELETE, permission assignment, package install/uninstall, event publish, endpoint callout probe, or cleanup.
- Do not run anonymous Apex. Even a read-looking anonymous Apex script can perform Data Manipulation Language (DML) or enqueue work.
- Do not use `--all-rows` unless the approved inspection explicitly includes deleted/archived records and the privacy boundary is recorded.
- Do not query fields guessed from naming convention. If `describe` does not confirm the object and field, stop.
- Do not report `MetadataComponentDependency` as a complete dependency graph. Treat it as first-pass impact evidence only.

## Stop Conditions

Stop when the target org identity does not match setup evidence, when the command would use a default org, when a required object/field is not confirmed by describe or official documentation, when a query needs more than 10,000 records, when output includes sensitive values that cannot be safely redacted, or when the requested action crosses into mutation.

If inspection requires mutation to answer the question, stop and provide a read-only gap report plus the exact approval needed for `salesforce-org-change`.

## Report

Lead with the inspected conclusion and its scope. Include target alias/org ID, API version, timestamp, command families, query text or metadata type, exit codes, redaction status, evidence paths, confirmed facts, estimates, and gaps. Do not generalize one org's state to another Salesforce org.
