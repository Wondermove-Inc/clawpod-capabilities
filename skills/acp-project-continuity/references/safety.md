# State, execution, and approval safety

Keep state on a trusted owner-only local filesystem. The Harness rejects escape, symlinks, non-regular files, unsafe modes, oversized/malformed state, stale revisions, non-canonical git roots, and branch/HEAD/cwd drift.

State is limited to project identity, ACPX session name/non-secret identifiers, generation, lease, and completion metadata. Prompts travel only on stdin to a bounded run; raw ACPX JSON, assistant output, prompts, environment, and credentials are never persisted or logged. If a session identifier is bearer-sensitive, stop.

Read/search approval does not authorize writes, commands, network, rotation, or close. Ask separately before expanded effects. Non-interactive permission requests fail closed. Failure releases only the owned lease and leaves an existing lineage unchanged.

Claude secrets require protected `exec.useSecrets` process injection and never enter chat, argv, Harness/Gateway input, files, handoffs, reports, or logs. The Harness never calls Gateway and requires no OpenClaw runtime changes.
