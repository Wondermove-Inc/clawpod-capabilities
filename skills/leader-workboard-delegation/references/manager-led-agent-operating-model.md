# Manager-Led Agent Operating Model For Salesforce PoC (v2 — Two-Track Routing)

Date: 2026-08-02
Version: v2 — self-contained `docs/poc-sf-org/**` delivery copy, integrating the generic manager-led agent operating model and the Salesforce application note.
Language: English by user decision on 2026-08-02 — explicit exception to the repository language policy for agent-read baseline documents.
Status: [VERIFIED] Two-track routing, workboard card lifecycle, escalation rule, and Salesforce folder application boundary confirmed by user decision on 2026-08-02. Enforcement rate figure is [UNVERIFIED] (see Enforcement).

> **Terminology supersession note (2026-08-13).** Where this document says "workboard card", "Workboard-managed", or "Workboard-governed" for Track B delivery, the current practitioner-visible delivery record is a Task per SKILL.md (Tasks-first; Workboard is private per-agent progress only). The routing principles in this document — two-track routing, dynamic routing, independent review, proportional control — remain current.

## Delivery Boundary

This file is the canonical operating-model copy for `docs/poc-sf-org/**` delivery packages.

This file is the single consolidated operating-model source. OpenClaw agent creation may receive only `docs/poc-sf-org/**`, so this file is intentionally self-contained and must not require a parent-folder link to understand the model.

## Terminology Boundary

- **agent organization**: the ClawPod/OpenClaw agent organization, reporting line, authority boundary, assignment routing, and practitioner collaboration structure.
- **Salesforce org**: a Salesforce tenant instance, such as a production org or sandbox.

In this folder, Korean `조직` may refer to a human organization, an agent organization, or a Salesforce org depending on context. Confirm the meaning before planning, verifying, or reporting.

## Purpose

This document records the operating model for ClawPod-style independent agents used by the Salesforce PoC package. The model is not limited to Salesforce, but this copy includes Salesforce-specific application rules needed when only `docs/poc-sf-org/**` is delivered.

The model applies to any agent organization size. Roles, titles, and team composition are dynamic; the fixed concept is the authority boundary held by the leader agent.

## Core Rule

[VERIFIED] The leader agent is the authority boundary for task routing, track classification, workboard card creation, execution authorization, review routing, and follow-up reassignment.

Authority moves only through leader assignment. Information exchange, consultation, and questions between practitioner agents remain peer-to-peer and are not restricted by this model. This preserves the autonomous-collaboration architecture; the leader is an authority gate, not a message broker or central scheduler.

## Two-Track Routing

[VERIFIED] Every incoming work item is classified by the leader into one of two tracks before assignment.

### Track B — Workboard-managed work

Route to Track B when any of the following holds:

- the work is multi-step or involves more than one practitioner (analysis programs, planning, test campaigns, builds, releases);
- the work has material impact: external-state mutation, production systems, code or configuration change, cost commitment, customer-facing, legal, or data impact;
- the leader cannot confidently classify the work (fail-to-workboard: ambiguity defaults to Track B).

Track B requirements:

1. The leader creates a main workboard card for the objective.
2. The leader creates an execution card per practitioner assignment and records each execution card id in the main card. Forward links from the main card are the tracking mechanism.
3. Practitioners never create workboard cards. A practitioner's operations on its execution card are limited to: read, claim, comment, proof (evidence attachment), complete.
4. Plan-before-execution applies: the practitioner submits a plan on the execution card; the leader approves before execution.
5. Human approval is obtained before execution when the work crosses the HITL gate grades (production mutation, irreversible external change, spend above threshold, legal or customer commitments). The selected recipe `WORKFLOW.md` is the package-local source of truth for approval grades, triggers, required approver, approval evidence, timeout behavior, and the emergency rule; read the instantiated `HITL-POLICY.md` when one exists. Do not maintain a second trigger list or a second grade definition in this document.
6. Completion, evidence, gaps, and residual risk are reported on the execution card; the leader verifies final state through the ids recorded in the main card.

### Track A — Direct delegation

Use Track A when all of the following hold:

- a single practitioner can complete the work immediately;
- the work is read-only or has no material impact;
- no plan review is needed to bound the risk.

Track A requirements: none beyond the standing practitioner responsibilities. No card, no plan gate, no per-step approval. The practitioner reports the result to the leader.

### Track Escalation

[VERIFIED] If a Track A assignment turns out to require mutation or otherwise crosses into Track B criteria, the practitioner stops at the point of discovery and reports to the leader. The leader creates the workboard card(s), then work resumes under Track B. Practitioners do not self-promote work into Track B by creating cards, and do not continue mutation work without a card.

## Assignment Cycle (Track B)

1. The leader inspects available agents and current status.
2. The leader selects the practitioner and creates the execution card, linked from the main card.
3. The practitioner claims the card and submits a plan.
4. The leader reviews; requests revision or approves. The leader may approve a bounded multi-step plan spanning several practitioners in one review; per-hop re-approval is reserved for high-risk transitions.
5. Human approval is obtained where HITL grades require it.
6. The practitioner executes only the approved scope.
7. The practitioner records completion, evidence, gaps, and residual risk on the card.
8. The leader reviews the result via the main card links, re-checks agent status, and decides the next assignment.

## Dynamic Routing

[VERIFIED] There is no fixed route such as `Leader -> Development -> QA` or any other named sequence. Such strings, where they appear, are historical records of single assignment decisions, never templates. The next assignment depends on the approved objective, the latest completion report, open gaps, risk and required independence, current availability, and role capability.

## Handoff Meaning

[VERIFIED] Handoff of authority is leader-mediated: a practitioner reports completion on its card; the leader decides continuation, reassignment, independent review, or stop; the next practitioner receives a new execution card.

