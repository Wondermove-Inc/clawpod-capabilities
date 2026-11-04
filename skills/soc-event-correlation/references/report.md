# Report format

One report per incident. Write it so an on-call responder or manager understands it without the raw logs. Plain language; expand every acronym and technique on first use ("lateral movement — moving from one machine to another; MITRE T1021").

1. **Bottom line** (one short paragraph): what happened, how serious, how confident, and the most important action.
2. **What happened:** the attack story in chronological prose, with business impact (which systems, which data).
3. **How we know:** a table — time · what happened · source · event id.
4. **What to do:** prioritized actions, split into do now / verify first, each with a one-line why.
5. **What we're unsure about:** gaps, alternatives considered and why they were rejected, and the data that would resolve each.

Every statement must trace to an event id in the table.

If a machine-readable record is requested, give a JSON object with the same facts: `incident` (title, hypothesis, confidence, status, kill_chain_phase, severity, first_seen, last_seen), `entities`, `steps` (time, summary, ATT&CK technique, kill-chain phase, event ids), `alternatives`, `gaps`, `recommendations` (do_now, verify_first).
