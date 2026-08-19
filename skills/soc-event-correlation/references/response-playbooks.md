# Response Playbooks — containment, eradication, recovery

Recommendations follow the NIST / SANS PICERL response phases. This skill
**recommends**; executing any action is a separate, approval-gated step. Every
recommended action names the evidence that justifies it and the asset it protects.

## Prioritize before you list

Order recommendations by:

1. **Kill-chain phase reached** — active C2 / Actions-on-Objectives outranks a
   suspected delivery.
2. **Asset value** — crown-jewel systems, privileged identities, and regulated
   data first.
3. **Confidence** — high-confidence containment goes in "do now"; low-confidence
   steps go in "verify first" with the evidence needed to raise confidence.

Split the output into **Do now** (high-confidence, reversible-enough containment)
and **Verify first** (needs more evidence before acting).

## Containment — limit the spread

Stop the incident from getting worse while you preserve evidence.

- Network: block C2 IPs/domains, isolate affected hosts, restrict the affected
  segment.
- Identity: disable or force-reset compromised accounts, revoke active sessions
  and tokens, step up MFA.
- Endpoint: kill malicious processes, quarantine files, suspend affected services.
- Preserve first: snapshot/image before wiping when evidence value is high.
- Prefer reversible containment when confidence is medium; note the blast radius.

## Eradication — remove the root cause

- Remove malware, backdoors, persistence (scheduled tasks, services, run keys,
  rogue accounts).
- Patch or reconfigure the exploited weakness so the same entry cannot be reused.
- Rotate credentials and secrets exposed during the intrusion.
- Verify eradication against the ATT&CK persistence/defense-evasion techniques you
  mapped — each mapped technique is a checklist item to clear.

## Recovery — restore safely

- Restore systems from known-good state; validate integrity before returning to
  production.
- Monitor recovered assets for re-compromise (the same IOCs and techniques).
- Lift containment gradually, watching for the attacker's return.

## Post-incident (hand-off note)

- Capture what worked, the dwell time, and the detection gaps (tactics with no
  evidence → detection-engineering follow-up).
- Record the incident as a **case** for future case-based correlation
  (`references/correlation-methods.md`).

## Recommendation writing rules

- One action per line, imperative, with: the action, the target asset, the
  justifying evidence locator, and the expected effect.
- State reversibility and blast radius for containment actions.
- Never recommend an action the evidence does not support; if you are unsure,
  it belongs in "verify first" with the collection step named.
- Recommend, do not execute. Blocking/isolating/disabling is an approval-gated
  action outside this skill.
