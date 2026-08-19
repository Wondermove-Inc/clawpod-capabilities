# Data Access — SIEM-agnostic

The correlation pipeline needs security events. The agent is given the site's
**SIEM connection info**; the SIEM product varies by site. This file defines
*what* to ask the SIEM for, not *which* SIEM — you adapt to whatever you are
connected to.

## Two query primitives (all correlation reduces to these)

### 1. Search by pivot

> Given an **entity** (IP, host, user, hash, domain, URL) and a **time window**,
> return matching events from **all connected sources**.

This is the engine of correlation: you start from an alert's entities, pull
everything else that touched them nearby in time, then pivot on the new entities
you find. The SIEM's own search does the cross-source join.

Each returned event must yield the normalized fields below (or `null`).

### 2. Fetch by locator

> Given a stable alert/event **id**, return that full record.

Used to expand a summarized alert into its full evidence, and to re-fetch anything
you cite.

## Normalized event contract (what every result must map to)

```
time      UTC event time (not ingest time)
source    device/product: firewall, IDS/IPS, EDR, proxy, DNS, email, identity/auth
actor     initiator: user, process, source IP
target    acted-on: host, destination IP, URL, file
action    login, connection, block, exec, dns_query, email_delivery, ...
entities  all pivotable ids: IPs, hostnames, usernames, hashes, domains, ports
severity  device-reported
locator   stable id to re-fetch this record  (never dropped)
```

If the SIEM's field names differ (they will), map them to these. Keep the raw
record reachable via `locator`.

## Adapting to any SIEM (procedure)

1. **Identify the product and interface** from the connection info and its
   documentation: base endpoint, index/space/tenant, auth method, and the
   read/search API.
2. **Find the search primitive**: how this product runs a filtered, time-bounded,
   read-only search (query DSL, SPL, KQL/ES|QL, UDM, WQL, …) and how it returns
   records with ids.
3. **Find the fetch primitive**: how to retrieve a single record by id.
4. **Map fields** from the product's schema to the normalized contract above.
5. **Confirm read-only + scope** before the first query (a preflight/list call is
   ideal); note anything the account cannot do.

Do this discovery once per session and reuse it. Prefer an approved
adapter/harness/helper if the environment provides one; only query the SIEM
directly when that is how the site expects the analyst agent to work.

## Safety (non-negotiable)

- **Read-only.** Search and fetch only. Never create/modify detection rules,
  connectors, dashboards, or cases through this skill; case/comment writes and any
  containment are separate, approved actions.
- **Always bounded.** Every search carries a time window and a result cap. Widen
  deliberately, never unbounded.
- **No arbitrary exploration.** Query only for entities/windows the investigation
  needs; do not sweep the whole SIEM.
- **Credentials stay in the connection.** Use the provided connection; never echo,
  log, or write credentials into reports or files.
- **No connection info → pause.** Request it; never guess an endpoint or fabricate
  events.
