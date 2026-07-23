# Scope profiles

For new agent onboarding in this workspace, request `workspace-max` in one consent interaction so the installed Harness command surface is available without repeated incremental grants.

`workspace-max` requests full Gmail, Gmail settings, Calendar, and Drive access plus identity scopes. These scopes can be sensitive or restricted and may require Google verification or a security assessment. OAuth access does not authorize individual sends, deletes, shares, invitations, ownership changes, or other side effects; those retain their command-level preview and approval gates.

Narrow profiles remain available only for explicitly requested constrained credentials. Never silently downgrade `workspace-max`, add unrelated Google services, use service accounts, or enable domain-wide delegation.