Peer-to-peer information exchange during execution (questions, context sharing, consultation) is permitted and encouraged. What practitioners may not do is transfer assignment authority to each other or treat a peer conversation as a completed handoff.

## Independent Review

For high-risk output (security, production mutation, externally visible deliverables), the leader assigns an independent reviewer or verifier who is not the producing practitioner. The leader's own plan approval does not substitute for independent verification of high-risk results (separation-of-duties: the producer must not control whether or when its output is checked).

## Practitioner Responsibilities

Each practitioner agent must:

- work only within the leader-approved assignment (Track B: the approved plan on the execution card; Track A: the delegation scope);
- state assumptions, dependencies, required approvals, and risks;
- use repository files, source-of-truth markers, and evidence rather than hidden conversation memory;
- mark claims as `[VERIFIED]`, `[UNVERIFIED]`, or `[ESTIMATED]`;
- stop and report when required context, authority, evidence, or capability is missing (including Track Escalation);
- report completion to the leader — on the execution card for Track B, directly for Track A.

## Source-Of-Truth Markers

[VERIFIED] `[VERIFIED]` / `[UNVERIFIED]` / `[ESTIMATED]` as previously defined. This is the single evidence taxonomy; do not introduce parallel marker sets.

## Salesforce Application

This Salesforce folder may add Salesforce-specific controls, such as target org verification, deploy approval, runtime verification, rollback planning, and evidence capture. Those controls are domain-specific additions. They must not create:

- a fixed practitioner sequence;
- a peer-to-peer practitioner handoff contract;
- a mandatory universal handoff schema for ordinary work;
- a Salesforce-only process as the general ClawPod/OpenClaw agent model.

In Salesforce work, the leader classifies and routes work per the two-track model. Salesforce-specific control: material Salesforce org mutation or other external impact is Track B work and requires human approval before execution, per the HITL gate grades referenced in Track B step 5.

## Skill Boundary

Role identity, reporting line, routing guidance, manager plan review, approval flow, and assignment status inspection are not Salesforce skills.

They belong to the organization/workflow/soul layer:

- organization membership, reporting line, authority, role boundaries, and routing guidance belong in `ORGANIZATIONS.md`-style documents and this Salesforce organization folder;
- the leader-led two-track routing, the Track B card and plan discipline, approval gates, dynamic reassignment, and reporting discipline belong in `WORKFLOW.md`-style documents and this manager-led operating model;
- each agent's identity, tone, responsibility interpretation, boundaries, and working principles belong in that agent's `SOUL.md`.

Capability skills are a separate layer from that organization / workflow / `SOUL.md` content. A capability skill never carries organization membership, reporting line, authority, or routing rules, and the organization/workflow/`SOUL.md` layer never substitutes for a capability skill. Skills are kept only when they provide a distinct technical capability or a safety gate that is not adequately represented by ordinary organization/workflow guidance.

[VERIFIED] The ClawPoD capability skill inventory for this package, reconciled on 2026-08-02 against `find salesforce-organizations/skills -name SKILL.md -type f | sort`, is:

Core Salesforce capability and gate skills:

1. `salesforce-development` — local Salesforce source planning, implementation, and verification reference routing;
2. `salesforce-dev-review` — independent read-only go/no-go review gate;
3. `salesforce-org-change` — explicitly authorized Salesforce org mutation safety gate.

Supporting Salesforce skills:

4. `salesforce-setup` — first-run Salesforce onboarding: tooling, credentials in the runtime secret store, authentication, target org binding, redacted readiness evidence;
5. `salesforce-org-inspection` — read-only org inspection with explicit target-org pinning, dependency and limits probes, evidence redaction, and stop conditions;
6. `salesforce-verification` — source, deploy-readiness, and runtime evidence verification without authorizing org mutation;
7. `salesforce-ui-verification` — UI behavior verification with URL-only org access and redacted evidence, no mutation.

Platform and support skills:

8. `leader-workboard-delegation` — routing a leader delegation to direct Track A or Workboard-governed Track B;
9. `clawpod-slack-channel-activation` — safe Slack channel activation with onboarding, approvals, and validation.

Role-facing `sf-*` skill wrappers and mandatory multi-stage `sf-*` gate chains are overspec for ordinary manager-led work. Use the leader's approved assignment, SoT markers, repository evidence, and proportional reviewer/org-change gates instead.

## Enforcement

[VERIFIED] Track routing and card discipline are defined in the workflow loaded at session initialization.

[UNVERIFIED] Instruction-level enforcement is estimated at ~80%+ compliance. This is not a hard guarantee: instruction-loaded rules are advisory to the runtime and can be dropped under context pressure.

Compensating control: periodic audit of mutation actions (file writes, deployments, external API calls) against workboard card references. A mutation without a corresponding Track B card is flagged and reviewed. Compliance rate should be measured from this audit, not asserted.

## Overspec Signals

[VERIFIED] A document, workflow, or skill is overspecified when it mandates, without a risk-based reason:

- a fixed practitioner sequence;
- workboard cards or plan gates for Track A work;
- a universal handoff schema or receiver-acknowledgement protocol between practitioners;
- immutable seals, hash locks, or revision locks on every transition;
- fail-closed validation before read-only analysis;
- long chains of mandatory gate skills where the Track B cycle is enough;
- a second evidence taxonomy duplicating the source-of-truth markers;
- machinery that makes agents depend on handoff packaging instead of the approved plan, markers, and repository evidence.

## Usage

Use this document as the baseline when reviewing agent organization documents, workflow documents, role documents, skill instructions, and domain-specific procedures in the `docs/poc-sf-org/**` delivery package. The expected result is dynamic, proportional control: workboard discipline where risk lives, direct delegation everywhere else.
