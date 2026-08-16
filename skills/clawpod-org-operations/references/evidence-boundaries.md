# Evidence boundaries, sources, and anti-patterns

## Evidence-backed invariants

Use explicit roles and decision authority, deadlines, impact, concise factual status, an expected next update, explicit handoff acceptance, verified closure, and tracked follow-up ownership.

Authoritative basis:

- Atlassian DACI, explicit driver/approver roles and agreed decision date: https://www.atlassian.com/team-playbook/plays/daci
- Team Topologies interaction modes, bounded collaboration and exit criteria: https://teamtopologies.com/news-blogs-newsletters/2025/2/21/team-topologies-interaction-modes-breaking-through-common-misconceptions
- GitHub PR templates and status checks, purpose, linked work, testing notes, and readiness evidence: https://docs.github.com/en/pull-requests/reference/managing-and-standardizing-pull-requests and https://docs.github.com/en/pull-requests/reference/status-checks
- Google SRE incident management and example postmortem, living incident documents, handoffs, recovery, and owned actions: https://sre.google/sre-book/managing-incidents and https://sre.google/sre-book/example-postmortem
- PagerDuty incident command and external communications, short factual updates, cadence expectations, handoff, and recovery confirmation: https://response.pagerduty.com/training/incident_commander and https://response.pagerduty.com/during/external_communication_guidelines
- NIST SP 800-61r3, current incident-response guidance and lessons learned: https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-61r3.pdf
- NIST SP 800-61r2, detailed primary/backup contacts and reporting mechanisms, used as legacy operational detail: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r2.pdf
- FIRST CSIRT Services Framework 2.1, escalation, correct contacts, response tracking, and situational reporting: https://www.first.org/standards/frameworks/csirts/csirt_services_framework_v2.1
- MITRE threat-informed operations, structured affected-system, detection, TTP, and impact records: https://healthcyber.mitre.org/wp-content/uploads/2021/11/774099090_WP_-Health-Delivery-Organizations-and-Ransomware_Final-11-23.pdf

## Design inferences and limits

Exact wording, color status, ordinary-office follow-up intervals, and product-specific fields are organizational choices, not universal standards. PagerDuty's numerical cadence is its practice, so require a next-update expectation without hardcoding the number. Team Topologies supports bounded collaboration, but the peer-help message fields are an adaptation. MITRE's cited record guidance is healthcare-oriented; generalize only the asset, detection, TTP, and impact structure. Use NIST r3 as current guidance and r2 only for useful operational detail.

## Anti-patterns

- Vague asks such as “check,” “ASAP,” or “improve,” without action, deadline, or success criteria.
- Confusing owner, reviewer, and approver, or distributing one decision across an unnamed group.
- Sending only a link without context, impact, evidence, and review focus.
- Mixing facts, assumptions, decisions, and requests in one undifferentiated paragraph.
- Assuming responsibility transferred without explicit acceptance.
- Repeating a no-response message without a new deadline, alternate path, escalation, or default action.
- Publishing empty cadence updates or omitting the next update expectation.
- Declaring completion without verification, residual risk, or tracked follow-ups.
- Hardcoding Jira, GitHub Issues, Workboard, or another task product instead of resolving the applicable `WORKFLOW.md` designation.
