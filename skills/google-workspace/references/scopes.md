# Scope profiles

Prefer narrow profiles: `identity`, `gmail-metadata`, `gmail-read`, `gmail-compose`, `gmail-modify`, `gmail-settings`, `calendar-freebusy`, `calendar-read`, `calendar-events`, `calendar-manage`, `drive-file`, `drive-metadata-read`, `drive-read`, or `drive-manage`.

Broad Gmail and Drive scopes can be sensitive or restricted and may require Google verification or a security assessment. `drive.file` cannot search arbitrary Drive content. Gmail sharing/delegate administration and Calendar ownership transfer require an explicitly configured Workspace admin model. Never silently fall back to service accounts or domain-wide delegation.
