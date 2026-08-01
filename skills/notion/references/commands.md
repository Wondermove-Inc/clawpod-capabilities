# Command routing

- Local/no credential: `auth.status`, `auth.onboarding.plan`, `diagnostics.doctor`, `resolve.id`, `resolve.url`, `markdown.validate`.
- Discovery/read: `search.query`, `page.retrieve`, `page.property.retrieve`, `page.retrieve_markdown`, block/database/data-source retrieval, comments, users, file-upload metadata.
- Guarded writes: page create/update/archive/restore, Markdown create/update, block append/update/delete, schema update, comment create, file-upload create.
- Webhooks: verify HMAC against the raw body before parsing; dedupe by event id in the caller's durable store.

Enhanced Markdown is preferred for normal prose. Use blocks when exact nesting, unsupported content, or block identity matters. Database IDs are containers; data-source IDs are query/schema targets.
