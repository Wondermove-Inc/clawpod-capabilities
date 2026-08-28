# Read-Only Inspection Reference

Use this reference for Salesforce org fact gathering that must not change org state.

## Evidence Envelope

Every inspection artifact must tie together:

- source request and work item;
- target alias, org ID, username, and API version;
- exact command with secrets removed;
- UTC or local timestamp with timezone;
- exit code and stdout/stderr location;
- query text or metadata type;
- permission limitation or row limit;
- redaction status.

Keep read-only inspection evidence separate from mutation before/after evidence.

## Command Patterns

Refresh target identity before collecting org facts:

```bash
sf org display --target-org <TARGET_ORG> --api-version <API_VERSION> --json
```

Inventory metadata types and selected components:

```bash
sf org list metadata-types --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf org list metadata --metadata-type Flow --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf org list metadata --metadata-type ApexClass --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf org list metadata --metadata-type LightningComponentBundle --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf org list metadata --metadata-type FlexiPage --target-org <TARGET_ORG> --api-version <API_VERSION> --json
```

Use `--folder <FOLDER_NAME>` only for folder-backed metadata such as Dashboard, Document, EmailTemplate, or Report.

Confirm schema before SOQL:

```bash
sf sobject describe --sobject Case --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf sobject describe --sobject PlatformAction --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf sobject describe --sobject ApexClass --use-tooling-api --target-org <TARGET_ORG> --api-version <API_VERSION> --json
```

Run bounded standard SOQL only after fields are confirmed:

```bash
sf data query --query "SELECT Id, Subject, Status FROM Case WHERE Id = '<CASE_ID>' LIMIT 1" --target-org <TARGET_ORG> --api-version <API_VERSION> --json
```

Run Tooling API SOQL only for Tooling API objects:

```bash
sf data query --use-tooling-api --query "SELECT Id, Name FROM ApexClass WHERE Name = '<APEX_CLASS_NAME>' LIMIT 1" --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf data query --use-tooling-api --query "SELECT MetadataComponentName, MetadataComponentType, RefMetadataComponentName, RefMetadataComponentType FROM MetadataComponentDependency WHERE RefMetadataComponentName = '<COMPONENT_API_NAME>' LIMIT 50" --target-org <TARGET_ORG> --api-version <API_VERSION> --json
```

Check org limits:

```bash
sf org list limits --target-org <TARGET_ORG> --api-version <API_VERSION> --json
```

## Boundaries

- `sf org list metadata*` proves inventory visibility, not deployability, runtime behavior, or UI placement.
- `sf sobject describe` proves available fields for that API surface and permission context, not business meaning.
- `sf data query --use-tooling-api` is for Tooling API objects. Do not mix it with ordinary sObject assumptions.
- If a SOQL query would return more than 10,000 records, stop and recommend a separately approved Bulk API inspection plan instead of forcing the query.
- `MetadataComponentDependency` can identify candidate references, but it is not complete impact analysis.

## Redaction

Avoid selecting free-form customer content fields unless they are required. Mask emails, phone numbers, access tokens, session IDs, frontdoor URLs, bearer values, private keys, and customer payloads before sharing.

Run a bounded scan on generated evidence when it may include auth/session data:

```bash
rg -n 'frontdoor\\.jsp|otp=|sid=|Authorization:|Bearer |accessToken|refreshToken|sfdxAuthUrl|clientSecret|privateKey|password' <EVIDENCE_DIR>
```

Exclude previous `security-token-scan*.txt` files from final effective scans to avoid recursive false positives.
