# Optional non-sensitive handoff

Shared storage is optional and is not a continuity backend. Bundled ACPX named sessions plus the local registry are the backend; prefer a local state file per trusted machine.

For an explicit cross-machine handoff, recommend `/workspace/shared/<org-id>/common/acp-projects/<project-id>/` and share only human-reviewed, non-sensitive handoff summaries, design decisions, test evidence, Workboard card ids, repository identity, branch, commit, agent kind, generation, closed/open intent, and verification instructions. Do not copy the live state file, lock file, session id, lease token, credentials, secret pointers, environment, prompts, source excerpts, or task output.

Never place Git repositories, worktrees, SQLite databases, continuity registry state, or active lease/lock files on shared SMB storage.

On the receiving machine, onboard locally and register the exact context. Start and attach a new local session lineage. Never treat a shared note as authority to bypass context validation, acquire a lease, or resume an id.
