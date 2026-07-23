# Operations

Read: `repo.view`; `issue.list/get`; `pr.list/view/checks`; `run.list/view/logs`; `release.list/view`; `api.get`.

Mutations: `issue.create/comment/close/reopen`; `pr.create/comment/review/merge`; `run.rerun/cancel`; `release.create/upload`.

Always specify `owner/name`. Preview mutations with `dryRun=true`; after current explicit approval use `confirm=<command>`. Use an idempotency key in the surrounding workflow for retried creates. The Harness never automatically retries mutations.
