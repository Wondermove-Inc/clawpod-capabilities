# Attack Frameworks — the three lenses

Apply all three to every correlated cluster. They answer different questions:
ATT&CK = *what technique*, Kill Chain = *how far*, Diamond = *who/what, and is the
hypothesis sound*.

## MITRE ATT&CK — what technique

Map each correlated step to an ATT&CK tactic and technique/sub-technique.

- The tactic is the attacker's goal at that step (Initial Access, Execution,
  Persistence, Privilege Escalation, Defense Evasion, Credential Access,
  Discovery, Lateral Movement, Collection, Command and Control, Exfiltration,
  Impact).
- The mapped technique set is a **coverage statement**: it tells you what the
  evidence proves and — by the tactics with no mapped evidence — what you cannot
  yet see. Name the gaps.
- Map only what evidence supports. An unmapped step is "unknown technique", not a
  guessed one.
- Sub-technique precision matters for the recommendation (T1078 Valid Accounts vs.
  T1110 Brute Force lead to different containment).

## Cyber Kill Chain — how far it got

Place the intrusion's furthest-reached phase on the linear chain:

Reconnaissance → Weaponization → Delivery → Exploitation → Installation →
Command & Control → Actions on Objectives.

- The furthest phase reached drives **urgency**: pre-Exploitation is a hunt;
  C2/Actions-on-Objectives is an active incident needing immediate containment.
- The chain is a coarse timeline; ATT&CK gives the technique detail inside each
  phase. Use them together: kill chain for "how bad, how urgent", ATT&CK for
  "exactly what and how to stop it".
- Attacks are not strictly linear (ATT&CK tactics repeat and overlap). Use the
  kill chain for triage urgency, not as a rigid script.

## Diamond Model — hypotheses that survive testing

For each incident hypothesis, fill the four vertices and the edges between them:

- **Adversary** — who (even if only "unattributed actor, TTP cluster X").
- **Capability** — the tools/techniques/malware used.
- **Infrastructure** — the IPs, domains, C2, staging the attacker used.
- **Victim** — the assets, identities, and data in scope.

Use it to **generate and test** hypotheses, not to decorate a conclusion:

- Pivot along edges: victim↔infrastructure (who else talked to that C2?),
  capability↔infrastructure (does this tool imply other infra?). Each pivot is a
  new collection task that can confirm or refute.
- A hypothesis with empty vertices is weak — say so and collect to fill them.
- Competing hypotheses each get their own diamond; the one whose edges the
  evidence actually supports wins.

## Using the lenses together

1. Build the scenario (pipeline Stage 4).
2. Tag each step: ATT&CK technique + kill-chain phase.
3. For the cluster as a whole, build the Diamond(s) and pivot to close gaps.
4. Report: kill-chain furthest phase (urgency), ATT&CK technique list (what/gaps),
   Diamond (attribution + collection leads).

## Anti-patterns

- Mapping techniques the evidence does not support (inflates coverage, misleads
  response).
- Treating the kill chain as strictly sequential and dismissing later-phase
  evidence because an earlier phase is "missing".
- Filling Diamond vertices with speculation to look complete.
