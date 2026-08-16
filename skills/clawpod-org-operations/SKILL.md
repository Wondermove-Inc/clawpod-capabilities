---
name: "clawpod-org-operations"
description: "Use when coordinating organizational handoffs, delegation, peer help, reports, reviews, approvals, escalations, follow-ups, incidents, or closure across agents and roles. Can select evidence-backed common, Engineering, SOC/CSIRT, or SRE templates and route shared work through the task service designated by the applicable WORKFLOW.md. Keep Workboard agent-local; use project-development for coding-session leases and the capability registry for package lifecycle."
---

# ClawPod Organizational Operations

Coordinate organizational work with explicit responsibility, authority, evidence, and next action. This is a prose-only Skill. It supplies judgment and templates, not a command, validator, task service, or execution surface.

## Procedure

1. Identify the actors, roles, authority boundaries, objective, urgency, and the one organizational action being requested.
2. For shared work, locate and read the applicable organization or agent `WORKFLOW.md` before choosing a system of record. Use exactly the shared task service designated there.
   - Do not carry a service choice across organizations or infer one from examples, prior work, or this Skill.
   - If no applicable `WORKFLOW.md` designates a shared task service, stop and ask which service is designated. Do not create or update shared work until resolved.
   - Keep Workboard local to one agent and its dispatched workers. Never treat it as a board shared with independent agents.
3. Select one of the nine families: delegation/task request, peer-help request, upward status/decision, blocker/escalation, handoff/shift change, review/approval request, incident update, completion/closure, or no-response follow-up.
4. Read [common-templates.md](references/common-templates.md). Then load exactly the relevant pack when context requires it: [engineering.md](references/engineering.md), [soc-csirt.md](references/soc-csirt.md), or [sre-incident.md](references/sre-incident.md). Combine common fields with the selected pack's extension for the same family.
5. Adapt detail to risk. State facts separately from assumptions, make the requested action and deadline explicit, identify the responsible owner and decision authority, and include a system-of-record reference without hardcoding a product.
6. Check [evidence-boundaries.md](references/evidence-boundaries.md) before presenting the result. Remove anti-patterns, preserve source limitations, and never claim acknowledgement, approval, delivery, or completion without runtime evidence.
7. Perform external writes only through the resolved service and its governing capability or approval rules. This Skill itself does not send, mutate, approve, or close anything.

## Selection rules

- Use **common** for ordinary cross-functional coordination.
- Add **Engineering** for code, repository, design, CI, deployment, or technical-review context.
- Add **SOC/CSIRT** for security events, evidence handling, affected assets, IOC/TTP, regulatory or legal decisions, and tracked response contacts.
- Add **SRE/incident** for service reliability, SEV operations, customer impact, incident command, mitigation, recovery, and live updates.
- If multiple packs apply, name the primary operating context and add only materially relevant fields from the secondary pack.
- Use `codex-claude-project-development` instead for coding-process onboarding, leases, or durable coding sessions. Use `clawpod-capability-registry` for capability package lifecycle.
