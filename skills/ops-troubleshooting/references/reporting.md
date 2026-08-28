# Reporting

Every troubleshooting turn ends with a report, even when nothing was changed. Keep facts, inference, and recommendations in separate sections.

## Structure

1. **Summary** — one sentence: symptom, cause (confirmed / probable), status (mitigated / fixed / open).
2. **Timeline** — first-seen, key evidence times, change times, action time, verification time. UTC from the evidence records.
3. **Evidence** — the findings (code, severity) and the commands that produced them (`argv`, host, `collectedAt`). Quote at most a few lines; never secrets.
4. **Cause** — mechanism, with the two independent signals that confirm it. Mark anything not confirmed as inference.
5. **Action taken** — plan id, action, target, `effects`, verification result. Or "none".
6. **Recommended changes** — owner, exact command or change, expected effect, rollback, risk. Not allowlisted actions live here.
7. **Follow-ups** — monitoring to add, capacity to review, hygiene to fix, tickets to open.

## Routing

- Handoff, escalation, incident update, or closure to other agents or roles → use `clawpod-org-operations` (SRE pack for reliability, SOC/CSIRT pack for security).
- Security analysis needed → `soc-event-correlation` with the evidence records attached.
- A durable document the room will reopen (postmortem, runbook, capacity review) → publish through `artifact-design` as a markdown artifact (`triage.*` sections map cleanly to headings and tables).

## Wording

Say what was observed and what was done. "Restarted `api` deployment (plan 3f2…), rollout complete at 10:14Z, restarts stable for 15 min" — not "should be fine now". If verification did not run, say it did not run.
