# Operations

Read: `repo.view`; `issue.list/get`; `pr.list/view/checks`; `run.list/view/logs`; `release.list/view`; `api.get`.

Mutations: `issue.create/comment/close/reopen`; `pr.create/comment/review/merge`; `run.rerun/cancel`; `release.create/upload/body.update`.

Always specify `owner/name`. Preview mutations with `dryRun=true`; after current explicit approval use `confirm=<command>`. Use an idempotency key in the surrounding workflow for retried creates. The Harness never automatically retries mutations.

For `release.body.update`, specify the exact tag and complete desired body. The preview performs an exact tag lookup and records the numeric release id, body diff, protected-field snapshot digest, and asset count. Confirm only that previewed operation. The mutation sends only the `body` JSON key to `repos/{owner}/{repo}/releases/{numeric-id}` and performs a separate readback. Success requires an exact body match plus byte-equivalent JSON values for all protected metadata and assets. `updated_at` is excluded because GitHub changes it for a body edit. Any mismatch is fail-closed and must be reported as potentially committed; do not retry the mutation.
