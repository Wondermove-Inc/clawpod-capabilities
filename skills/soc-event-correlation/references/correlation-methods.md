# Correlation Methods — similarity, sequence, case

The literature groups security event correlation into three families. Each has a
distinct strength and a distinct blind spot. Apply all three; never stop at the
cheapest one.

## 1. Similarity-based

Correlate two events when their attributes or times are close, using a distance
measure over shared fields (same source IP, same user, same rule, within N
seconds).

- **Good for**: collapsing duplicates and fan-out, first-pass grouping, cheap and
  scalable.
- **Blind spot**: it cannot prove a multi-step attack. Two similar events may be
  the same benign process repeated. Similarity groups noise; it does not explain
  intent.
- **Use in**: Stage 2 (aggregate) and as weak spatial edges in Stage 3.

## 2. Sequence / causal

Correlate events that stand in a prerequisite → consequence relationship: one
event creates the condition the next one needs.

- Model each attack step as having **prerequisites** (what must be true first) and
  **consequences** (what becomes true after). Link step A→B when A's consequence
  satisfies B's prerequisite.
- Examples: successful credential use → authenticated session; exploit →
  child-process spawn; beacon to C2 → outbound bulk transfer; new local admin →
  lateral RDP.
- **Good for**: multi-step and *previously unseen* attacks — the chain logic does
  not need a signature for the whole attack, only for the step relationships.
- **Blind spot**: needs reliable timing/causality; noisy timestamps or missing
  telemetry break the chain. Record the gap instead of guessing the link.
- **Use in**: Stage 3 causal edges and Stage 4 scenario order. This is the primary
  technique for the incident narrative.

## 3. Case-based

Compare the new cluster to a library of previously resolved incidents; classify
and predict from the closest matches.

- **Good for**: fast classification ("this looks like the September phishing→token
  theft case"), setting priors on confidence, and reusing a known-good response.
- **Blind spot**: anchored to the past — a novel attack has no near case; do not
  force a match. A weak case match lowers, not raises, confidence.
- **Use in**: Stage 4/5 to calibrate confidence and seed the recommendation, and
  to flag "no prior case → treat as novel, widen collection".

## Combining them

- Similarity reduces volume → sequence builds the story → case calibrates
  confidence and response.
- Disagreement is signal: if similarity groups events that sequence logic cannot
  causally link, the group is probably coincidental — split it.
- Confidence for a link = strength of its edges (specific shared entity + tight
  causal fit + supporting case) minus down-weights (shared/high-cardinality
  entity, large time gap, missing telemetry).

## Anti-patterns

- Declaring an incident from similarity alone ("50 alerts share this IP" — the IP
  may be a proxy).
- Building a causal chain across a telemetry gap by assumption.
- Forcing a case match to a novel attack to feel more certain.
