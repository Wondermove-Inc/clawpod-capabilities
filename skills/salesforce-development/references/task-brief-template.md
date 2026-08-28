# Task Brief Template — Salesforce Maintenance Work Order

Use this structure when writing or receiving a task brief for Salesforce maintenance work.
It extends the generic Task Brief contract (Goal / Background / Scope / Completion criteria)
with the Salesforce-specific sections proven in this repository.

`[VERIFIED]` worked example: `evidence/AX-MAINT-20260802-043/handoff/task-brief.md` (2026-08-02).

## Structure

### 1. Objective

One paragraph: what gap this work closes and why. Name the reviewer finding, verification
item, or customer request that motivates it. No speculation.

### 2. User requirements included

Bullet list of the user's constraints quoted or paraphrased faithfully — including what
the user excluded. Do not weaken requirements (e.g. "create a Case" must not become
"create or identify a Case").

### 2b. Background context

The brief author's pre-research, treated as authoritative by the executor: files and
metadata to touch (absolute or repo-relative paths), applicable conventions and rule IDs,
prior evidence to reuse, and known pitfalls (e.g. relevant `lessons.md` T-IDs). The
executor works from this section instead of re-exploring.

### 3. Target (org pin — all four values mandatory)

- Salesforce org alias
- Salesforce org id (15/18-char)
- API version
- Expected user

Every `sf` command in the work must pin this target explicitly (`DR-CMN-001`); the first
command after any handoff gate re-confirms org identity.

### 4. Planned bounded change

The exact metadata components to be added or modified, by name. Anything not listed here
is out of scope. Runtime-only actions (e.g. executing a fixture) are stated separately
from metadata changes (`DR-CMN-004`).

### 5. Acceptance (numbered, each independently checkable)

Write one numbered item per gate, in execution order. The proven set for a deploy-bearing
maintenance task includes:

1. Handoff artifact validates before any new org contact (when a handoff gate is in use).
2. First Salesforce command re-confirms target org identity.
3. Approved request record (Case) exists; assignee tagged via Chatter Mention (`DR-CMN-011`).
4. RED evidence: focused test fails before implementation exists.
5. GREEN evidence: focused tests pass after the minimal implementation.
6. Static analysis blockers zero for touched files (`DR-CMN-005`).
7. Check-only deploy succeeds before actual deploy (`DR-CMN-002`).
8. Pre-actual reviewer returns go.
9. Actual deploy attributed by explicit deploy ID, after-deploy test, and retrieve
   round-trip recorded (`DR-CMN-014`, `DR-CMN-013`).
10. Runtime verification produces the intended observable state, recorded as evidence.
11. Completion communicated on the request record (Case Chatter) with the same Mention.
12. The report's negative-claims item (see §6) is present.

Drop items that do not apply (e.g. no deploy → drop 4–9) rather than leaving them vague.

### 6. Non-requirements (negative claims — mandatory section)

Two lists, both required:

- **Out of scope**: what this work will not touch (orgs, credentials, external systems,
  destructive changes).
- **Not claimed**: what the final report must NOT assert even if adjacent evidence exists
  (e.g. "no claim that this fixture covers every async failure mode", "no production/customer
  org behavior claim"). This keeps `[VERIFIED]` tags honest.

## Rules for use

- Every acceptance item must map to evidence file paths under `evidence/<work-id>/`.
- The brief is frozen once work starts; scope changes require a revised brief (and a
  handoff revision when a handoff gate is in use).
- Rule IDs referenced above are defined in `dev-rules/common_rules.md`.
