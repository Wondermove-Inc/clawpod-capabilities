# Worked Example — one end-to-end pass

Illustrative only (entities are placeholders). It shows the loop, evidence
anchoring, competing hypotheses, and confidence — not a specific SIEM's syntax.

## Seed

Triggering alert: EDR flags `powershell.exe` spawning `rundll32.exe` on host
`WKS-2231`, user `j.kim`, at `T0` (locator `edr:a1b2`).

Seed entities: host `WKS-2231`, user `j.kim`, process lineage. Initial window
`T0 ± 1h`.

## Pivot and expand

1. Pivot on `WKS-2231` + `j.kim` in the window:
   - Proxy: `WKS-2231` → `cdn-update[.]example` (rare domain), `T0+3m`
     (`proxy:77aa`).
   - Identity: `j.kim` interactive logon to `WKS-2231` at `T0−12m` (`idp:5f`),
     then `j.kim` Kerberos TGS for `SRV-DB1` at `T0+9m` (`idp:6a`).
2. Expand on new high-value entity `cdn-update[.]example` (specific domain):
   - Threat intel: domain flagged as known C2 staging (enrichment, raises edge
     weight).
   - Two other hosts queried the same domain within 20m (`proxy:81bd`,
     `proxy:83c1`) — possible fan-out.
3. Expand on `SRV-DB1` (crown-jewel asset):
   - Auth: successful `j.kim` logon to `SRV-DB1` at `T0+11m` (`idp:6a` → session
     `wlog:22`); no prior history of `j.kim` on `SRV-DB1` (anomaly).
4. Stop: shared entity `10.0.0.1` (the site NAT gateway) appears on hundreds of
   events — infrastructure noise, down-weighted, not pivoted. Budget reached.

## Graph → scenario (causal order)

`idp:5f` logon → `edr:a1b2` suspicious exec → `proxy:77aa` C2 beacon →
`idp:6a`/`wlog:22` lateral auth to `SRV-DB1`. Each link is prerequisite→consequence.

## Framework mapping

- Kill chain: reached **Actions on Objectives** (lateral movement to a DB server)
  → active incident, high urgency.
- ATT&CK: T1059.001 (PowerShell) `edr:a1b2`; T1071 (C2 over web) `proxy:77aa`;
  T1021 (Lateral Movement) `idp:6a`. Gap: no Initial Access evidence yet — a
  collection task, not an assumption.
- Diamond: victim `WKS-2231`/`SRV-DB1`/`j.kim`; infrastructure `cdn-update`;
  capability PowerShell loader; adversary unattributed.

## Competing hypotheses

- **H1 (leading, medium-high):** real intrusion — logon→exec→C2→lateral chain with
  a TI-flagged domain and first-time access to a crown jewel. Refuting evidence
  sought: is `cdn-update` a sanctioned tool? Found none.
- **H2 (open, low):** benign admin — `j.kim` is IT staff running a script.
  Refuted by the TI-flagged domain and no change ticket.
- **H3 (rejected):** false positive — rejected; multiple independent sources
  corroborate.

## Report (abbreviated — note the plain, conclusion-first style)

**Bottom line.** We have a likely active intrusion (confidence medium-high). An
attacker on workstation WKS-2231, using the account `j.kim`, ran a suspicious
script, contacted a known malicious server, and then reached the database server
SRV-DB1 — a crown-jewel system `j.kim` had never accessed before. **Isolate
WKS-2231 and suspend the `j.kim` account now.**

**What happened.** At T0 the account `j.kim` was already logged in to WKS-2231.
At T0 the endpoint tool saw PowerShell launch another program in a way malware
commonly uses. Three minutes later the machine contacted `cdn-update[.]example`,
a domain threat intelligence lists as attacker command-and-control. Nine minutes
after that, `j.kim` authenticated to the database server SRV-DB1 for the first
time ever — consistent with the attacker moving deeper into the network (lateral
movement; MITRE T1021). We did not find how the attacker first got in.

**How we know** (each row is backed by a log record):

| Time | What happened | Source |
|---|---|---|
| T0−12m | `j.kim` logs in to WKS-2231 | identity |
| T0 | PowerShell spawns rundll32 (malware-like) | EDR |
| T0+3m | WKS-2231 → `cdn-update[.]example` (known C2) | proxy + threat intel |
| T0+11m | `j.kim` first-ever logon to SRV-DB1 | identity + auth |

**What to do.** Do now: isolate WKS-2231; suspend `j.kim`'s sessions and tokens;
block `cdn-update[.]example` at the proxy. Verify first: check the two other hosts
that reached the same domain; hunt for how the attacker first got in.

**Open questions.** Initial entry point is unknown — pull email and web logs for
`j.kim` before T0−12m to find it.
