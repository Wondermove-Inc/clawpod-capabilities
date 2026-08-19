---
name: soc-event-correlation
description: "Correlate security alerts and logs across devices into one incident: build the attack story (MITRE ATT&CK, Kill Chain) and recommend containment, eradication, and recovery. Use for alert triage, deciding whether an alert is part of a larger attack, and multi-alert or multi-device correlation — not raw SIEM search or detection-rule authoring."
---

# SOC Event Correlation

Turn scattered security signals into one defensible incident narrative plus a
response recommendation. This skill is a **method**, not a SIEM connector: it
tells the analyst agent *how* to correlate and *how* to recommend, independent of
which SIEM or security devices a site runs. It works the same at every deployment.

## When to use / not use

Use it when you hold at least one alert or a case and need to know whether it is
part of a larger attack, what the attacker did, and what to do next.

Do not use it as a log browser, a detection-rule editor, or a threat-intel
lookup — those are **inputs** to this method. If you only need to read one alert
verbatim or run a single query, use the SIEM query interface directly.

## Getting the data (SIEM-agnostic — read this first)

This skill assumes **no specific SIEM**. The SIEM differs per site (Splunk,
Elastic, QRadar, Sentinel, Chronicle, OpenSearch, Wazuh, …). Each deployment gives
the analyst agent the site's **SIEM connection info** (endpoint, space/index,
auth). Your job is to use that connection to pull the data the correlation
pipeline needs — whatever the product.

Procedure (full detail: `references/data-access.md`):

1. **Learn the connected SIEM first.** From the provided connection info and its
   own documentation, determine how to run a bounded, read-only search and how to
   fetch one record. Do not assume a query language.
2. Run the two primitives the pipeline needs, mapped to that SIEM:
   - **Search by pivot** — given an entity (IP, host, user, hash, domain) and a
     time window, return matching events across all connected sources.
   - **Fetch by locator** — given a stable alert/event id, return that record.
3. Normalize what comes back into the common event shape
   (`references/correlation-pipeline.md`).

Rules: read-only queries only, always bounded (time window + result cap); never
change detection rules, connectors, or cases beyond what a separate approved
action allows; never fabricate events. If you were not given connection info,
request it and pause — do not guess an endpoint.

## Investigation loop (start here)

Given a case or triggering alert, drive the pipeline as a **bounded loop**:

1. **Preflight** the SIEM connection — auth and scope (`references/data-access.md`).
2. **Seed** — fetch the triggering alert; extract its entities (IPs, hosts, users,
   hashes, domains) and its event time. Set an initial time window around that
   time — start narrow (e.g. ±1h) and widen deliberately.
3. **Pivot** — search by each seed entity within the window; normalize, aggregate,
   and add results to the graph (pipeline stages 1–3).
4. **Expand** — pivot on *new, high-value* entities the results reveal. Prefer
   specific entities (a file hash, a user, a domain) over high-cardinality or
   shared ones (a NAT/proxy IP) — those add noise, not signal.
5. **Stop** when any holds: no new high-value entities appear, the window is
   covered, a result/pivot budget is reached, or the picture is enough to decide.
   Record what you did not expand and why.
6. **Reconstruct and recommend** (pipeline stages 4–5); emit the report.

Every search stays bounded (time window + result cap). If the graph explodes on
one entity, that entity is infrastructure noise — down-weight it and stop pivoting
on it. A worked end-to-end pass: `references/worked-example.md`.

## The correlation pipeline (five stages)

Run these in order. Full detail: `references/correlation-pipeline.md`.

1. **Normalize** — map every event to a common shape: time, source device, actor,
   target, action, entities, raw locator. Never discard the locator.
2. **Aggregate / de-duplicate** — collapse near-identical and repeated alerts into
   representative events so hundreds of rows become a handful of facts.
3. **Correlate (graph)** — build a graph: nodes are events, edges are shared
   entities (spatial), closeness in time (temporal), and prerequisite→consequence
   links (causal). Clusters are candidate incidents.
4. **Reconstruct the scenario** — order each cluster into an attack story: which
   step enabled the next, across the kill chain.
5. **Recommend** — produce prioritized, evidence-anchored response actions.

## Choose the right correlation technique

Detail: `references/correlation-methods.md`.

- **Similarity-based** (shared attributes / time proximity) — cheap grouping of
  duplicates and fan-out. Cannot, by itself, prove a multi-step attack.
- **Sequence / causal** (prerequisite → consequence) — the core technique for
  multi-step and previously unseen attacks. Use it to link stages.
- **Case-based** (compare to prior resolved incidents) — classify and predict from
  history; anchors your confidence and your recommendation.

Apply all three; do not stop at similarity.

## Three analytical lenses (apply every time)

Detail: `references/attack-frameworks.md`.

- **MITRE ATT&CK** — map each correlated step to a technique/sub-technique. The set
  of mapped techniques is your coverage statement: what you can prove, and the
  gaps you cannot yet see.
- **Cyber Kill Chain** — locate the intrusion's furthest-reached phase
  (recon → delivery → exploitation → C2 → actions on objectives). This drives
  urgency.
- **Diamond Model** — for each hypothesis, fill adversary / capability /
  infrastructure / victim. Use it to generate and *test* hypotheses, not to
  decorate a conclusion.

## Guardrails for an AI analyst (non-negotiable)

Research on AI-driven SOCs flags hallucination, over-confidence, and poor
cross-environment generalization as the dominant failure modes. Defend against
them:

- **Evidence anchoring** — every claim cites at least one raw event locator. No
  locator, no claim. Never invent an IOC, a timestamp, or a log line.
- **Competing hypotheses (ACH)** — state at least two explanations (e.g. real
  intrusion vs. benign admin activity vs. false positive) and actively look for
  evidence that *refutes* the leading one before you commit.
- **Confidence, explicitly** — label each finding `high` / `medium` / `low` with
  the reason. Distinguish "confirmed", "suspected", and "insufficient evidence".
- **Escalate on uncertainty** — if evidence is missing or hypotheses stay tied,
  recommend the specific data to collect and hand off to a human. Do not force a
  verdict.
- **No unauthorized action** — this skill recommends; it does not execute
  containment. Blocking, isolating, or disabling accounts is a separate,
  approval-gated action.

## Output

Emit one structured incident report (schema: `references/output-schema.md`):
incident hypothesis and confidence, entity graph, kill-chain position, ATT&CK
technique list, an evidence-anchored timeline, competing hypotheses considered,
and prioritized response recommendations. Keep the human-readable summary and the
machine-readable object consistent.

## Response recommendations

Detail: `references/response-playbooks.md`. Frame recommendations as NIST /
SANS PICERL phases — **containment, eradication, recovery** — each action tied to
the evidence that justifies it and prioritized by asset value and confidence.
Separate "do now" (high-confidence containment) from "verify first"
(needs more evidence).

## References

- `references/data-access.md` — SIEM-agnostic query primitives and normalized fields
- `references/correlation-pipeline.md` — the five stages in depth
- `references/correlation-methods.md` — similarity / sequence / case techniques
- `references/attack-frameworks.md` — ATT&CK, Kill Chain, Diamond Model
- `references/response-playbooks.md` — containment / eradication / recovery
- `references/output-schema.md` — the incident report schema
- `references/worked-example.md` — one end-to-end pass
