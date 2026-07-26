# Operation selection

Use read commands before writes. Run `system.preflight` and `system.validate`; refuse execution when source, tree, patch, dependency lock, installed runtime, plaintext `.env`, or source-symlink checks fail.

Use `project.create/inspect/plan`, then `run.prepare`. Each prepared operation is one of:

- a stage declared by the selected pinned pipeline manifest,
- an explicit `{checkpoint: stage}` gate,
- a typed OpenMontage tool call with provider/model/input/timeout metadata.

`run.prepare` binds the pipeline manifest, normalized tool/provider contract, plan digest, provider set, per-operation ceilings, and total ceiling. `run.start` snapshots the complete intent into the job; workers never reread the mutable project intent. External start/resume requires exact ceiling equality, future expiry, and an approval binding digest over the intent, provider set, operation digests, cost, reference, and expiry. Provider-backed jobs must receive approved secrets through environment or mode-0600 file injection in the starting process; detached workers inherit them ephemerally and never persist them. Jobs recheck approval expiry and remaining authorization immediately before every provider call, checkpoint every completed operation, reconcile tool-reported cost, stop at explicit human gates, reject ceiling overruns, detect lost or PID-reused workers, and preserve partial artifacts. Resume is allowed only from awaiting/failed/cancelled state, requires a matching immutable checkpoint, and permits one claimed descendant.

Checkpoint approval is bound to the exact awaiting job, intent digest, stage, real project-relative artifact path and digest, approval reference, and future expiry. The worker independently verifies that binding before continuing.

Use `stage.prepare/validate/commit` for Skill-produced canonical stage artifacts. Use `tool.prepare` followed by `tool.run` for a bounded individual OpenMontage tool. Path-bearing inputs require `projectId`, remain project-relative in the approval digest, and are materialized only after boundary and symlink checks. Raw ffmpeg arguments reject absolute paths, traversal, network URLs, and secret-like values.

Run `qa.run` before completion. It uses real ffprobe metadata for container, duration, streams, frame rate, audio, subtitles, delivery extension, size, and artifact digest. Optional audio/subtitle absence is reported rather than hidden.

Backlot is optional and loopback-only. `backlot.start` owns the exact process identity; `backlot.stop` requires confirmation plus the owner nonce and refuses PID reuse. Browser opening remains delegated to an approved browser/desktop capability.

`install.plan-update` hashes the complete mutable source surface. `install.apply-update` revalidates unchanged source, stages by byte-copy without `.env` or Git metadata, rejects escaping dependency symlinks, writes a runtime lock, validates before and after activation, rotates the last-known-good backup only after success, and restores the previous runtime if activation fails. `install.rollback` preserves the failed candidate, validates the restored runtime, and restores the prior active runtime if rollback validation fails. These remain separate explicit mutations.
