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

## Minimal human summary (accompanies the object)

> **[severity] title** — hypothesis (confidence). Reached *kill-chain phase*;
> techniques: T…, T…. Do now: 1–3 highest-priority actions. Gaps: what's missing.

Nothing in the summary may exceed what the object's locators support.
