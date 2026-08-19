# Correlation Pipeline — the five stages

Run in order. Each stage consumes the previous stage's output. Do not skip
ahead; a graph built on un-normalized events produces false links.

## Stage 1 — Normalize

Map every raw event to a common record so events from different devices can be
compared. Minimum fields:

- `time` (UTC, event time — not ingest time)
- `source` (device/product: firewall, IDS, EDR, proxy, DNS, email, identity)
- `actor` (who/what initiated: user, process, source IP)
- `target` (what was acted on: host, destination IP, URL, file)
- `action` (login, connection, block, exec, DNS query, email delivery…)
- `entities` (all pivotable identifiers: IPs, hostnames, usernames, file hashes,
  domains, ports)
- `severity` (device-reported)
- `locator` (a stable pointer to re-fetch the full record — **never dropped**)

Rules: keep original timestamps and time zones explicit; keep the locator; do not
enrich yet (enrichment is Stage 3); if a field is unknown, record `null`, never a
guess.

## Stage 2 — Aggregate / de-duplicate

Collapse volume before you reason. Hundreds of near-identical rows carry the same
one fact.

- **Duplicate collapse** — identical (source, actor, target, action) within a
  short window becomes one representative event with a count and a first/last
  time.
- **Fan-out collapse** — one source touching many targets (port scan, spray) or
  many sources hitting one target becomes one aggregated event with the set.
- **Threshold events** — "N failures in M minutes" becomes a single derived event.

Keep every underlying locator on the representative event; aggregation must be
reversible for evidence.

## Stage 3 — Correlate (build the graph)

Model correlation as a property graph. Nodes = aggregated events (and the
entities they touch). Edges express *why* two events might belong together:

- **Spatial (shared entity)** — same IP, host, user, hash, or domain. Strongest
  when the entity is specific (a hash) and weak when generic (a NAT gateway IP,
  a shared proxy). Down-weight high-cardinality/shared infrastructure entities.
- **Temporal** — events close in time within a bounded window. Order matters:
  A-before-B supports "A enabled B".
- **Causal (prerequisite → consequence)** — A produces a condition B requires
  (successful auth → session; exploit → new process; C2 beacon → data transfer).
  This is what distinguishes an attack chain from a coincidence.

Enrich *here*, and only to support edges: asset context (crown-jewel? exposed?),
identity context (privileged? service account?), and threat intel (is an entity a
known IOC?). Enrichment raises or lowers edge weight; it never invents an edge.

Connected components (clusters) above a confidence threshold are **candidate
incidents**. A single loud alert with no edges is a candidate too — but flag it as
unaggregated/isolated.

## Stage 4 — Reconstruct the scenario

Turn each cluster into an ordered attack story.

- Sort the cluster's events by causal then temporal order.
- Name each step by its kill-chain phase and ATT&CK technique
  (`references/attack-frameworks.md`).
- State the link: "step *i* enabled step *i+1* because …", each with a locator.
- Identify entry point, pivot points, privilege changes, and objective (what the
  attacker was after: data, persistence, ransom staging).
- Note missing links explicitly ("no evidence of initial access yet") — a gap is a
  finding and a collection task, not something to fill with assumption.

## Stage 5 — Recommend

Produce prioritized response actions (`references/response-playbooks.md`), each
tied to the evidence that justifies it and to the affected asset. Separate
high-confidence "do now" containment from "verify first" steps that need more
evidence. Attach the residual gaps and the confidence of the whole incident.

## Pipeline hygiene

- Re-run stages 2–3 when new events arrive; correlation is incremental, not
  one-shot.
- Keep the graph and the timeline in sync with the raw locators at all times.
- If Stage 1 input is empty (no data seam), stop and report; never proceed on an
  empty or assumed event set.
