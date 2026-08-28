---
name: "clawpod-slack-channel-activation"
description: "Safely activate Slack with onboarding, delivery refs, approvals, and validation."
---

# ClawPoD Slack Channel Activation

Use this skill when a user asks to set up, activate, troubleshoot, validate, or make reusable the native OpenClaw Slack channel/message integration for an OpenClaw agent or runtime.

This skill covers OpenClaw native Slack channel activation. The canonical config target is `channels.slack`, not `skills.entries.slack`.

## Safety and approval boundaries

Never expose Slack token values, token prefixes, signing secrets, app tokens, bot tokens, user tokens, private endpoints, or credential-bearing config contents.

Use protected secret storage and SecretRefs only. Do not store plaintext secrets in memory Markdown, Workboard comments, Tasks, chat, reports, logs, prompts, screenshots, or proposal examples.

Stop for explicit approval before any of these actions:

- writing OpenClaw config;
- changing Slack scopes, app manifest, slash command URLs, event subscriptions, interactivity URLs, app installation state, or app admin settings;
- restarting or reloading a Gateway when it may affect active users;
- broadening allowlists, workspace-wide routing, channel membership, or group policy;
- reading private history beyond the explicitly approved target;
- live/public/channel test posts, files, pins, reactions, or app mentions in a non-test target;
- destructive changes, secret rotation/deletion, production/public release, or irreversible routing changes;
- creating, revising, applying, or replacing this skill outside the approved Skill Workshop lifecycle.

Prefer stable Slack IDs (`U...`, `C...`, `D...`) over names. Keep `dangerouslyAllowNameMatching: false`, `allowBots: false`, and `dmPolicy: "allowlist"` unless the user explicitly approves a narrower or broader change and the risk is recorded.

## Required Workboard handling

For multi-step Slack activation, routing-policy, troubleshooting, or skill-lifecycle work:

1. Create or update a Workboard card before config, code, live Slack, or Skill Workshop lifecycle changes.
2. Record owner, scope, approval boundaries, Slack targets, SecretRef strategy, evidence requirements, blockers, and next action.
3. Decompose if the work needs planning, config, validation, troubleshooting, eval, implementation, or final review.
4. Use wake-guards while waiting on restart, user-side Slack validation, another agent, or external approval.
5. Do not complete the card until active runtime validation and requested live Slack validation pass, or a blocker with owner/reason/next action is recorded.

## Onboarding when Slack is not configured

If `channels.slack` is missing, incomplete, or token/config values are unknown, use the onboarding guide before changing config:

```text
references/onboarding.md
```

The onboarding guide defines:

- the user-provided values needed before installation or activation;
- Slack app setup choices for Socket Mode and HTTP mode;
- which token classes are needed without recording token values;
- SecretRef placement options for env, file, or exec providers;
- safe OpenClaw config templates with placeholders only;
- approval gates for config writes, Slack app/admin changes, Gateway reloads, and live tests;
- validation and troubleshooting steps that do not imply live readiness before approved tests pass.

Do not ask the user to paste credentials into chat. If a credential must be stored, use the protected secret mechanism or an approved SecretRef storage flow, then record only safe pointer/path metadata.

## Slack file and message delivery references

Use these references when Slack delivery troubleshooting or reusable delivery guidance is in scope:

```text
references/slack-file-delivery.md
references/slack-message-delivery.md
```

`references/slack-file-delivery.md` covers safe file attachment handling, including current OpenClaw media-root constraints, markdown-to-PDF handoff, and no-secret checks before upload.

`references/slack-message-delivery.md` covers message delivery behavior for top-level channel replies, threaded replies, and status indicator targeting. It separates final reply routing from transient status/typing indicator routing.

These references are guidance only. They do not authorize config writes, runtime patches, Gateway reloads, Slack app/admin changes, file uploads, channel posts, or live tests without the approval gates above.

## Final artifact requirements

When this skill is created or updated, deliver:

- skill/proposal name;
- proposal id if available;
- status such as pending/applied;
- description;
- onboarding reference path when added;
- delivery reference paths when added;
- eval summary;
- final review verdict;
- Workboard card id and completion state.
