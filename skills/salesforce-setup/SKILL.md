---
name: salesforce-setup
description: First-run Salesforce onboarding for a ClawPoD agent - verify or install sf tooling, install Java on Ubuntu after environment checks, use existing auth evidence when available, collect credentials and authenticate only when new or missing auth is approved and needed, bind the target org, and prove readiness with redacted evidence.
---

# Salesforce Setup

Capability: `salesforce-setup`

Use this OpenClaw skill when a ClawPoD agent must get a Salesforce org working for the first time: verify that the sf toolchain is installed, onboard (install) missing sf modules with user approval, install missing Java on Ubuntu after environment checks, use existing auth evidence when available, collect setup information and authenticate only when new or missing authentication is approved and needed, bind an explicit target org, and prove local tool/API readiness before development, inspection, verification, UI work, or approved org change.

This skill does not authorize Salesforce metadata or data mutation. Installation changes only the local machine; login changes only local CLI authentication state. Salesforce CLI and plugin installs require user approval. Java installation on Ubuntu is allowed by this skill after the environment checks below, without a separate user approval. Login still requires user approval.

## Always Apply

1. Read the active request, repository instructions, active plan, worklog context, and `references/setup-contract.md`.
2. Use official first-party Salesforce sources for Salesforce platform and CLI claims. Load `references/citation-register.md` when you need portable citation details.
3. Treat `org` as a Salesforce tenant instance. If nearby Korean documents say `조직`, confirm whether they mean a Salesforce org or the ClawPoD agent organization before planning.
4. Never rely on a default org. Every org-touching command in this skill must include `--target-org` or `-o` except `sf org list --json` and the login commands (`sf org login web`, `sf org login sfdx-url`), which create or select the authentication themselves.
5. Capture setup evidence with command, timestamp, exit code, local Salesforce CLI version, plugin version when relevant, target alias, org ID, username, instance URL domain, API version, and redaction status.
6. Redact access tokens, refresh tokens, SFDX auth URLs, client IDs when not needed, frontdoor URLs, `sid`, `otp`, bearer values, passwords, private keys, and customer payloads before sharing evidence. Receiving a secret from the user into the runtime secret store is allowed; exposing one in chat, files, source, or evidence is not.
7. Route read-only org fact gathering after setup to `salesforce-org-inspection`. Route local source implementation to `salesforce-development`. Route any approved mutation to `salesforce-org-change`.

## Onboarding: verify, then install what is missing

Check first, in this order:

```bash
node --version
sf --version
sf plugins --core
java -version
python3 --version
test -f sfdx-project.json
```

If `sfdx-project.json` is missing and the request requires Salesforce project readiness, do not call it an sf CLI install failure. Tell the coordinator or user exactly:

> "sfdx-project.json 확인이 필요합니다. Salesforce repo 주소를 전달해주세요"

Then stop project-root readiness until the Salesforce DX project repository or correct project root is available.

If the Salesforce CLI or Code Analyzer plugin is missing, ask for user approval, then install only these:

```bash
npm install @salesforce/cli --global
sf plugins install code-analyzer
```

If Java is missing, this skill may install Java on Ubuntu without a separate user approval. First verify the environment is Ubuntu and `apt-get` is available:

```bash
uname -a
. /etc/os-release && printf '%s %s\n' "$ID" "$VERSION_ID"
command -v apt-get
```

Proceed only when `ID=ubuntu` and `apt-get` exists. Use the Ubuntu package manager, not ad-hoc installers or remote scripts, then verify Java:

```bash
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk
java -version
```

- Node.js prerequisite: the Active LTS version (official install guide). If Node.js itself is missing, stop and report — installing Node.js, Python, or a browser is an OS-level change outside this skill.
- Java 11+ and Python 3.10+ are existence checks for Code Analyzer engines (`salesforce-verification` owns the gate verdict). If Java cannot be installed through the Ubuntu path above, record the fact, report it, and continue setup; do not claim Java-dependent analyzer readiness.
- Record installed versions in evidence after any install.

## Authentication: secret store first, Chrome fallback second

