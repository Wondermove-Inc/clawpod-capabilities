# Slack message delivery reference

Use this reference when Slack replies are configured to post as top-level channel messages while the user still expects OpenClaw status or typing indicators to appear.

This is implementation and troubleshooting guidance. It is not proof of live Slack readiness, and it does not authorize runtime patching, source changes, Gateway reloads, or live Slack tests without explicit approval.

## Delivery concepts

Keep these concerns separate:

- final reply routing: where the assistant's user-visible answer is posted;
- status indicator targeting: where transient status or typing indicators attach while work is in progress.

Disabling threaded final replies should not automatically disable status indicator targeting.

## Expected behavior

When `replyToModeByChatType.channel` or `replyToModeByChatType.group` is configured as `off`, a normal top-level channel/group inbound message should produce a top-level final reply.

The status indicator should still have a target:

- top-level inbound message with reply mode `off`: final reply thread timestamp is absent, status target is the inbound message timestamp;
- top-level inbound message with reply mode `all`: final reply thread timestamp and status target are both the inbound message timestamp;
- real inbound Slack thread reply: final reply thread timestamp and status target both use the inbound thread timestamp.

## Source-level implementation guidance

In the Slack adapter helper that resolves thread targets, do not derive the status target directly from the final reply thread target.

Conceptual shape:

```text
replyThreadTs = isThreadReply ? incomingThreadTs : replyToMode == all ? messageTs : undefined
statusThreadTs = isThreadReply ? incomingThreadTs : messageTs
```

Preserve the existing source names, types, and formatting of the OpenClaw source repository. The important requirement is that status targeting is not coupled to final reply threading.

## Regression coverage to request

Ask for unit or integration coverage around the Slack thread-target helper:

1. Top-level inbound, reply mode `off`:
   - final reply thread target absent;
   - status target equals inbound message timestamp.
2. Top-level inbound, reply mode `all`:
   - final reply thread target equals inbound message timestamp;
   - status target equals inbound message timestamp.
3. Real inbound thread reply:
   - final reply thread target equals inbound thread timestamp;
   - status target equals inbound thread timestamp.

## Validation and reporting boundary

A runtime patch or source change is not complete until the approved validation has run. Report separately:

- source or runtime file changed;
- syntax/static checks run;
- Gateway reload or restart approval and result;
- Slack web or client observations, if live tests were approved;
- known client rendering limits;
- rollback path.

Slack client status/typing surfaces may render differently across web, desktop, and mobile clients. Treat client-specific observations as evidence, not universal proof.

## Eval checklist

- Final reply routing and status indicator targeting are described as separate concerns.
- Top-level final reply behavior is preserved when reply mode is `off`.
- Real inbound thread replies still use the inbound thread timestamp.
- The reference does not claim live Slack readiness without approved live tests.
- The reference does not change `/spring`, app mention, or direct DM routing policy.
- Runtime/source changes, Gateway reloads, and live Slack tests remain approval-gated.
