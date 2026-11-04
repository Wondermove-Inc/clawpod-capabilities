---
name: soc-event-correlation
description: "Correlate security alerts and logs across devices into one incident: build the attack story (MITRE ATT&CK, Kill Chain) and recommend containment, eradication, and recovery. Use for alert triage, deciding whether an alert is part of a larger attack, and multi-alert or multi-device correlation — not raw SIEM search or detection-rule authoring."
---

# SOC Event Correlation

Turn scattered security alerts and logs into one incident: what happened, how far the attacker got, and what to do next. This is a method, not a SIEM connector; it works with whatever SIEM the site runs.

Use it when you have at least one alert or case and need to know whether it is part of a larger attack. For reading one alert or running one query, use the SIEM directly.

## 1. Get the data

Use the site's SIEM connection info (endpoint, index/space, auth); ask for it if you were not given it. Learn from the product's docs how to **search by pivot** (an entity — IP, host, user, hash, domain, URL — in a time window, across all sources) and **fetch by id**, and map its fields to the common event fields — see [data-access.md](references/data-access.md). Keep each search to a time window and a result cap.

## 2. Normalize before you link

Most bad correlations come from mismatched data, not bad reasoning.

- **Time:** use event time in UTC, not ingest time. Devices drift; treat events within a few minutes of each other as unordered unless the same device logged both.
- **Identity:** one user appears as `CORP\jkim`, `jkim@corp.com`, `j.kim`, and a SID — merge them through the directory (SID/UPN mapping), never by name similarity. Resolve an IP to the host that held it **at that moment** (DHCP, VPN, EDR records); IPs get reassigned.
- **NAT, proxy, VPN:** they hide the real source. Translate through their logs before linking on an IP.
- **Same event, several sensors:** a firewall, IDS, and proxy record of one flow is one event with corroboration, not three steps.

## 3. Investigate (loop)

1. **Seed:** fetch the triggering alert; take its entities and time. Start narrow (e.g. ±1h).
2. **Pivot:** search each entity in the window; collapse repeats (same actor/target/action → one event with a count; scans and sprays → one event with the target set).
3. **Expand:** pivot on new, specific entities (a hash, a user, a rare domain). An entity on hundreds of events (NAT, proxy, DNS server) is infrastructure — don't pivot on it. Widen the window backward to find the entry point.
4. **Scope sweep:** run each confirmed indicator (hash, domain, IP, account) across all hosts over a longer window (e.g. 30 days) to find every other affected system. No hit only clears hosts and sources you have logs for; list the rest as gaps.
5. **Stop** when no new useful entities appear. Note what you did not expand.

## 4. Link events into an attack story

Judge every link by its strength, strongest first:

| Strength | Link | Examples |
|---|---|---|
| Hard | Same identifier carried across events | logon/session id, process GUID or parent-child, flow 5-tuple, email message-id → click → download, a file-transfer record carrying the same hash |
| Strong | Cause → effect in a plausible order and time | login → session, exploit → new process, beacon → data transfer, new admin → lateral login |
| Medium | Shared rare entity | a hash, domain, or account seen on few hosts; first-time-ever access (user never on this host, domain never seen in the org) |
| Weak | Time proximity alone, or common/infrastructure entities | never link on these alone |

- Check rarity before trusting a shared entity: how many hosts/users touched it in the last 30 days. Rare means signal; common means noise.
- Order linked events into steps: entry point, what each step enabled, privilege changes, objective. Write missing links as gaps ("no initial-access evidence yet"); never fill them by assumption.
- Enrich linked entities with threat intel, asset criticality, and account privilege. Enrichment raises or lowers confidence in a link; it never creates one.
- Compare with past incidents (case notes, memory) when available.
- The chain is only as strong as its weakest link; that link sets your confidence.

Tag each step:

- **MITRE ATT&CK** technique (sub-technique when evidence shows it, e.g. T1071.001 Web Protocols). Map only what evidence supports; tactics with no evidence are your blind spots.
- **Kill Chain** furthest phase reached (recon → weaponization → delivery → exploitation → installation → C2 → actions on objectives; weaponization is rarely visible in logs). It sets urgency: before exploitation is a hunt; C2 or later is an active incident.

## 5. Check yourself

- Every claim cites at least one event id. Never invent an IOC, time, or log line.
- Weigh at least one alternative (benign admin activity, false positive) and look for evidence against your leading explanation.
- State confidence (high / medium / low) and why. "Insufficient evidence" with the data needed to decide is a valid result.

## 6. Recommend

Base actions on the scope you found: containment (block C2, isolate hosts, disable/reset accounts, revoke sessions), eradication (remove persistence, patch the entry point, rotate exposed secrets), recovery (image the host first when evidence matters, restore, watch for return). Split into **do now** and **verify first**; each action names its target and event ids. Execution is done with the capability that owns it.

## Result

Give the conclusion and confidence, the linked steps with ATT&CK/Kill Chain tags and event ids, the scope (affected hosts and accounts), gaps and alternatives, and the actions. Full pass: [worked-example.md](references/worked-example.md).
