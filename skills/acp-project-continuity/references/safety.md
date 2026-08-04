# Local state and runtime safety

Keep the state root on a trusted local filesystem with owner-only access. Supply absolute paths beneath one explicit workspace root. The Harness rejects path escape, symlink components, non-regular state, group/world-accessible state, oversized state, malformed structure, and stale revisions.

The registry stores only project ids, normalized paths, branch names, opaque non-secret session ids, lease tokens, expiry integers, and lineage metadata. Never pass credentials, authorization headers, environment dumps, prompts, task content, model output, or customer data. Secret-like input or persisted state is rejected.

Inject credentials and sensitive runtime configuration only through the agent/runtime's protected process environment or its approved secret facility. Keep those values out of Harness argv, stdout, state, handoff files, shell history, logs, and version control. A session id or lease token must be an opaque non-secret identifier; if a vendor treats one as a bearer credential, do not use this capability for it.

The Harness performs no Gateway, network, ACP, or vendor call. The Skill may instruct a first-class session runtime separately, but it must never send continuity state or secrets to an unapproved backend.
