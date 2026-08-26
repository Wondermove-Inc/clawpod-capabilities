# Google Workspace 0.3.7 OAuth file presence gate

- Authentication now checks that the selected OAuth authentication file exists and parses, without rejecting mode, UID, GID, ownership, symlink, or link-count metadata.
- Binding status no longer exposes permission health, and permission check/repair commands are retired.
- Binding registry parsing, alias selection, bounded reads, transactions, backups, rollback, OAuth behavior, endpoint/scope validation, and secret redaction remain intact.
- New credential files still use a private creation default where supported, but runtime does not enforce or repair filesystem metadata.
