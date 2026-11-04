# Data access (any SIEM)

The SIEM differs per site (Splunk, Elastic, QRadar, Sentinel, Chronicle, OpenSearch, Wazuh, …). Use the connection info you were given and the product's own documentation.

## Find out once per session

1. Product, endpoint, index/space/tenant, auth method.
2. How to run a filtered, time-bounded search (SPL, KQL/ES|QL, AQL, Query DSL, UDM Search/YARA-L, …) that returns record ids.
3. How to fetch one record by id.
4. How its field names map to the common fields below.

If the environment provides an adapter or harness for the SIEM, use it.

## Two operations

- **Search by pivot:** entity + time window → matching events from all sources.
- **Fetch by id:** id → the full record (to expand an alert and to re-check anything you cite).

## Common event fields

```
time      UTC event time (not ingest time)
source    device/product: firewall, IDS/IPS, EDR, proxy, DNS, email, identity
actor     initiator: user, process, source IP
target    acted-on: host, destination IP, URL, file
action    login, connection, block, exec, dns_query, email_delivery, ...
entities  pivotable ids: IPs, hostnames, usernames, hashes, domains, ports
severity  device-reported
id        record id to re-fetch it (always keep)
```

Unknown field → `null`, never a guess. Keep the original time zone explicit.
