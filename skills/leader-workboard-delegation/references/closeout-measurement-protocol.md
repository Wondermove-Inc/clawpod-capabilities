# Track B Closeout Measurement Protocol

[VERIFIED] The operating model requires that the compliance rate of Track B delegation be measured from a periodic audit, not asserted (`references/manager-led-agent-operating-model.md:161`, "Compliance rate should be measured from this audit, not asserted."; the same document marks its enforcement rate figure `[UNVERIFIED]` at line 6).

This protocol defines how to run that audit. Run the measurement in the operating workspace, not in this repository.

## Sample

Take as the sample the N most recent closed Track B execution Tasks in the operating workspace, in reverse close order, with no filtering by outcome. The operator chooses N and keeps the same N across runs so results are comparable. [ESTIMATED] N = 20 is an adequate default for a first run — a judgment about audit effort versus signal, falsifiable if a 20-Task sample turns out to have too few failures to distinguish failing-field patterns.

Export each sampled Task to its own plain-text file containing the Task description, the practitioner start comment, and the practitioner completion summary, in that order. One file per Task. These exports are the audit input; everything below is computed over them.

## Metrics

Report each metric as a fraction with the raw counts, together with N and the sample window. Set no target or threshold for any metric: let the first run establish the baseline, and read later runs against that baseline.

- **Required-field presence rate** — the fraction of sampled exports for which `scripts/task-closeout-gate.py <export>` exits 0. Record the `MISSING`/`INVALID` field names printed by the failing runs, since the distribution of failing fields matters more than the rate alone.
- **Substantive-fill rate** — of the fields that the gate accepts, the fraction whose value carries real information about that specific task rather than filler. Judged manually: a value that would read identically on any other Task (for example `result: done`, `residual_risks: none` on a change that plainly carries risk) is filler.
- **Evidence-attachment rate** — the fraction of exports whose `evidence` field resolves to an artifact the auditor can actually open: a file path, a URL, a PR, a commit. A value that is syntactically evidence-shaped but unreachable counts as a failure.
- **False-done rate** — the fraction of completed Tasks whose evidence, on inspection, does not support the claimed result. Requires opening the evidence for each sampled Task that passed the previous metric.
- **Per-task overhead** — the count of mandatory coordination artifacts produced per Task (Tasks created, required comments, reviews) set against the size of the delivered change. Recorded so that a rising compliance rate bought with disproportionate coordination cost is visible rather than hidden.

## Model-contradiction check

For each observed failure or misrouted delegation in the sample window, record whether the operator or agent involved was following a superseded Workboard-model document instead of the Tasks-first procedure in `SKILL.md`, and name the document. [ESTIMATED] Treat a cluster of failures traceable to one superseded document as a documentation defect rather than a compliance defect, and fix it by correcting or retiring that document — this attribution is falsified if the same failures persist after the document is retired.

## Recording location

Record audit results in the operating workspace's own system of record — the leader coordination Task or its equivalent — alongside the sample window, N, and the raw counts behind each metric. Do not commit results to this repository; version only the protocol here, so that a later audit can state which revision of the protocol it followed.
