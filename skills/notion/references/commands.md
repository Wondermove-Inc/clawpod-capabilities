# Command routing

- Local/no credential: `auth.status`, `auth.onboarding.plan`, `diagnostics.doctor`, `operation.plan`, `resolve.id`, `resolve.url`, `markdown.validate`.
- Approved credential verification: `auth.onboarding.verify` normalizes identity/workspace and checks 1-50 typed roots with actionable sharing/capability diagnostics.
- Discovery/read: `search.query`, page/property/Markdown retrieval, bounded block trees, database/data-source/template retrieval, comments, users, and file-upload status.
- Guarded writes: page create/update/archive/restore, Markdown create/update, block append/update/delete, schema update, typed page/discussion/reply comments, and file-upload create/complete.
- Webhooks: verify HMAC against the raw body before parsing; dedupe by event id in the caller's durable store.

Enhanced Markdown is preferred for normal prose. Use blocks when exact nesting, unsupported content, or block identity matters. Database IDs are containers; data-source IDs are query/schema targets. Supply `allowedRoots` for writes; configured roots are enforced before preview and execution. Preserve `operation_id` and `request_digest` in caller-owned protected journal state, never the token or an unredacted sensitive body.
