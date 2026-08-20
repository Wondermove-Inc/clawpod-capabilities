# SOC/CSIRT extension pack

This pack **coordinates and reports** security work (handoffs, escalations, incident updates, closure). For the underlying analysis — correlating alerts into an incident, the attack story, ATT&CK/kill-chain mapping, and the response recommendation — use `soc-event-correlation`, then carry its result into these templates.

Separate confirmed facts, analyst assessment, and unverified hypotheses. Apply evidence-access and disclosure rules from the organization.

1. **Delegation/task:** case/classification, severity, affected assets/users, evidence source and handling, access restrictions.
2. **Peer help:** observed IOC/TTP, detection method, relevant telemetry, sensitivity, bounded analysis question.
3. **Upward status/decision:** exposure and business impact, legal/privacy/disclosure decision, decision authority, notification audience.
4. **Blocker/escalation:** severity, evidence-preservation need, containment authority, primary/backup contacts, escalation trace.
5. **Handoff:** case timeline, evidence custody and locations, active containment, unverified leads, contact and response status.
6. **Review/approval:** detection/response change, false-positive or coverage impact, validation data, rollback, approving authority.
7. **Incident update:** case ID, classification/severity, affected assets, IOC/TTP, confirmed impact, containment, contacts, next update.
8. **Completion/closure:** containment/recovery evidence, evidence retention, residual exposure, reporting obligations, lessons and tracked actions.
9. **No-response follow-up:** original contact, tracked responses, primary/backup route, urgency, paging/escalation trigger, safe default action.

Never expose restricted evidence merely to make a template complete. Reference its controlled location and access class instead.
