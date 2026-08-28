# Slack activation onboarding guide

Use this guide when `channels.slack` is missing, incomplete, or not yet validated for an OpenClaw runtime.

This guide is for collecting the minimum safe information needed to configure Slack. It is not permission to perform Slack app/admin changes, write config, restart Gateway, or run live Slack tests. Those actions require explicit approval.

## Non-negotiable secret rules

- Do not paste Slack token values, signing secrets, or private endpoints into chat, memory, Workboard, Tasks, prompts, logs, reports, screenshots, or examples.
- Record token classes and SecretRef locations only.
- Store credentials through a protected secret mechanism or approved SecretRef provider.
- If a user provides a credential in chat by mistake, do not repeat it. Move it into protected secret storage when appropriate and refer only to safe pointer metadata.

## Decide the Slack connection mode

### Socket Mode, recommended default

Ask for or confirm:

- Slack workspace where the app will be installed.
- Whether the requester has Slack app admin/install permission.
- Slack app display name.
- App-Level Token class with `connections:write` scope, stored through SecretRef.
- Bot Token class from the installed app, stored through SecretRef.
- Whether slash command support is needed and the command name, for example `/spring`.
- Approved human Slack user IDs and channel IDs by stable ID.

### HTTP Request URL mode

Use only when Socket Mode is not desired or not available.

Ask for or confirm:

- Public Gateway URL and Slack event request path.
- Signing Secret class, stored through SecretRef.
- Bot Token class from the installed app, stored through SecretRef.
- Whether each account needs a unique webhook path.
- Approval for Slack app Event Subscriptions / Interactivity / Slash Command URL changes.

## User-provided values checklist

Collect these as facts, not as secret plaintext values:

- Target runtime or pod name.
- OpenClaw config path, usually `/root/.openclaw/openclaw.json`.
- Slack workspace name or team ID when safely available.
- Slack app name.
- Connection mode: `socket` or `http`.
- Token classes available: app-level token, bot token, and signing secret only for HTTP mode.
- SecretRef provider choice: `env`, `file`, or `exec`.
- SecretRef ids or environment variable names, not secret values.
- Slash command mode: native commands or one configured command such as `/spring`.
- Approved slash command name.
- Approved human user IDs.
- Approved channel IDs.
- Desired `dmPolicy`, normally `allowlist`.
- Desired `groupPolicy` and `requireMention` behavior.
- Desired `session.dmScope`, normally `per-channel-peer` for multi-user DM/direct isolation.
- Whether config writes are approved.
- Whether Gateway restart/reload is approved.
- Whether live Slack tests are approved and exact test targets.

## Slack app setup checklist

Use the local OpenClaw Slack docs as source material before making changes:

```bash
/usr/lib/node_modules/openclaw/docs/channels/slack.md
/usr/lib/node_modules/openclaw/docs/tools/slash-commands.md
```

For Socket Mode:

1. Create a Slack app from a manifest or app settings.
2. Enable Socket Mode.
3. Create an app-level token with `connections:write`.
4. Add only the bot scopes needed for the approved capabilities.
5. Install the app to the workspace.
6. Store the bot token and app-level token through SecretRefs.
7. Configure the slash command only when `/spring` or another command is approved.

Common bot scopes depend on approved capabilities. Typical message integration uses app mentions, message history for approved surfaces, direct-message scopes, command handling, and chat write. File, pin, reaction, emoji, or user lookup scopes should be included only when those capabilities are needed.

For HTTP mode:

1. Confirm the public Gateway URL and request path.
2. Configure Slack Event Subscriptions and slash/interactivity URLs only after approval.
3. Store the signing secret and bot token through SecretRefs.
4. Use unique webhook paths for multi-account HTTP setups.

## SecretRef placement guide

Use one SecretRef object shape:

```json5
{ source: "env" | "file" | "exec", provider: "default", id: "..." }
```

Common file provider references:

```text
file:filemain:/channels/slack/botToken
file:filemain:/channels/slack/appToken
```

For file providers, validate only:

- file exists;
- ownership and permissions are restrictive;
- required JSON pointer entries exist and are non-empty;
- `openclaw secrets reload --json --timeout 30000` succeeds.

Do not print file contents.

## Safe config template

Use placeholders only. Replace them with SecretRefs and approved stable IDs before writing config.

```json5
{
  "session": {
    "dmScope": "per-channel-peer"
  },
  "channels": {
    "slack": {
      "enabled": true,
      "mode": "socket",
      "botToken": { "source": "file", "provider": "filemain", "id": "/channels/slack/botToken" },
      "appToken": { "source": "file", "provider": "filemain", "id": "/channels/slack/appToken" },
      "dmPolicy": "allowlist",
      "allowFrom": ["USER_ID_PLACEHOLDER"],
      "groupPolicy": "open",
      "requireMention": true,
      "dangerouslyAllowNameMatching": false,
      "allowBots": false,
      "commands": {
        "native": false,
        "nativeSkills": false
      },
      "slashCommand": {
        "enabled": true,
        "name": "COMMAND_NAME_PLACEHOLDER",
        "ephemeral": true
      }
    }
  }
}
```

For HTTP mode, replace `mode`, `appToken`, and Socket Mode assumptions with approved HTTP fields and a signing secret SecretRef.

## Approval gates before writing config

Before writing OpenClaw config, confirm:

- exact config path;
- redacted backup plan;
- fields that will change;
- SecretRef provider and ids;
- approved users/channels by stable ID;
- whether Gateway reload/restart is approved;
- rollback command or restore path.

Before changing Slack app settings, confirm:

- Slack workspace/app identity;
- exact Slack admin setting to change;
- whether public URLs or command names will change;
- expected impact on active users.

Before live tests, confirm:

- exact test user IDs and channel IDs;
- whether public channel posts are allowed;
- whether slash command tests are allowed;
- what success and failure mean.

## Validation checklist

Use pass/fail/unknown. Do not claim live readiness until the relevant approved tests pass.

- `channels.slack` exists and is enabled only when intended.
- Required SecretRefs resolve by status/shape only.
- Gateway active status reports Slack configured, running, connected, and probe ok.
- Approved DM test passes, if approved.
- Approved channel mention test passes, if approved.
- Approved slash command test passes, if approved.
- `/spring` channel-to-DM behavior is validated only if that policy and live test are approved.
- Direct DM replies are top-level unless a threaded-DM policy is explicitly approved.
- No substantive response body is leaked in public channels for channel-to-DM policy.

## Troubleshooting prompts

If Slack is not configured:

- Which mode is intended, Socket Mode or HTTP?
- Are the required token classes available in protected storage?
- Is the app installed to the target workspace?
- Does the Gateway active status see Slack as configured and connected?

If `/spring` does not respond:

- Is Slack using native command mode or a single configured slash command?
- Does the Slack app command name match the OpenClaw config?
- Does the command endpoint point to the active Gateway handler?
- Is the response invisible because it is ephemeral?

If a DM fails:

- Is the target ID a human user rather than the bot/app user?
- Is the sender allowlisted under `dmPolicy: "allowlist"`?
- Are bot users blocked by `allowBots: false`?

If a CLI/plugin SecretRef diagnostic appears:

- Compare it with active Gateway RPC status.
- Do not treat a local bootstrap diagnostic as an active runtime outage when active Gateway status and approved message tests pass.
