# Verification Boundary

This reference defines the non-mutating verification contract for `salesforce-verification`.

## No-Mutation Boundary

- Forbidden here: actual deploy, retrieve that overwrites local source from org state, metadata create/update/delete, Flow activation/deactivation, data create/update/delete, permission assignment, Platform Event publication, live external endpoint probe, and cleanup.
- Actual deploy is out of scope for this skill.
- Dry-run/check-only deploy validation is deploy-shaped org contact. Use it only when the assignment explicitly authorizes verification against a named target org, and never treat it as permission to perform the actual deploy.
- Do not rely on default org configuration. Any authorized org command must include `--target-org` or `-o`.
- Do not use shell backticks, command substitution, globs, or generated command strings for Salesforce org commands.

## Local Quality Gate

Run only checks that match the changed surface:

- XML/schema parsing for metadata files.
- Focused unit tests or validators for local code.
- Salesforce Code Analyzer for Apex, Visualforce, Flow, and Lightning components when available.
- Secret scan over final evidence and touched source.

Code Analyzer requirements:

- Record `sf plugins --core`, `sf code-analyzer run --help`, selected engines, JDK/Python versions when those engines are used, command, exit code, and output file path.
- Use `sf code-analyzer run --output-file <path>.json` or another documented output extension. Do not assume `run --json` exists.
- Use `--severity-threshold 3` when the gate is High/Moderate zero.
- If Java 11+ or Python 3.10+ is missing for selected engines, report the blocked engine and do not claim the gate passed.

## Apex Test Evidence

- `sf apex run test` invokes tests in a Salesforce org. It can validate org-resident code and deployed source, not un-deployed local edits.
- Pin `--target-org`, select `--class-names` or `--tests`, use `--code-coverage` when Apex coverage is part of the claim, and preserve JSON/JUnit output.
- Record which changed classes/triggers each test covers. For `RunSpecifiedTests` deploy validation, each class and trigger in the deployment package must meet the relevant coverage requirement.
- Test fixture DML inside Apex tests rolls back as part of test execution, but the command is still org contact and requires explicit target authorization.

## Deploy Dry-Run / Check-Only Evidence

- `sf project deploy start --dry-run` validates the deployment and runs selected Apex tests without saving components to the org.
- Preserve deploy/check-only ID, component list, test level, tests, source hash, exact input path or manifest, command, stdout/stderr, and exit code.
- Compare dry-run input hash to any later actual-deploy candidate. If the hash changed, require a new dry-run and reviewer gate.
- Do not use `--ignore-errors` or `--ignore-conflicts` for a verification gate unless an authorized release owner explicitly accepts the risk in writing.

## Redaction

- Never save raw `frontdoor.jsp`, `otp=`, `sid=`, access tokens, bearer headers, signing keys, Named Credential secrets, session URLs, or copied raw scan hits as final evidence.
- Store only redacted URLs such as `<REDACTED_FRONTDOOR_URL>` and keep temporary unredacted values in process memory when possible.
- Exclude previous scan-output files from effective re-scan or they can copy the secret pattern into the next scan result.
- Final evidence must include a clean scan summary and the scan scope.

## Confirmed Sources

| Claim | Official source | API version / release | Date confirmed |
| --- | --- | --- | --- |
| Deploy dry-run validates and runs Apex tests without saving; deploy supports `--target-org`, `--test-level`, and `--tests`. | https://developer.salesforce.com/docs/platform/salesforce-cli-reference/guide/cli_reference_project_deploy_start.html | API version not applicable on CLI page | 2026-08-02 |
| Apex tests are invoked in an org and support JSON result format, code coverage, class/test selection, and wait behavior. | https://developer.salesforce.com/docs/platform/salesforce-cli-reference/guide/cli_reference_apex_run_test.html | API version not applicable on CLI page | 2026-08-02 |
| Code Analyzer uses CLI plugin commands, PMD/CPD/Salesforce Graph require JDK 11+, Flow Scanner requires Python 3.10+, `--severity-threshold` can fail the command, and `--output-file` determines output format. | https://developer.salesforce.com/docs/platform/salesforce-code-analyzer/guide/analyze.html | API version not applicable on tool page | 2026-08-02 |
| Metadata API `deploy()` checkOnly is validation without saving components. | https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_deploy.htm | 67.0 (Summer '26) | 2026-08-02 |

Project worklog basis: `docs/poc-sf-org/worklog/lessons.md` T-03, T-09, T-14, T-16, T-24, T-27, T-29, T-39, T-111, T-116, T-117, T-141, and T-147.
