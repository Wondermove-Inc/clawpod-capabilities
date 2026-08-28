# Deploy and Retrieve Reference

Use for explicitly authorized Salesforce deploy, retrieve, and check-only metadata movement.

## Prepare

- Confirm authorization and target identity using `authorization-boundary.md`.
- Define approved component list and explicitly excluded components.
- Prefer check-only or dry-run validation before actual mutation.
- Inspect component, test, and coverage results before requesting or using actual mutation authorization.
- Keep mutation units separate; do not combine development with cleanup, Flow activation, or endpoint changes unless authorization explicitly covers the combined unit.

## Execute

For every deploy or retrieve:

1. Reconfirm target identity.
2. Run the exact pinned command once within approved scope.
3. Record deploy, test, retrieve, and cleanup IDs whenever those operations occur.
4. Preserve stdout, stderr, timestamp, exit code, target identity evidence, and exact command with secrets removed.
5. Verify after state through the same surface used for before state.
6. Retrieve org-side metadata changes into source only when approved workflow requires it; record retrieve ID and inspect the actual diff.

Deployment success alone is not completion. Verify permissions, user visibility, Flow activation, runtime behavior, or data state separately when applicable.
