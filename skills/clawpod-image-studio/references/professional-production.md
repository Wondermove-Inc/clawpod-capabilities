# Professional AI Photo Production Procedure

Use this procedure for a complete professional production. All commands in this
document are local, non-networked, and non-billable. Provider calls remain behind
the existing `request.validate` → `request.estimate` → `request.prepare` →
`image.generate|edit` boundary, chained by the agent in one turn.

## 1. Intake and planning

1. Create a project with `project.create` and retain its revision.
2. Build the complete Creative Brief contract, then call `brief.save` with
   `expectedProjectRevision`. Use `brief.approve` only for a named human reviewer.
3. Compile the entire shot list with `shot.compile`. The compiler rejects unknown
   fields, implicit units, invalid enums, unbounded attempts, unavailable models,
   and unsupported required controls. Inspect it with `shot.list`.
4. Treat references, releases, identity, product truth, trademarks, regulated
   claims, and publication as human gates. A generated image is never evidence of
   rights or consent.

## 2. Production and review

1. Prepare each paid attempt through the existing guarded provider commands.
   Never place credentials in Studio records. Do not retry ambiguous submissions.
2. After a provider result exists, use `generation.register`; for an existing
   non-provider file use `candidate.register`. Registration only reads files under
   `<root>/artifacts` or explicitly staged `<root>/studio/inputs` and makes no call.
3. Run `qa.evaluate`. It deterministically verifies the registered hash, readable
   image contract, and detectable dimensions. It cannot approve creative work.
4. Run `critic.input` to create a canonical, hash-bound expert-review payload.
   Scores returned by any critic remain advisory for identity, product truth,
   brand-critical details, claims, creative acceptance, and rights.
5. A human records the select with `select.record`. Prefer directed work described
   by `revision.plan`; regeneration is a new branch and, when paid, a freshly prepared digest run in the same turn.

## 3. Finish, proof, and delivery

1. Produce new bytes without touching the selected source, then register the
   editable master and ordered recipe with `finish.record`.
2. Run QA on the exact master and use `master.approve` with a named human, role,
   asset hash, record revision, and proof condition.
3. Use `contact_sheet.create` for deterministic SVG review sheets and exact JSON
   manifests. They are visibly color-limited review proxies, never masters.
4. Use `delivery.prepare` to bind every path, hash, version, approval, provenance,
   destination, and external-visibility condition. Recompute and inspect it.
5. Use `delivery.package` only with an already-existing durable root. External
   delivery requires a separate publication approval identifier. ZIP metadata,
   ordering, names, and timestamps are normalized for reproducibility.
6. Finish with `audit.verify` and report all IDs, hashes, approvals, limitations,
   provenance, unresolved exceptions, and delivery/package digests.

Stochastic generation cannot guarantee identity, product geometry, logos,
typography, palette, or style continuity. Specify these with rights-cleared
references, exact constraints and tolerances, controlled edits, and set review.
