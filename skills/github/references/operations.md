# Operations

Read: `repo.view`; `issue.list/get`; `pr.list/view/checks`; `run.list/view/logs`; `release.list/view`; `api.get`.

Mutations: `repo.create`; `issue.create/comment/close/reopen`; `pr.create/comment/review/merge`; `run.rerun/cancel`; `release.create/upload/body.update`.

Always specify `owner/name`. Preview mutations with `dryRun=true`; after current explicit approval use `confirm=<command>`. Use an idempotency key in the surrounding workflow for retried creates. The Harness never automatically retries mutations.

For `repo.create`, supply an exact `owner/name`, absolute non-symlink local source directory, visibility (`private`, `public`, or `internal`), description of at most 350 characters, and optional HTTPS homepage. Dry run verifies the source is a clean, non-bare Git work tree with an attached branch and full HEAD, and previews only the target, visibility, branch, HEAD, clean state, description length, and homepage, not the absolute source path. Confirm invokes `gh repo create` once with source, `origin`, and push, then separately reads repository metadata and the exact branch ref. Success requires exact target, requested visibility, source branch as default, an HTTPS repository URL, and remote SHA equal to source HEAD. Any post-start failure or mismatch is potentially committed and must not be retried.

For `release.body.update`, specify the exact tag and complete desired body. The preview performs an exact tag lookup and records the numeric release id, body diff, protected-field snapshot digest, and asset count. Confirm only that previewed operation. The mutation sends only the `body` JSON key to `repos/{owner}/{repo}/releases/{numeric-id}` and performs a separate readback. Success requires an exact body match plus byte-equivalent JSON values for all protected metadata and assets. `updated_at` is excluded because GitHub changes it for a body edit. Any mismatch is fail-closed and must be reported as potentially committed; do not retry the mutation.
