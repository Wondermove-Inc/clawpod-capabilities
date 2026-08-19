# Output Schema — the correlated incident report

Emit one report per candidate incident. Keep the human-readable summary and the
machine-readable object consistent — the summary must not claim anything the
object cannot back with a locator.

## Shape

```json
{
  "incident": {
    "id": "string (stable, e.g. derived from the primary entity + first seen)",
    "title": "one-line description",
    "hypothesis": "the leading explanation in one sentence",
    "confidence": "high | medium | low",
    "confidence_reason": "why this level, in terms of edge strength and gaps",
    "status": "confirmed | suspected | insufficient_evidence",
    "kill_chain_phase": "furthest phase reached",
    "severity": "critical | high | medium | low",
    "first_seen": "UTC", "last_seen": "UTC"
  },
  "entities": [
    { "type": "ip|host|user|hash|domain|url|file", "value": "string",
      "role": "source|target|c2|victim|infrastructure",
      "context": "asset/identity/threat-intel notes", "is_ioc": true }
  ],
  "attack_mapping": [
    { "step": 1, "tactic": "ATT&CK tactic", "technique": "Txxxx(.yyy) name",
      "kill_chain_phase": "phase", "evidence": ["locator", "..."] }
  ],
  "timeline": [
    { "time": "UTC", "step": 1, "summary": "what happened",
      "link_reason": "why this enabled the next step (or 'entry')",
      "evidence": ["locator"] }
  ],
  "graph": {
    "nodes": ["event/entity ids"],
    "edges": [ { "from": "id", "to": "id",
                 "type": "spatial|temporal|causal", "weight": 0.0 } ]
  },
  "competing_hypotheses": [
    { "hypothesis": "alt explanation (e.g. benign admin / false positive)",
      "supporting": ["locator"], "refuting": ["locator"],
      "verdict": "rejected | open | leading" }
  ],
  "gaps": [
    { "missing": "what evidence is absent",
      "collect": "the specific query/telemetry to obtain it" }
  ],
  "recommendations": {
    "do_now": [
      { "phase": "containment|eradication|recovery", "action": "imperative",
        "asset": "target", "evidence": ["locator"], "effect": "expected result",
        "reversible": true, "blast_radius": "scope" }
    ],
    "verify_first": [
      { "action": "imperative", "needs": "evidence to gather first",
        "evidence": ["locator"] }
    ]
  }
}
```

## Rules

- **Every** `attack_mapping`, `timeline`, and `recommendations` entry carries at
  least one `evidence` locator. An entry with no locator is invalid — drop it or
  move the claim to `gaps`.
- `status: insufficient_evidence` is a valid, expected outcome. Use it with a
  populated `gaps` list instead of forcing a verdict.
- `confidence` reflects edge strength minus down-weights
  (`references/correlation-methods.md`), not how plausible the story feels.
- Keep `competing_hypotheses` non-empty: at least the leading one plus one
  alternative (commonly "false positive / benign activity") with its verdict.
- The `graph` must reference the same events cited in `timeline`; the report is
  one consistent object, not parallel narratives.

## Writing the report (human-readable — this is the primary deliverable)

The JSON object is supporting data. **The report a person reads is the main
output**, and it must be understandable by a non-expert — an on-call responder or
a manager — **without opening the JSON or the raw logs**. Write it logically, in
plain language, conclusion first.

Structure, in this order:

1. **Bottom line (one short paragraph).** What happened, how serious, how
   confident, and the single most important action. A busy reader can stop here
   and act correctly.
2. **What happened.** The attack story as plain chronological prose — full
   sentences, not fragments: "At 09:12 the attacker ran a script on WKS-2231,
   which let them reach the database server SRV-DB1 nine minutes later." Say the
   business impact (which systems, which data), not only technique codes.
3. **How we know.** The key evidence in plain terms. Put the step-by-step detail
   in a **table** (time · what happened · source) so it scans at a glance.
4. **What to do.** Recommendations in priority order — plain imperatives, split
   into "do now" and "verify first", each with a one-line why.
5. **What we're unsure about.** The gaps, and what would resolve each.

Rules for the prose:

- **Lead with the conclusion (BLUF).** Never make the reader assemble the verdict
  from scattered facts.
- **Plain language.** Expand every acronym and technique on first use — "lateral
  movement (moving from one machine to another; MITRE T1021)". A reader who does
  not know ATT&CK must still follow it.
- **One logical thread.** Chronological or causal order; do not jump around.
- **Narrative for the story, a table for the timeline.** Do not dump the JSON or
  a wall of fragments as the report.
- **It must stand alone.** Every claim still traces to evidence in the object, but
  the reader should not need a locator to understand the logic.
- Keep the prose and the JSON consistent — same facts, same order, no contradiction.

Nothing in the summary may exceed what the object's locators support.
