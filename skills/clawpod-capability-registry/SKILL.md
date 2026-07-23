---
name: clawpod-capability-registry
description: Discover, assess, install, validate, update, or roll back reusable AgentSkills and CLI Harnesses from the ClawPod capability registry. Use when an agent needs a missing capability, wants to avoid duplicating an existing one, must compare capability versions, or needs to verify, upgrade, or recover an installed capability.
---

# ClawPod Capability Registry

Use `https://github.com/Wondermove-Inc/clawpod-capabilities` as the canonical registry. Do not search other GitHub repositories for ClawPod capabilities.

## Workflow

1. **Frame the need**
   - Extract the user intent, required outcome, environment, side effects, and approval boundary.
   - Use direct execution for genuinely one-off work.

2. **Discover before creating**
   - Inspect capabilities already available in the current agent environment.
   - Read the canonical `registry/index.json`; compare candidates by description, type, compatibility, and version.
   - Reuse or improve an existing capability instead of creating a near-duplicate.

3. **Choose the boundary**
   - Choose an AgentSkill for reusable judgment, routing, domain knowledge, or a variable procedure.
   - Choose a CLI Harness for deterministic execution with typed inputs, stable output, explicit side effects, and machine-verifiable failure behavior.
   - Choose both when a Skill should select an operation and a Harness should execute it.

4. **Assess candidates**
   - Confirm registry identity and package path match.
   - Check OpenClaw and platform compatibility, prerequisites, safety classification, approval requirements, and limitations.
   - Prefer a stable compatible version. Do not silently cross a breaking version boundary.
   - Reject plaintext secrets, private endpoints, undeclared side effects, and untracked generated files.

5. **Install through the approved lifecycle**
   - Use the environment's first-class Skill or CLI Harness lifecycle surface. Do not invent commands or manually mutate managed lifecycle state.
   - Verify the declared digest when present.
   - Keep installation separate from risky invocation. Installation never authorizes credential use, production impact, external publication, or destructive action.
   - Obtain explicit approval for shared-state, elevated, credentialed, externally visible, destructive, or production-impacting actions.

6. **Validate before use**
   - Confirm required files and referenced paths exist.
   - For a Skill, verify frontmatter, positive triggers, nearby negative triggers, instructions, and fresh-agent discoverability.
   - For a Harness, verify its manifest, entrypoint, command discovery, structured output, and representative success and failure paths.
   - Run the documented smoke test through the real invocation path. File presence alone is not successful installation.

7. **Deliver the post-install onboarding handoff**
   - Immediately after validation, determine whether the capability requires login, OAuth consent, account linking, scopes, credentials, browser/device interaction, or tenant configuration.
   - If it does, do not report the capability as ready for use. Tell the user it is installed but not yet connected; explain the onboarding sequence, the account or tenant, permission categories, protected credential location, revocation path, and any app/client prerequisite.
   - Separate what the user must do (for example sign in, select an account, approve scopes, or confirm a device) from what the agent will do (open the managed browser, receive the callback, store credentials, and run verification).
   - Ask whether to start onboarding now. Do not begin credentialed onboarding until the user explicitly agrees in the current conversation.
   - If the user defers, record authorization as pending and provide the exact resume action.

8. **Record provenance**
   - Record id, type, version, source path, digest when available, installation location, validation result, approval decision, and onboarding readiness.
   - Report installation, verification, side effects, residual limits, rollback instructions, and the onboarding handoff when required.

## Update and Rollback

- Re-read the canonical registry before updating.
- Review compatibility and migration notes before changing versions.
- Preserve the last known-good version until the replacement passes validation.
- Roll back failed or unexpectedly changed versions and record the evidence.
- Never overwrite local modifications silently. Ask whether to preserve, migrate, or discard them.

## Failure Handling

- Distinguish registry unavailability, incompatibility, malformed packages, failed validation, missing approval, and backend failure.
- Retry only read-only or idempotent operations when failure is plausibly transient.
- Stop after partial side effects; report the verified state and safest recovery action.
- Never fall back to another repository when the canonical registry is unavailable.

## Completion Criteria

Complete only when the capability matches the intent, compatibility and safety were reviewed, installation used an approved lifecycle, a representative invocation succeeded, provenance and evidence were recorded, rollback is known, and remaining limitations were reported. For credentialed capabilities, completion of installation also requires a user-visible onboarding handoff; installation must not be presented as operational readiness while authorization is still pending.
