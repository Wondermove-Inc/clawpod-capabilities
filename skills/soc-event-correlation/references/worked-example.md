# Worked Example — one end-to-end pass

Illustrative only (entities are placeholders). It shows the loop, link
strength, scope sweep, alternative explanations, and confidence — not a
specific SIEM's syntax.

## Seed

Triggering alert: EDR flags `powershell.exe` spawning `rundll32.exe` on host
`WKS-2231`, user `j.kim`, at `T0` (event id `edr:a1b2`).

Seed entities: host `WKS-2231`, user `j.kim`, process lineage. Initial window
`T0 ± 1h`.

## Pivot and expand

1. Pivot on `WKS-2231` + `j.kim` in the window:
   - Windows logon: `j.kim` interactive logon to `WKS-2231` at `T0−12m`, logon
     id `0x3e7a` (`wlog:5f`).
   - EDR network: the `rundll32.exe` process from `edr:a1b2` connects out at
     `T0+3m` (`edr:a1c0`).
   - Proxy: `WKS-2231` → `cdn-update[.]example` (rare domain), `T0+3m`
     (`proxy:77aa`).
   - Identity: `j.kim` Kerberos TGS for `SRV-DB1` at `T0+9m` (`idp:6a`).
2. Expand on new specific entity `cdn-update[.]example`:
   - Threat intel: domain flagged as known C2 staging (enrichment, raises confidence
     in the link).
   - Two other hosts queried the same domain within 20m (`proxy:81bd`,
     `proxy:83c1`) — possible fan-out.
3. Expand on `SRV-DB1` (crown-jewel asset):
   - Windows logon: `j.kim` network logon to `SRV-DB1` at `T0+11m` (`wlog:22`);
     no prior history of `j.kim` on `SRV-DB1` (first-time access).
4. Scope sweep: hash of the DLL `rundll32` loaded (from `edr:a1b2`) and
   `cdn-update[.]example` across all hosts, last 30 days — hits only on the two
   fan-out hosts. EDR is missing on 12 servers, so they are a gap, not clean.
5. Stop: shared entity `10.0.0.1` (the site NAT gateway) appears on hundreds of
   events — infrastructure, not pivoted. No new useful entities remain.

## Linked steps

`wlog:5f` logon → `edr:a1b2` suspicious exec → `edr:a1c0`/`proxy:77aa` C2
beacon → `idp:6a`/`wlog:22` lateral logon to `SRV-DB1`.

Link strength:

- `wlog:5f` → `edr:a1b2`: **Hard** — same logon id `0x3e7a`.
- `edr:a1b2` → `edr:a1c0` → `proxy:77aa`: **Hard** — same process, then same
  flow (same source port, destination and time) seen by EDR and proxy — one
  event, two sensors (§2).
- `proxy:77aa` → `wlog:22`: **Strong** (cause → effect by order) + **Medium**
  (first-time access) — the weakest link, so it caps confidence at medium.

## Framework mapping

- Kill chain: reached **Actions on Objectives** (lateral movement to a DB server)
  → active incident, high urgency.
- ATT&CK: T1059.001 (PowerShell) and T1218.011 (Rundll32) `edr:a1b2`;
  T1071.001 (Web Protocols) `edr:a1c0`/`proxy:77aa`; T1078 (Valid Accounts) and
  T1021 (Remote Services) `idp:6a`/`wlog:22`. Gap: no Initial Access evidence
  yet — a collection task, not an assumption.

## Alternatives considered

- **H1 (leading, medium):** real intrusion — logon→exec→C2→lateral chain with
  a TI-flagged domain and first-time access to a crown jewel. Refuting evidence
  sought: is `cdn-update` a sanctioned tool? Found none. Confidence is capped by
  the weakest link above.
- **H2 (open, low):** benign admin — `j.kim` is IT staff running a script.
  Weakened by the TI-flagged domain and no change ticket; not yet ruled out.
- **H3 (rejected):** false positive — rejected; multiple independent sources
  corroborate.

## Result

- Conclusion: likely active intrusion, reached Actions on Objectives;
  confidence medium (capped by `proxy:77aa` → `wlog:22`).
- Scope: `WKS-2231`, the two fan-out hosts, account `j.kim`, `SRV-DB1`; 12
  servers without EDR unchecked.
- Do now: isolate `WKS-2231` (`edr:a1b2`); block `cdn-update[.]example`
  (`proxy:77aa`); revoke `j.kim` sessions and reset the account (`wlog:22`).
- Verify first: the two fan-out hosts (`proxy:81bd`, `proxy:83c1`); search
  email and web logs for `j.kim` before `T0−12m` to find the entry point.
