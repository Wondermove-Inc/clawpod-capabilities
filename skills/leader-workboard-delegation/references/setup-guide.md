# leader-workboard-delegation setup/reference guide

## Purpose

Use this short reference when installing, validating, or invoking the `leader-workboard-delegation` skill in an OpenClaw/ClawPoD workspace.

## Recommended workflow hook

Add only a narrow invocation rule to the governing workflow file. Do not copy Track A/Track B mechanics into workflow documents because the skill is the source of truth for routing details.

Recommended wording:

```md
Before work begins, leader/coordinating agents must use `leader-workboard-delegation` to classify any practitioner-delegable work into direct delegation (Track A) or Tasks-governed delegation (Track B).
```

## Expected installation layout

```text
skills/leader-workboard-delegation/
  SKILL.md
  references/
    setup-guide.md
    manager-led-agent-operating-model.md
    workboard-leader-practitioner-delegation-guide.md
  scripts/
    eval-leader-workboard-delegation-skill.py
```

## Quick validation checklist

1. `SKILL.md` frontmatter description is under 160 bytes.
2. `SKILL.md` says Track A is direct only for single-practitioner, immediate, read-only/no-material-impact work with no plan-review need.
3. `SKILL.md` says Track B applies when Track A criteria fail, including multi-step, multi-practitioner, material-impact, uncertain, review/follow-through, or evidence-tracked work.
4. Track B procedure requires leader-created related execution cards, not parent/child dependency links for concurrent delegation.
5. Required Track B fields include practitioner id, role owner, scope, non-goals, expected output or done-when criteria, evidence, residual risk, and next responsible role.
6. Support references resolve relative to the skill directory.

## Invocation expectation

When a leader/coordinating agent is about to create Workboard cards for practitioner delegation, the agent should read or otherwise apply this skill before calling Workboard creation tools. The expected decision is:

- Track A: do not create Workboard cards, delegate directly.
- Track B: create a leader SoT card and leader-created related practitioner execution cards with explicit cross-references.

## Non-goals

This setup guide is not a CLI harness, validator, or replacement for `SKILL.md`. It must not authorize production, external, destructive, credential, secret-bearing, legal, payment, release, or failed-gate-risk actions.
