# Slack file delivery reference

Use this reference when an OpenClaw agent needs to deliver a file through Slack or explain why a Slack file attachment failed.

This is operational guidance, not approval to upload files. Live/public/channel file delivery requires explicit approval for the exact destination and artifact.

## Safety boundary

Before converting or uploading any artifact:

- confirm the source artifact is the intended current version;
- check that the artifact does not contain credentials, tokens, signing secrets, private endpoints, private keys, or credential-bearing config;
- avoid copying secret-bearing content into chat, memory, Workboard, Tasks, logs, screenshots, prompts, proposal examples, or durable references;
- record only safe metadata, such as artifact type, allowed local path category, upload status, and non-secret destination.

If the artifact may contain sensitive data, stop and ask for a safer redacted artifact or explicit handling instructions.

## Current failure modes

### Markdown file attachment

In the current OpenClaw Slack file delivery path, direct `text/markdown` attachment delivery may be rejected by the OpenClaw/Slack media policy. Do not state this as a universal Slack platform rule. Scope the finding to the active OpenClaw Slack file attachment path and cite the observed failure or source check.

Recommended handoff for a markdown report:

1. Confirm which `.md` file is the current source of truth.
2. Confirm it is safe to render and upload.
3. Convert the markdown report to PDF.
4. Upload the PDF from an allowed OpenClaw media root.

### Local path outside allowed media roots

A file under `/workspace` may be readable by the agent but still fail media upload if it is outside the active local media roots. Do not treat workspace readability as Slack upload permission.

OpenClaw local media access checks require the file path to resolve under an allowed media root. In the default root/runtime layout, allowed roots are derived from:

- preferred OpenClaw temp directory, normally `/tmp/openclaw` when available;
- config media directory, normally `/root/.openclaw/media`;
- state media directory, normally `/root/.openclaw/media` in the default layout;
- state canvas directory, normally `/root/.openclaw/canvas`;
- state workspace directory, normally `/root/.openclaw/workspace`;
- state sandboxes directory, normally `/root/.openclaw/sandboxes`.

If `OPENCLAW_STATE_DIR`, `OPENCLAW_CONFIG_PATH`, `OPENCLAW_HOME`, or agent-scoped media roots are configured differently, verify the effective roots from the active runtime before writing a durable diagnosis.

## Safe PDF upload workflow

Use this workflow for a non-secret markdown report that should be attached in Slack:

1. Identify the current `.md` source artifact and its owner.
2. Confirm the artifact is not secret-bearing.
3. Convert the markdown to PDF using an available local converter.
4. Copy the PDF to an allowed media root, preferably `/root/.openclaw/media/` in the default runtime.
5. Upload the PDF through the approved message/file delivery tool.
6. Treat tool success as transport evidence only. It does not prove the underlying task is complete unless the source of truth is also updated.
7. Record the non-secret artifact path category, upload result, and destination. Do not record signed URLs, token-bearing values, or private file contents in durable skill guidance.

## Eval checklist

- No plaintext secrets or token-looking examples are present.
- The guide does not claim that all Slack markdown uploads are universally blocked.
- The guide separates local file readability from allowed media upload roots.
- Allowed roots are framed as effective runtime/default-root facts, not immutable platform constants.
- Uploads, public file posts, and live Slack tests remain explicit-approval actions.
