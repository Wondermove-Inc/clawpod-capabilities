---
name: soc-event-correlation
description: "Correlate security alerts and logs across devices into one incident: build the attack story (MITRE ATT&CK, Kill Chain) and recommend containment, eradication, and recovery. Use for alert triage, deciding whether an alert is part of a larger attack, and multi-alert or multi-device correlation — not raw SIEM search or detection-rule authoring."
---

# SOC Event Correlation

Turn scattered security alerts and logs into one incident: what happened, how far the attacker got, and what to do next. This is a method, not a SIEM connector; it works with whatever SIEM the site runs.

Use it when you have at least one alert or case and need to know whether it is part of a larger attack. For reading one alert or running one query, use the SIEM directly.

## 1. Get the data

Use the site's SIEM connection info (endpoint, index/space, auth). If you were not given it, ask for it. Learn from the product's own docs how to run two things, then normalize results to the common event fields — see [data-access.md](references/data-access.md):

- **Search by pivot:** an entity (IP, host, user, hash, domain, URL) within a time window, across all sources.
- **Fetch by id:** one full record by its alert/event id.

Keep each search to a time window and a result cap so it returns quickly.

## 2. Investigate (loop)

1. **Seed:** fetch the triggering alert; take its entities and time. Start with a narrow window (e.g. ±1h).
2. **Pivot:** search each entity in the window; collapse duplicates and repeated alerts (same source/actor/target/action → one event with a count; scans and sprays → one event with the target set).
3. **Expand:** pivot on new, specific entities (a hash, a user, a rare domain). An entity that appears on hundreds of events (NAT, proxy, DNS server) is infrastructure — don't pivot on it.
4. **Stop** when no new useful entities appear or the picture is clear. Note what you did not expand.

## 3. Link events into an attack story

- **Shared entity** links events, strongly for specific entities, weakly for shared infrastructure.
- **Cause → effect** is what makes it an attack chain, not a coincidence: login → session, exploit → new process, C2 beacon → data transfer, new admin → lateral login. Similar events alone don't prove an attack.
- Order the linked events into steps: entry point, what each step enabled, privilege changes, objective. Write missing links as gaps ("no initial-access evidence yet"), never fill them by assumption.
- Enrich linked entities with threat intel, asset criticality, and account privilege. Enrichment raises or lowers confidence in a link; it never creates one.
- If past incidents are available (case notes, memory), compare with them to check your reading.

Tag each step:

- **MITRE ATT&CK** technique (sub-technique when evidence shows it, e.g. T1071.001 Web Protocols). Map only what evidence supports; tactics with no evidence are your blind spots.
- **Kill Chain** furthest phase reached (recon → weaponization → delivery → exploitation → installation → C2 → actions on objectives; weaponization is rarely visible in logs). It sets urgency: before exploitation is a hunt; C2 or later is an active incident.

## 4. Check yourself

- Every claim cites at least one event id. Never invent an IOC, time, or log line.
- Weigh at least one alternative (benign admin activity, false positive) and look for evidence against your leading explanation.
- State confidence (high / medium / low) and why. "Insufficient evidence" with the data needed to decide is a valid result.

## 5. Recommend

Group actions by containment (block C2, isolate host, disable/reset account, revoke sessions), eradication (remove persistence, patch the entry point, rotate exposed secrets), and recovery (restore known-good state — image the host first when evidence matters — and watch for return). Order by kill-chain phase reached, asset value, and confidence; split into **do now** and **verify first**. Each action names its target and the evidence behind it. Executing an action is done with the capability that owns it.

## 6. Report

Write a plain-language report a non-expert can act on, conclusion first — format in [report.md](references/report.md), full example in [worked-example.md](references/worked-example.md).