**Step 1 — authenticate only when needed and approved.** Tooling checks, readiness checks, and validation of an already-authenticated target do not by themselves require collecting new credentials. When new or missing authentication is required for the intended target, ask the user for setup information and store it in the runtime secret store: SFDX auth URL (format `[SFDX_AUTH_URL_FORMAT_REDACTED]`), instance URL, and target alias. Never ask the user to paste secrets into chat; request them through the runtime's secret store mechanism.

With the secret available, log in non-interactively by piping the value from the secret store through stdin:

```bash
<secret-store read command> | sf org login sfdx-url --alias <TARGET_ALIAS> --sfdx-url-stdin
```

`--sfdx-url-stdin` consumes standard input and must be the final token; placing another flag after it makes the command fail to parse. The secret-store read mechanism itself is the receiving runtime's interface — no confirmed OpenClaw spec exists for it yet `[ESTIMATED]`.

Prefer stdin. If a file is unavoidable, place it outside the repository, delete it immediately after login, and exclude your own temporary artifact from the later secret scan.

**Step 2 — only when the user states they cannot provide the secret.** Verify a Chrome binary exists on this machine, then launch the login from the agent's own PC (VPC) and ask the user to complete the browser login:

```bash
sf org login web --alias <TARGET_ALIAS> --instance-url <INSTANCE_URL> --browser chrome
```

If Chrome is absent, stop and report; do not install a browser.

Do not add `--set-default` in either path.

## Target binding and capability probes

```bash
sf org list --json
sf org display --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf org list metadata-types --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf org list limits --target-org <TARGET_ORG> --api-version <API_VERSION> --json
sf sobject describe --target-org <TARGET_ORG> --api-version <API_VERSION> --sobject Case --json
```

These command shapes are verified against local Salesforce CLI `@salesforce/cli/2.141.6` help output, the official CLI reference, and the project worklog. Recheck `--help` in the current shell before using flags that are not listed above.

## Forbidden

- Do not run deploy, retrieve, quick deploy, source tracking reset, Flow activation/deactivation, metadata update, data create/update/delete/upsert, permission assignment, package install/uninstall in the org, event publish, live endpoint probe, cleanup, or destructive changes.
- Do not run `sf org display --verbose`, `sf org auth show-access-token`, `sf org auth show-sfdx-auth-url`, `sf org auth show-user-password`, or any command whose purpose is to reveal credentials.
- Do not set a default org as a substitute for explicit target pinning.
- Do not paste login URLs, auth files, access tokens, browser callback URLs, or raw credential-bearing JSON into prompts, reports, source, or evidence. Secrets live only in the runtime secret store or transiently in stdin.
- Do not install anything beyond `@salesforce/cli`, the `code-analyzer` plugin, and Ubuntu `openjdk-17-jdk`. `@salesforce/cli` and `code-analyzer` require user approval; Ubuntu Java installation is allowed by this skill only after the required environment checks.

## Stop Conditions

Stop and ask for coordinator or user direction before continuing when target alias, org ID, username, environment type, expected instance domain, API version, user approval for Salesforce CLI/plugin install or login, or permission boundary is missing or contradictory.

Stop when Node.js is missing, an approved Salesforce CLI/plugin install fails, Java is missing but the environment is not confirmed Ubuntu with `apt-get`, or the user declines an install the sequence requires.

Stop if new or missing authentication is required but the approved secret-store request was not made. Do not collect credentials for tooling/readiness-only work or for an already-authenticated target that can be verified without new login.

Stop if any output includes unredacted credential material, or if a temporary credential file still exists after login. Redact or delete the local artifact, rerun a bounded secret scan, and route review to `salesforce-dev-review`.

Stop if the user cannot provide the secret and no Chrome binary is available for the fallback login.

Stop if setup evidence proves only a local developer org but the request requires a customer, sandbox, production, or PoC org. Report that as `[UNVERIFIED]` target fit rather than generalizing from the available org.

## Report

Lead with setup status, then evidence. State what was already installed versus installed now, the auth path used (secret store or Chrome fallback), the target org binding, local CLI/plugin versions, API version, commands run, redaction result including temporary-file deletion, unverified gaps, and the next skill that should handle the actual work.
