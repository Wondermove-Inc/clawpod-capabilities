# Salesforce Setup Contract

Use this reference for the first-run onboarding sequence: verify or install sf tooling, use existing non-secret auth evidence when available, collect setup secrets and authenticate only when new or missing auth is approved and needed, and bind the target org — without changing Salesforce metadata or data.

## Sequence

1. Verify local tooling:

```bash
node --version
sf --version
sf plugins --core
java -version
python3 --version
test -f sfdx-project.json
```

If `sfdx-project.json` is missing and Salesforce project readiness is required, say exactly:

> "sfdx-project.json 확인이 필요합니다. Salesforce repo 주소를 전달해주세요"

Then stop project-root readiness until the Salesforce DX project repository or correct project root is available.

2. With user approval, install a missing Salesforce CLI or Code Analyzer plugin:

```bash
npm install @salesforce/cli --global
sf plugins install code-analyzer
```

- Node.js must be the Active LTS version per the official install guide. If Node.js is missing, stop and report; OS-level installs (Node.js, Python, browsers) are outside this skill. Java is the one exception: the ClawPoD standard execution environment is Ubuntu, so this skill may install Ubuntu `openjdk-17-jdk` without a separate user approval, but only after the environment checks in SKILL.md confirm `ID=ubuntu` and `apt-get` exists. On any non-Ubuntu environment, Java stays outside this skill.
- Java 11+ and Python 3.10+ are existence checks only — Code Analyzer engine gating stays with `salesforce-verification`. Record Python absence as a reported fact, not a setup failure. Record Java absence the same way only when the Ubuntu install path above is unavailable or fails; do not claim Java-dependent analyzer readiness in that case.

3. Request setup information only when new or missing authentication is approved and needed for the target: SFDX auth URL, instance URL, target alias. For tooling/readiness-only checks or already-authenticated target verification, use existing non-secret auth evidence instead of collecting new credentials. Values that are collected go into the runtime secret store, never into chat, repository files, or evidence.

4. When authentication is needed, authenticate non-interactively from the secret store, stdin preferred:

```bash
<secret-store read command> | sf org login sfdx-url --alias <TARGET_ALIAS> --sfdx-url-stdin
```

`--sfdx-url-stdin` consumes standard input and must be the final token on the command line.

If a file is unavoidable: create it outside the repository, `sf org login sfdx-url --sfdx-url-file <path>`, delete the file immediately after login, and verify deletion.

5. Fallback, only when the user states they cannot provide the secret: confirm a Chrome binary exists, then launch the browser login from the agent's own PC (VPC) and ask the user to complete it:

```bash
sf org login web --alias <TARGET_ALIAS> --instance-url <INSTANCE_URL> --browser chrome
```

If Chrome is absent, stop and report. Do not install a browser. Do not add `--set-default` in either auth path — ClawPoD agents must still pin every later org command with `--target-org` or `-o`.

6. Confirm authenticated org list (candidates only, not proof of correct target):

```bash
sf org list --json
```

7. Bind the exact target:

```bash
sf org display --target-org <TARGET_ORG> --api-version <API_VERSION> --json
```

Normalize the evidence into these fields before sharing: `alias`, `org_id`, `username`, `instance_url_domain`, `connected_status`, `api_version`, `environment_type` when present, `source_command`, `timestamp`, `exit_code`, and `redaction_status`.

8. Run bounded read-only capability probes only when they are needed for the next task:

```bash
sf org list metadata-types --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf org list limits --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf sobject describe --target-org <TARGET_ORG> --api-version <API_VERSION> --sobject Case --json
```

## Redaction

`sf org display` can include access token and client ID fields, and `--verbose` can include an SFDX auth URL. Do not use `--verbose`. Before evidence leaves the local scratch area, replace token-like fields with fixed placeholders and record that redaction occurred.

Scan source and evidence that might contain credentials with a bounded pattern set:

```bash
rg -n 'frontdoor\.jsp|otp=|sid=|Authorization:|Bearer |accessToken|refreshToken|sfdxAuthUrl|force://|clientSecret|privateKey|password' <EVIDENCE_DIR>
```

Exclude prior scan output files and this skill's own deleted-then-recreated temporary artifacts from the final effective scan so the scan does not recursively match its own findings. A hit on a surviving temporary credential file is a stop condition, not a note.

## Setup Completion Criteria

Setup is complete only when:

- local CLI and plugin versions are recorded, including anything installed during onboarding;
- when new or missing authentication was required, the approved secret-store request was made and its outcome recorded (secret stored, or user-declared unavailable with Chrome fallback used);
- no temporary credential file survives the login step;
- target org identity is explicit and redacted;
- API version handling is recorded;
- required read-only capability probes succeeded or their failures are reported;
- no credential-bearing value remains in shared output;
- the next skill is identified.

Setup does not prove that the org is fit for customer PoC work unless a responsible person or approved evidence confirms that target fit.
